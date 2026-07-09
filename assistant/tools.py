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
            return f"I don't have permission to open {app_name} yet."

        subprocess.Popen(command)

        return f"Opening {app_name}."

    def open_website(self, website_name):
        website_name = website_name.lower().strip()

        url = ALLOWED_WEBSITES.get(website_name)

        if url is None:
            return f"I don't know the website {website_name} yet."

        webbrowser.open(url)

        return f"Opening {website_name}."

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
        