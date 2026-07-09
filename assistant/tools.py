import os
import subprocess
import webbrowser
from datetime import datetime

import psutil


ALLOWED_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "file explorer": ["explorer.exe"],
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "task manager": ["taskmgr.exe"],
    "snipping tool": ["snippingtool.exe"],
    "wordpad": ["write.exe"],
    "device manager": ["devmgmt.msc"],
    "settings": ["cmd.exe", "/c", "start", "ms-settings:"],
}

ALLOWED_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "spotify": "https://open.spotify.com",
}


class JarvisTools:
    def open_app(self, app_name):
        app_name = app_name.lower().strip()
        command = ALLOWED_APPS.get(app_name)

        if command is None:
            # Try launching dynamically via shell start command
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", app_name], shell=True)
                return f"Attempting to launch {app_name}."
            except Exception:
                return f"I don't have permission to open {app_name} yet."

        try:
            subprocess.Popen(command)
        except Exception:
            # Fallback to shell start
            try:
                # E.g. command[0] is 'chrome.exe'
                subprocess.Popen(["cmd.exe", "/c", "start", command[0]], shell=True)
            except Exception:
                return f"Failed to open {app_name}."

        return f"Opening {app_name}."

    def open_website(self, website_name):
        website_name = website_name.lower().strip()

        # If it is a direct domain name (e.g., "github.com", "google.co.uk", "localhost:3000")
        if "." in website_name or ":" in website_name or website_name.startswith("http"):
            url = website_name
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            webbrowser.open(url)
            return f"Opening {website_name}."

        # Otherwise look in allowed dictionary
        url = ALLOWED_WEBSITES.get(website_name)

        if url is None:
            # Dynamically guess the domain as www.website_name.com
            guessed_url = f"https://www.{website_name}.com"
            webbrowser.open(guessed_url)
            return f"I couldn't find {website_name} in my allowed list, so I am opening {guessed_url}."

        webbrowser.open(url)
        return f"Opening {website_name}."

    def search_google(self, query):
        query = query.strip()
        url = f"https://www.google.com/search?q={subprocess.list2cmdline([query])[1:-1]}"
        # Double check URL formatting
        import urllib.parse
        safe_query = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={safe_query}"
        webbrowser.open(url)
        return f"Searching Google for: {query}."

    def search_youtube(self, query):
        query = query.strip()
        import urllib.parse
        safe_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={safe_query}"
        webbrowser.open(url)
        return f"Searching YouTube for: {query}."

    def get_time(self):
        return datetime.now().strftime(
            "It is %I:%M %p."
        )

    def get_date(self):
        return datetime.now().strftime(
            "Today is %A, %B %d, %Y."
        )

    def get_system_status(self):
        cpu = psutil.cpu_percent(interval=0.3)
        memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()

        response = (
            f"CPU usage is {cpu:.0f} percent. "
            f"Memory usage is {memory.percent:.0f} percent."
        )

        if battery is not None:
            response += (
                f" Battery level is {battery.percent:.0f} percent."
            )

        return response

    def get_weather(self, location=None):
        import requests
        
        # 1. If location is not specified, auto-detect using free Geo-IP lookup
        if not location:
            try:
                r = requests.get("https://ipapi.co/json/", timeout=2)
                if r.status_code == 200:
                    d = r.json()
                    location = d.get("city") or d.get("region")
            except Exception:
                pass
        
        if not location:
            location = "London"  # fallback default
            
        # 2. Get Latitude & Longitude using Open-Meteo Geocoding
        lat, lon, display_name = None, None, location
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
            gr = requests.get(geo_url, timeout=3)
            if gr.status_code == 200 and gr.json().get("results"):
                res = gr.json()["results"][0]
                lat = res["latitude"]
                lon = res["longitude"]
                display_name = f"{res['name']}, {res.get('country', '')}"
        except Exception:
            pass
            
        if lat is None or lon is None:
            # Simple fallback coordinates for common fallback
            lat, lon = 51.5074, -0.1278  # London
            display_name = "London (Fallback)"

        # 3. Fetch Forecast from Open-Meteo
        try:
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            wr = requests.get(weather_url, timeout=3)
            if wr.status_code == 200:
                cw = wr.json()["current_weather"]
                temp = cw["temperature"]
                wind = cw["windspeed"]
                code = cw["weathercode"]
                
                # Weather code translation mapping
                descriptions = {
                    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
                    45: "foggy", 48: "depositing rime fog", 51: "light drizzle", 53: "moderate drizzle",
                    55: "dense drizzle", 61: "slight rain", 63: "moderate rain", 65: "heavy rain",
                    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
                    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
                    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail"
                }
                desc = descriptions.get(code, "fair conditions")
                return f"Currently in {display_name}, it is {temp:.1f}°C with {desc}. Wind speed is {wind:.1f} km/h."
        except Exception as e:
            return f"I couldn't fetch the weather for {location} right now, sir."

    def get_news(self):
        import requests
        import xml.etree.ElementTree as ET
        
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                items = root.findall(".//item")[:4]
                headlines = []
                for i, item in enumerate(items, 1):
                    title = item.find("title").text
                    # strip source name e.g., " - Times of India"
                    title = title.split(" - ")[0]
                    headlines.append(f"{i}. {title}")
                return "Here are the top news headlines: " + " | ".join(headlines)
        except Exception:
            pass
        return "I'm unable to connect to the news feed right now, sir."

    def define_word(self, word):
        import requests
        word = word.strip().lower()
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                definition = data[0]["meanings"][0]["definitions"][0]["definition"]
                part_of_speech = data[0]["meanings"][0]["partOfSpeech"]
                return f"{word.capitalize()} ({part_of_speech}): {definition}"
            elif r.status_code == 404:
                return f"I couldn't find a definition for '{word}', sir."
        except Exception:
            pass
        return f"I'm having trouble accessing my dictionary tools right now."

    def convert_currency(self, amount, from_curr, to_curr):
        import requests
        from_curr = from_curr.strip().upper()
        to_curr = to_curr.strip().upper()
        url = f"https://open.er-api.com/v6/latest/{from_curr}"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                rates = data.get("rates", {})
                if to_curr in rates:
                    rate = rates[to_curr]
                    result = float(amount) * rate
                    return f"{amount} {from_curr} is approximately {result:.2f} {to_curr}."
                else:
                    return f"I don't know the exchange rate for {to_curr}, sir."
        except Exception:
            pass
        return "I'm unable to perform currency conversion right now, sir."
        