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
        