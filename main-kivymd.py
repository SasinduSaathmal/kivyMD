from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.uix.dialog import MDDialog
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.uix.button import MDFlatButton
from kivymd.uix.menu import MDDropdownMenu
from kivy.network.urlrequest import UrlRequest
from kivy.clock import Clock
from kivy.utils import platform
import pandas
import aiohttp
import json
import datetime
import geocoder
import pytz
import asyncio
import requests
import os
import certifi
import ssl
import sys
from kivy.resources import resource_add_path, resource_find


ssl.default_ca_certs = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

if platform == "win":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

Builder.load_file("weather-md.kv")


class WeatherUI(Screen):
    pass


class ChangeDialog(MDBoxLayout):
    pass


class NoInternetInterface(Screen):
    pass


class MessageHandler():
    def __init__(self, **kwargs):
        super(MessageHandler, self).__init__(**kwargs)

    def cityNotFound(self):
        print("City Not Found")
        if not self.alert_dialog:
            self.alert_dialog = MDDialog(
                title="City Not Found!",
                text="The city or the country you typed is probably wrong.",
                buttons=[
                    MDFlatButton(
                        text="OK",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=lambda x: self.closeDialog(alert=True, dialog=True, error=False),
                    )
                ],
            )

        try:
            self.root.ids.city.text = self.city = self.old_city.capitalize()
            self.root.ids.country.text = self.country = self.old_country.capitalize()
            self.country_code = self.old_country
        except Exception as e:
            self.root.ids.city.text = self.city
            self.root.ids.country.text = self.country

        self.alert_dialog.open()

    def connectionError(self):
        if not self.is_retry_event:
            self.retry_event = Clock.schedule_interval(self.retry, 3)
            self.is_retry_event = True

        self.conn_error_dialog = MDDialog(
            title = "Connection Error",
            text = "Failed to connect to the api after 10 max retries.",
            widget_style = "android",
            buttons = [
                MDFlatButton(
                    text = "RETRY",
                    text_color = "red",
                    on_release = lambda x: self.closeDialog(dialog=False, alert=False, error=True),
                    )
                ],
            )

        if not self.first_run:
            self.root.ids.city.text = self.city = self.old_city.capitalize()
            self.root.ids.country.text = self.country = self.old_country.capitalize()
            self.country_code = self.old_country

        self.conn_error_dialog.open()

    def get_city(self, *args):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Change the city",
                type="custom",
                content_cls=self.cdialog,
                buttons=[
                    MDFlatButton(
                        text="CANCEL",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=lambda x: self.closeDialog(dialog=True, alert=False, error=False),
                    ),
                    MDFlatButton(
                        text="UPDATE",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=self.get_data,
                    ),
                ],
            )
        self.dialog.open()
        print(self.city, self.country)


    def closeDialog(self, *args, **kwargs):
        if kwargs["dialog"] == True:
            self.dialog.dismiss(force=True)
        if kwargs["alert"] == True:
            self.alert_dialog.dismiss(force=True)
        if kwargs["error"] == True:
            self.conn_error_dialog.dismiss(force=True)
            self.conn_error_dialog_closed = True


