import os
import subprocess
import threading
import time
import urllib.request
import webbrowser

import pystray
from PIL import Image, ImageDraw


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Project root is one level above assistant\.
PROJECT_ROOT = os.path.dirname(BASE_DIR)

MAIN_PYTHON = os.path.join(
    PROJECT_ROOT,
    ".venv",
    "Scripts",
    "python.exe",
)

TTS_PYTHON = os.path.join(
    PROJECT_ROOT,
    "external",
    "JarvisLuxTTS",
    ".venv-tts",
    "Scripts",
    "python.exe",
)

ASSISTANT_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "assistant",
    "main.py",
)

UI_SERVER_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "ui",
    "ui_server.py",
)

DESKTOP_GUI_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "ui",
    "jarvis_desktop.py",
)

CONTROL_PANEL_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "ui",
    "controlpanel.py",
)

TTS_DIR = os.path.join(
    PROJECT_ROOT,
    "external",
    "JarvisLuxTTS",
)

HEALTH_URL = "http://127.0.0.1:8765/health"
UI_URL     = "http://localhost:3000"
UI_STATUS  = "http://localhost:3000/status"

CREATE_NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE


class JarvisController:
    def __init__(self):
        self.tts_process          = None
        self.assistant_process     = None
        self.ui_process            = None
        self.desktop_process       = None
        self.control_panel_process = None

        self.lock = threading.Lock()

        self.icon = pystray.Icon(
            "JARVIS",
            self.create_icon(),
            "JARVIS Controller",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Start JARVIS",
                    self.start_from_menu,
                ),
                pystray.MenuItem(
                    "Restart JARVIS",
                    self.restart_from_menu,
                ),
                pystray.MenuItem(
                    "Stop JARVIS",
                    self.stop_from_menu,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Launch Desktop GUI",
                    self.launch_desktop_from_menu,
                ),
                pystray.MenuItem(
                    "Open Control Panel",
                    self.launch_control_panel_from_menu,
                ),
                pystray.MenuItem(
                    "Open Web UI",
                    self.open_ui_from_menu,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Exit Controller",
                    self.exit_from_menu,
                ),
            ),
        )

    # --------------------------------------------------
    # CREATE SYSTEM TRAY ICON
    # --------------------------------------------------

    def create_icon(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(image)

        draw.ellipse((4, 4, 60, 60), outline=(0, 220, 255, 255), width=4)
        draw.ellipse((16, 16, 48, 48), outline=(0, 180, 220, 255), width=3)
        draw.ellipse((29, 29, 35, 35), fill=(255, 255, 255, 255))

        return image

    # --------------------------------------------------
    # PROCESS HELPERS
    # --------------------------------------------------

    def process_running(self, process):
        return (
            process is not None
            and process.poll() is None
        )

    # --------------------------------------------------
    # TTS HEALTH CHECK
    # --------------------------------------------------

    def tts_is_healthy(self):
        try:
            with urllib.request.urlopen(
                HEALTH_URL, timeout=2,
            ) as response:
                return response.status == 200
        except Exception:
            return False

    def ui_is_healthy(self):
        try:
            with urllib.request.urlopen(
                UI_STATUS, timeout=2,
            ) as response:
                return response.status == 200
        except Exception:
            return False

    def wait_for_tts(self, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.tts_is_healthy():
                return True
            if (
                self.tts_process is not None
                and self.tts_process.poll() is not None
            ):
                return False
            time.sleep(2)
        return False

    # --------------------------------------------------
    # START TTS SERVER
    # --------------------------------------------------

    def start_tts(self):
        if self.tts_is_healthy():
            print("TTS server is already online.")
            return True

        if self.process_running(self.tts_process):
            print("TTS server is already starting.")
        else:
            print("Starting JARVIS TTS server...")
            self.tts_process = subprocess.Popen(
                [
                    TTS_PYTHON, "-m", "uvicorn",
                    "tts_server:app",
                    "--host", "127.0.0.1",
                    "--port", "8765",
                ],
                cwd=TTS_DIR,
                creationflags=CREATE_NEW_CONSOLE,
            )

        print("Waiting for TTS server...")
        if self.wait_for_tts():
            print("TTS server is online.")
            return True

        print("TTS server failed to start.")
        return False

    # --------------------------------------------------
    # START MAIN ASSISTANT
    # --------------------------------------------------

    def start_assistant(self):
        if self.process_running(self.assistant_process):
            print("JARVIS assistant is already running.")
            return True

        print("Starting JARVIS assistant...")
        self.assistant_process = subprocess.Popen(
            [MAIN_PYTHON, ASSISTANT_SCRIPT],
            cwd=PROJECT_ROOT,
            creationflags=CREATE_NEW_CONSOLE,
        )

        time.sleep(2)

        if self.assistant_process.poll() is not None:
            print("JARVIS assistant failed to start.")
            return False

        print("JARVIS assistant started.")
        return True

    # --------------------------------------------------
    # START WEB UI SERVER
    # --------------------------------------------------

    def start_ui(self):
        if self.ui_is_healthy():
            print("Web UI server is already online.")
            return True

        if self.process_running(self.ui_process):
            print("Web UI server is already starting.")
            return True

        if not os.path.exists(UI_SERVER_SCRIPT):
            print(f"Web UI server script not found: {UI_SERVER_SCRIPT}")
            return False

        print("Starting JARVIS Web UI server...")
        self.ui_process = subprocess.Popen(
            [MAIN_PYTHON, UI_SERVER_SCRIPT],
            cwd=PROJECT_ROOT,
            creationflags=CREATE_NEW_CONSOLE,
        )

        # Give it 5 s to start up
        for _ in range(10):
            time.sleep(0.5)
            if self.ui_is_healthy():
                print(f"Web UI is online at {UI_URL}")
                return True
            if self.ui_process.poll() is not None:
                print("Web UI server exited unexpectedly.")
                return False

        print("Web UI started (may still be warming up).")
        return True

    # --------------------------------------------------
    # START DESKTOP GUI
    # --------------------------------------------------

    def start_desktop(self):
        """Launch the PyQt5 Iron Man-style desktop GUI."""
        if self.process_running(self.desktop_process):
            print("Desktop GUI is already running.")
            return True

        if not os.path.exists(DESKTOP_GUI_SCRIPT):
            print(f"Desktop GUI script not found: {DESKTOP_GUI_SCRIPT}")
            return False

        print("Launching JARVIS Desktop GUI...")
        self.desktop_process = subprocess.Popen(
            [MAIN_PYTHON, DESKTOP_GUI_SCRIPT],
            cwd=PROJECT_ROOT,
            creationflags=CREATE_NEW_CONSOLE,
        )

        time.sleep(1)

        if self.desktop_process.poll() is not None:
            print("Desktop GUI exited unexpectedly.")
            return False

        print("Desktop GUI launched.")
        return True

    # --------------------------------------------------
    # START CONTROL PANEL
    # --------------------------------------------------

    def start_control_panel(self):
        """Launch the PyQt5 Control Panel (Auth + Commands + Training + Devices)."""
        if self.process_running(self.control_panel_process):
            print("Control Panel is already running.")
            return True

        if not os.path.exists(CONTROL_PANEL_SCRIPT):
            print(f"Control Panel script not found: {CONTROL_PANEL_SCRIPT}")
            return False

        print("Launching JARVIS Control Panel...")
        self.control_panel_process = subprocess.Popen(
            [MAIN_PYTHON, CONTROL_PANEL_SCRIPT],
            cwd=PROJECT_ROOT,
            creationflags=CREATE_NEW_CONSOLE,
        )

        time.sleep(1)

        if self.control_panel_process.poll() is not None:
            print("Control Panel exited unexpectedly.")
            return False

        print("Control Panel launched.")
        return True

    # --------------------------------------------------
    # START COMPLETE JARVIS SYSTEM
    # --------------------------------------------------

    def start_jarvis(self):
        with self.lock:
            if self.process_running(self.assistant_process):
                print("JARVIS is already running.")
                return

            if not self.start_tts():
                return

            self.start_assistant()
            self.start_ui()

    # --------------------------------------------------
    # STOP PROCESS TREE
    # --------------------------------------------------

    def stop_process(self, process, name):
        if not self.process_running(process):
            return
        print(f"Stopping {name}...")
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        except Exception as error:
            print(f"Could not stop {name}: {error}")

    # --------------------------------------------------
    # STOP COMPLETE JARVIS SYSTEM
    # --------------------------------------------------

    def stop_jarvis(self):
        with self.lock:
            self.stop_process(self.assistant_process,     "JARVIS assistant")
            self.stop_process(self.desktop_process,       "JARVIS Desktop GUI")
            self.stop_process(self.control_panel_process, "JARVIS Control Panel")
            self.stop_process(self.ui_process,            "JARVIS Web UI")
            self.stop_process(self.tts_process,           "JARVIS TTS server")

            self.assistant_process     = None
            self.desktop_process       = None
            self.control_panel_process = None
            self.ui_process            = None
            self.tts_process           = None

            print("JARVIS stopped.")

    # --------------------------------------------------
    # RESTART COMPLETE JARVIS SYSTEM
    # --------------------------------------------------

    def restart_jarvis(self):
        self.stop_jarvis()
        time.sleep(2)
        self.start_jarvis()

    # --------------------------------------------------
    # SYSTEM TRAY MENU ACTIONS
    # --------------------------------------------------

    def start_from_menu(self, icon, item):
        threading.Thread(
            target=self.start_jarvis,
            daemon=True,
        ).start()

    def stop_from_menu(self, icon, item):
        threading.Thread(
            target=self.stop_jarvis,
            daemon=True,
        ).start()

    def restart_from_menu(self, icon, item):
        threading.Thread(
            target=self.restart_jarvis,
            daemon=True,
        ).start()

    def launch_desktop_from_menu(self, icon, item):
        """Launch the PyQt5 desktop GUI."""
        threading.Thread(
            target=self.start_desktop,
            daemon=True,
        ).start()

    def launch_control_panel_from_menu(self, icon, item):
        """Launch the JARVIS Control Panel."""
        threading.Thread(
            target=self.start_control_panel,
            daemon=True,
        ).start()

    def open_ui_from_menu(self, icon, item):
        """Start UI server if not running, then open browser."""
        def _open():
            if not self.ui_is_healthy():
                self.start_ui()
            webbrowser.open(UI_URL)

        threading.Thread(target=_open, daemon=True).start()

    def exit_from_menu(self, icon, item):
        threading.Thread(
            target=self.shutdown_controller,
            daemon=True,
        ).start()

    # --------------------------------------------------
    # EXIT CONTROLLER
    # --------------------------------------------------

    def shutdown_controller(self):
        self.stop_jarvis()
        self.icon.stop()

    # --------------------------------------------------
    # RUN CONTROLLER
    # --------------------------------------------------

    def run(self):
        print("=" * 50)
        print("JARVIS CONTROLLER")
        print("=" * 50)
        print()
        print("Controller started.")
        print("Look for the JARVIS icon in the system tray.")
        print(f"Web UI will be available at {UI_URL}")
        print("Right-click tray -> Launch Desktop GUI for Iron Man UI")

        # Automatically start JARVIS.
        threading.Thread(
            target=self.start_jarvis,
            daemon=True,
        ).start()

        # Run system tray icon (blocks main thread on Windows).
        self.icon.run()


if __name__ == "__main__":
    controller = JarvisController()
    controller.run()