class DataHandler():
    def __init__(self, **kwargs):
        super(DataHandler, self).__init__(**kwargs)

    def checkConnection(self):
        self.is_retrying = True
        try:
            resp = requests.get("https://example.com")
            status = resp.status_code
            return True, status
        except Exception as e:
            return False, e


    async def get_my_current_location(self):
        try:
            g = geocoder.ip("me")
            if g.latlng is not None:
                coordinates = g.latlng
                if coordinates is not None:
                    latitude, longitude = coordinates
                    self.root.ids.city.text = self.city = g.city
                    self.root.ids.country.text = self.country_code = g.country
                    index = list(self.country_codes).index(self.country_code)
                    self.country = self.countries[index]
                    self.is_ip = False
                    return latitude, longitude
                else:
                    print("Unable to retrieve your GPS coordinates.")
            else:
                return None

        except Exception as e:
            print(f"GPS Location Exception: {e}")
        return None

    async def get_location(self, location_url):
        async with self.session.get(location_url, ssl=False) as location_response:
            if location_response.status == 200:
                json_data = await location_response.json()

                try:
                    lat = json_data[0]["lat"]
                    lon = json_data[0]["lon"]
                except Exception as e:
                    lat, lon = 1, 1
                    error_path = os.path.join("", "Errors.txt")
                    with open(error_path, "a") as error_file:
                        dt = datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")
                        error_file.write(f"[{dt}] {str(e)}\n")

                return lat, lon

            else:
                print(
                    "Error",
                    f"An error occurred! Error code {location_response.status}",
                )

    async def get_weather_data(self, weather_url):
        async with self.session.get(weather_url, ssl=False) as weather_response:
            if weather_response.status == 200:
                json_data = await weather_response.json()
                json_location = os.path.join("", "response.json")
                with open(json_location, "w") as file:
                    json.dump(json_data, file, indent=4, sort_keys=True)

                return "Success"
            else:
                print(f"An error occurred! Error code {weather_response.status}")

    def extractCountryData(self):
        path = os.path.join("assets", "country-data.csv")
        data = pandas.read_csv(path)
        countries = data.Name.values
        country_codes = data.Code.values
        return countries, country_codes

    def modify_time(self, json_data, key, subkey=None, tz=False, timezone=None):
        if subkey == None:
            json_utc_time = json_data[key]
        else:
            json_utc_time = json_data[key][subkey]
        utc_datetime = datetime.datetime.utcfromtimestamp(json_utc_time)
        my_timezone = pytz.timezone("Asia/Colombo")
        datetime_change = utc_datetime.astimezone(my_timezone).strftime("%z")
        mins = int(datetime_change[3:])
        hours = int(datetime_change[1:3])
        op = datetime_change[0]
        if tz == True:
            hours, mins, op = self.modify_timezone(timezone)
        if op == "+":
            time_to_add = datetime.timedelta(hours=hours, minutes=mins)
            new_time = utc_datetime + time_to_add
            time = new_time.strftime("%H:%M:%S")
        else:
            time_to_substract = datetime.timedelta(hours=hours, minutes=mins)
            new_time = utc_datetime - time_to_substract
            time = new_time.strftime("%H:%M:%S")

        return time

    def modify_timezone(self, utc_timezone):
        timezone = utc_timezone / 3600
        if timezone > 0:
            hour, min = tuple(str(round(timezone, 1)).split("."))
            op = "+"
        else:
            hour, min = tuple(str(round(timezone, 1)).replace("-", "").split("."))
            op = "-"
        min = int(int(min) * 6)
        return int(hour), min, op

    def kelvin2celsius(self, value):
        celsius_value = round(value - 273.15, 2)
        return celsius_value

    async def modify(self):
        with open("response.json", "r") as file:
            json_data = json.load(file)

        timezone = json_data["timezone"]
        time = self.modify_time(json_data, "dt", tz=True, timezone=timezone)
        feels_like_temp = self.kelvin2celsius(json_data["main"]["feels_like"])
        humidity = json_data["main"]["humidity"]
        temperature = self.kelvin2celsius(json_data["main"]["temp"])
        sunrise = self.modify_time(json_data, "sys", "sunrise", True, timezone)
        sunset = self.modify_time(json_data, "sys", "sunset", True, timezone)
        wind = json_data["wind"]["speed"]
        icon = json_data["weather"][0]["icon"]
        icon_url = self.setIconAnimation(str(icon))
        description = json_data["weather"][0]["description"]
        main = json_data["weather"][0]["main"]
        self.icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"
        self.weather_data = {
            "time": str(time),
            "temp": str(temperature),
            "feels_like": str(feels_like_temp),
            "humidity": str(humidity),
            "sunset": str(sunset),
            "sunrise": str(sunrise),
            "weather": str(main),
            "weather-info": str(description),
            "icon": str(icon_url),
            "wind": str(wind),
        }


    def setIconAnimation(self, icon):
        anime_urls = {"01d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "01n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "02d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "02n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "03d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "03n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "04d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "04n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "09d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "09n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "10d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "10n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "11d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "11n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "13d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "13n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "50d": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__",
                    "50n": "https://private-cdn.lottie.host/104a8665-dede-4f65-8784-2bcb9eb9e7b6/variation/OvlgitWG7i.gif?versionId=.zJT3J1xY1kRFSMhHR4WeyFawWRTS5HA&response-content-disposition=attachment&Expires=1708110838&Key-Pair-Id=KIYCB0SQ8V5G8&Signature=LfC2rJY-zz47SypBnBOcQ8ymSeIDQlg-93qlB2ASl341QSAfXuy7VT87nK20qFxWR9Vf1n9ULheOc2Utk-UY~k3do~Fwy~wx1y~lutQ51ZAUVFqa7HJNanDsA-fEz1lTMUmw7DL4jzXrL2c-XK1hEDgqnx6gaWX-xJRMcmH0kSyFvUUZIPwAmxSrlAcSDUavN3s1DLFwu-lDMEiJFQWCqaRhC8CULcTlGPjoG8gc-jtDImlp5Z-5LopAa3gtadBokel-02KwcS9sbm4iEuhteY7271ZxqQVMN9XzDl8sPCVFsJrZZZCRJg4wFp2HWiXeSJ9TA6u~ElXP6KcyuFZD5g__"}

        url = anime_urls[icon]
        return url


class WeatherApp(MDApp, MessageHandler, DataHandler):
    def __init__(self, **kwargs):
        super(WeatherApp, self).__init__(**kwargs)

        self.request_in_progress = False  # Flag to track request status
        self.first_run = True
        self.called = False
        self.alert_dialog = None
        self.dialog = None
        self.conn_error_dialog = None
        self.is_retry_event = False
        self.is_retrying = False
        self.is_ip = True
        self.city = "City"
        self.country_code = "Country code"
        self.country = "Country"
        self.max_retries = 10
        self.retry_counter = 0

    def build(self):
        # self.theme_cls.colors = colours
        self.icon = "images/weather-icon.png"
        self.theme_cls.theme_style_switch_animation = True
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.theme_style = "Dark"
        sm = ScreenManager()
        weather_interface = WeatherUI(name="online")
        offline_screen = NoInternetInterface(name="offline")
        sm.add_widget(weather_interface)
        sm.add_widget(offline_screen)
        sm.current = "offline"

        return sm

    def on_start(self):
        self.initMenu()
        Clock.schedule_once(self.start_request)
        Clock.schedule_interval(
            self.check_request_status, 0.5
        )  # Check status every 0.5 seconds

    def changeTheme(self, x):
        # "#607D8B"
        self.theme_cls.theme_style = (
            "Dark" if self.theme_cls.theme_style == "Light" else "Light"
        )

    def initMenu(self):
        countries, country_codes = self.extractCountryData()
        self.countries = countries
        self.country_codes = country_codes

        self.cdialog = ChangeDialog()

        self.menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": str(i),
                "on_press": lambda x=str(i): self.changeCountry(x),
            }
            for i in self.countries
        ]

        self.menu = MDDropdownMenu(
            caller=self.cdialog.ids.country_input,
            items=self.menu_items,
            ver_growth="down",
            hor_growth="right",
            position="center",
            width_mult=4,
            max_height=200,
            elevation=5,
        )

    def filterCountries(self, *args):
        country_input = self.cdialog.ids.country_input.text.lower()

        def filterCountry(country):
            if country_input in country:
                return True

        if (not country_input == "") and (not self.called == True):
            items = list(filter(filterCountry, self.countries))
            self.menu_items = [
                {
                    "viewclass": "OneLineListItem",
                    "text": str(i),
                    "on_press": lambda x=str(i): self.changeCountry(x),
                }
                for i in items
            ]
            self.menu.items = self.menu_items
            self.menu.dismiss()
            self.menu.open()

            self.menu_items = [
                {
                    "viewclass": "OneLineListItem",
                    "text": str(i),
                    "on_press": lambda x=str(i): self.changeCountry(x),
                }
                for i in self.countries
            ]

        self.called = False

    def retry(self, *args):
        self.retry_counter += 1
        status, code = self.checkConnection()
        if status == True:
            if self.is_retrying == True:
                self.is_retrying = False
                self.retry_event.cancel()
                self.is_retry_event = False
            Clock.schedule_once(self.start_request)
        else:
            print(code)

        if self.retry_counter % 10:
            self.connectionError()

    def changeCountry(self, text):
        self.called = True
        print(text)
        self.cdialog.ids.country_input.text = text
        index = list(self.countries).index(text.lower())
        # self.city = self.cdialog.ids.city_input.text
        # self.country = text
        # self.country_code = self.country_codes[index]
        self.menu.dismiss()

    def doProgress(self, state):
        if state == "off":
            print("Start")
            self.root.ids.progress.start()
        if state == "on":
            print("Stop")
            self.root.ids.progress.stop()

    def get_data(self, *args):
        self.dialog.dismiss(force=True)
        if not self.request_in_progress:
            self.root.ids.progress.start()
            self.old_city = self.city
            self.old_country = self.country
            print(f"[Log1]Old: {self.old_city}, {self.old_country} | New: {self.city}, {self.country}")
            self.old_country_code = self.country_code
            self.country = self.cdialog.ids.country_input.text
            try:
                index = list(self.countries).index(self.country.lower())
                self.country_code = self.country_codes[index]
            except Exception:
                print(f"[Error]Old: {self.old_city}, {self.old_country} | New: {self.city}, {self.country}")
                self.country = self.old_country
                self.dialog.dismiss(force=True)
                self.cityNotFound()
                return
            self.city = self.cdialog.ids.city_input.text
            Clock.schedule_once(self.start_request)
        self.root.ids.progress.stop()

    def start_request(self, *args):
        self.request_in_progress = True
        Clock.schedule_once(
            lambda dt: asyncio.run(self.make_request(self.city, self.country_code))
        )
        print(self.city, self.country, self.country_code)

    async def make_request(self, city, country_code):
        api_key = "c4fd92f2363b707ff8f8f192e5d3f02c"
        async with aiohttp.ClientSession(trust_env=True) as self.session:
            if not self.first_run:
                if not self.is_ip:
                    location_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city},{country_code}&limit=1&appid={api_key}"
                    for i in range(self.max_retries):
                        self.doProgress("off")
                        try:
                            lat, lon = await self.get_location(location_url)
                            self.doProgress("on")
                            break
                        except Exception as e:
                            print(f"Error at getting location: {e}")

                    else:
                        self.connectionError()
                        return

            else:
                for i in range(self.max_retries):
                    self.doProgress("off")
                    try:
                        lat, lon = await self.get_my_current_location()
                        self.doProgress("on")
                        break
                    except Exception as e:
                        print(f"Error at ip getting location: {e}")

                else:
                    print("[error]connection error")
                    self.connectionError()
                    return

            if lat == 1 and lon == 1:
                print("Error in flow")
                self.root.ids.city.text = self.city = self.old_city
                self.root.ids.country.text = self.country = self.old_country
                self.country_code = self.old_country
                self.dialog.dismiss(force=True)
                self.cityNotFound()
                return "City not found!"
            else:
                weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
                for i in range(self.max_retries):
                    self.doProgress("off")
                    try:
                        status = await self.get_weather_data(weather_url)
                        self.doProgress("on")
                        break
                    except Exception as e:
                        print(f"Error at getting weather data: {e}")
                else:
                    self.connectionError()
                    return

                if not status == "Success":
                    self.city = status
                    return status
                data = await self.modify()
                self.first_run = False
                return data

    def check_request_status(self, dt):
        if self.request_in_progress:
            if not self.first_run:
                self.request_in_progress = False
                # self.root.ids.image.source = f"images/{self.weather_data['icon']}.png"
                self.root.ids.image.source = f"{self.weather_data['icon']}"
                self.root.ids.weather.text = self.weather_data["weather"]
                self.root.ids.weather_info.text = self.weather_data["weather-info"]
                self.root.ids.temperature.text = f"{self.weather_data['temp']}°C"
                self.root.ids.feels_like_temp.text = f"Feels Like {self.weather_data['feels_like']}°C"
                self.root.ids.humidity.text = self.weather_data["humidity"] + "%"
                self.root.ids.sunrise.text = self.weather_data["sunrise"]
                self.root.ids.sunset.text = self.weather_data["sunset"]
                self.root.ids.wind.text = self.weather_data["wind"] + " m/s"

            self.root.ids.city.text = self.city.capitalize()
            self.root.ids.country.text = self.country.capitalize()

    


if __name__ == '__main__':
    if hasattr(sys, '_MEIPASS'):
        resource_add_path(os.path.join(sys._MEIPASS))
    WeatherApp().run()
