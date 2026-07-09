"""
JARVIS Control Panel
====================
PyQt5 desktop control panel for managing the JARVIS assistant.

Features:
  Tab 1 — Authentication : Sign in to Alexa, Google Home, Supabase
  Tab 2 — Command Console: Send commands, view history
  Tab 3 — Training       : Add/edit/delete custom trained commands (Supabase)
  Tab 4 — Devices        : List + test Alexa / Google Home devices

Run:
    .venv\\Scripts\\python.exe ui\\controlpanel.py
"""

import os
import sys
import threading

# ── path setup ───────────────────────────────────────────────────────────────
_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_ASSISTANT    = os.path.join(_PROJECT_ROOT, "assistant")
for _p in (_PROJECT_ROOT, _ASSISTANT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

ENV_PATH = os.path.join(_PROJECT_ROOT, ".env")

# ── Qt ────────────────────────────────────────────────────────────────────────
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QSplitter, QFrame, QScrollArea, QSizePolicy, QAbstractItemView,
    QMessageBox, QGraphicsDropShadowEffect, QStatusBar,
)
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize


# ─────────────────────────────────────────────────────────────────────────────
# SHARED STYLE
# ─────────────────────────────────────────────────────────────────────────────

DARK    = "#020b14"
PANEL   = "#041825"
BORDER  = "rgba(0,229,255,0.18)"
CYAN    = "#00e5ff"
GREEN   = "#00e676"
RED     = "#ff3d5a"
YELLOW  = "#ffea00"
TEXT    = "#cde8f5"
MUTED   = "#5c8fa5"

STYLE_BASE = f"""
QWidget {{ background: {DARK}; color: {TEXT}; font-family: 'Segoe UI', Consolas, sans-serif; font-size: 12px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; background: {PANEL}; }}
QTabBar::tab {{
    background: {DARK}; color: {MUTED}; padding: 8px 18px;
    border: 1px solid {BORDER}; border-bottom: none; border-radius: 6px 6px 0 0;
    font-family: Consolas; letter-spacing: 1px; font-size: 11px;
}}
QTabBar::tab:selected {{ background: {PANEL}; color: {CYAN}; border-bottom: 2px solid {CYAN}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QLineEdit, QTextEdit, QComboBox {{
    background: {DARK}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 12px;
    font-size: 12px;
}}
QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {CYAN}; }}
QComboBox::drop-down {{ border: none; padding-right: 8px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER}; }}

QTableWidget {{
    background: {DARK}; color: {TEXT}; gridline-color: {BORDER};
    border: 1px solid {BORDER}; border-radius: 6px;
}}
QTableWidget::item {{ padding: 6px 10px; }}
QTableWidget::item:selected {{ background: rgba(0,229,255,0.12); color: {TEXT}; }}
QHeaderView::section {{
    background: {PANEL}; color: {CYAN}; padding: 8px 10px;
    border: none; border-bottom: 1px solid {BORDER};
    font-family: Consolas; font-size: 10px; letter-spacing: 1px;
}}

QScrollBar:vertical {{ width: 4px; background: {DARK}; }}
QScrollBar::handle:vertical {{ background: rgba(0,229,255,0.25); border-radius: 2px; }}
QScrollBar:horizontal {{ height: 4px; background: {DARK}; }}
QScrollBar::handle:horizontal {{ background: rgba(0,229,255,0.25); border-radius: 2px; }}

QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; font-size: 10px; }}
"""

def btn(label: str, color: str = CYAN, width: int = None) -> QPushButton:
    b = QPushButton(label)
    if width:
        b.setFixedWidth(width)
    b.setFixedHeight(36)
    b.setStyleSheet(f"""
        QPushButton {{
            background: rgba(0,229,255,0.08); color: {color};
            border: 1px solid {color}; border-radius: 8px;
            padding: 0 14px; font-family: Consolas; font-size: 11px; letter-spacing: 1px;
        }}
        QPushButton:hover {{ background: rgba(0,229,255,0.18); }}
        QPushButton:pressed {{ background: rgba(0,229,255,0.08); }}
        QPushButton:disabled {{ opacity: 0.4; }}
    """)
    return b

def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {CYAN}; font-family: Consolas; font-size: 10px; "
        f"letter-spacing: 2px; padding: 4px 0; border-bottom: 1px solid {BORDER};"
    )
    return lbl

def field(placeholder: str = "", password: bool = False) -> QLineEdit:
    f = QLineEdit()
    f.setPlaceholderText(placeholder)
    if password:
        f.setEchoMode(QLineEdit.Password)
    return f

def status_dot(ok: bool) -> QLabel:
    lbl = QLabel("● CONNECTED" if ok else "○ NOT CONNECTED")
    lbl.setStyleSheet(f"color: {GREEN if ok else RED}; font-family: Consolas; font-size: 10px;")
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
# ENV MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class EnvManager:
    """Read and write .env file key-value pairs."""

    @staticmethod
    def read() -> dict[str, str]:
        env = {}
        if not os.path.exists(ENV_PATH):
            return env
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
        return env

    @staticmethod
    def write(updates: dict[str, str]):
        """Update/add keys in .env, preserve comments."""
        env = EnvManager.read()
        env.update(updates)

        lines = []
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

        written = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                new_lines.append(line)
                continue
            if "=" in stripped:
                k = stripped.split("=")[0].strip()
                if k in updates:
                    new_lines.append(f"{k}={updates[k]}\n")
                    written.add(k)
                    continue
            new_lines.append(line)

        # Add any new keys not already in file
        for k, v in updates.items():
            if k not in written:
                new_lines.append(f"{k}={v}\n")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    @staticmethod
    def get(key: str, default: str = "") -> str:
        return EnvManager.read().get(key, default)


# ─────────────────────────────────────────────────────────────────────────────
# WORKER THREADS
# ─────────────────────────────────────────────────────────────────────────────

class TestAlexaWorker(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, email, password, region):
        super().__init__()
        self.email = email; self.password = password; self.region = region

    def run(self):
        try:
            from alexapy import AlexaLogin
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            login = AlexaLogin(
                url=f"https://www.{self.region}",
                email=self.email, password=self.password,
                outputfiles_path=os.path.join(_ASSISTANT, ".alexa_cache"),
                debug=False,
            )
            loop.run_until_complete(login.login())
            if login.status.get("login_successful"):
                self.result.emit(True, "Alexa connected successfully.")
            else:
                self.result.emit(False, f"Login failed: {login.status}")
        except Exception as e:
            self.result.emit(False, str(e))


class TestGoogleWorker(QThread):
    result = pyqtSignal(bool, str, list)

    def __init__(self, email, password):
        super().__init__()
        self.email = email; self.password = password

    def run(self):
        try:
            from glocaltokens.client import GLocalAuthenticationTokens
            client = GLocalAuthenticationTokens(
                username=self.email, password=self.password
            )
            devices = client.get_google_devices_json() or []
            names = [d.get("device_name", "?") for d in devices]
            self.result.emit(True, f"Found {len(devices)} Google Home device(s).", names)
        except Exception as e:
            self.result.emit(False, str(e), [])


class TestSupabaseWorker(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, url, key):
        super().__init__()
        self.url = url; self.key = key

    def run(self):
        try:
            from supabase import create_client
            client = create_client(self.url, self.key)
            client.table("jarvis_memory").select("id").limit(1).execute()
            self.result.emit(True, "Supabase connected.")
        except Exception as e:
            self.result.emit(False, str(e))


class RouterWorker(QThread):
    reply = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            from brain import JarvisBrain
            from router import JarvisRouter
            brain  = JarvisBrain()
            router = JarvisRouter(brain=brain)
            ans    = router.route(self.text)
            self.reply.emit(ans or "(no response)")
        except Exception as e:
            self.reply.emit(f"Error: {e}")


class ListAlexaDevicesWorker(QThread):
    result = pyqtSignal(list)

    def __init__(self, email, password, region):
        super().__init__()
        self.email = email; self.password = password; self.region = region

    def run(self):
        try:
            from alexapy import AlexaLogin, AlexaAPI
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            login = AlexaLogin(
                url=f"https://www.{self.region}",
                email=self.email, password=self.password,
                outputfiles_path=os.path.join(_ASSISTANT, ".alexa_cache"),
                debug=False,
            )
            loop.run_until_complete(login.login())
            devices = loop.run_until_complete(AlexaAPI.get_devices(login)) or []
            smart   = loop.run_until_complete(AlexaAPI.get_smart_home_entities(login)) or []
            result  = [{"name": d.get("accountName", "?"), "type": "Echo", "serial": d.get("serialNumber")} for d in devices]
            result += [{"name": s.get("name", "?"), "type": "Smart Home", "serial": s.get("entityId")} for s in smart]
            self.result.emit(result)
        except Exception as e:
            self.result.emit([{"name": f"Error: {e}", "type": "-", "serial": ""}])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

class AuthTab(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._workers = []
        env = EnvManager.read()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        layout.addWidget(section_label("AMAZON ALEXA"))
        alexa_grid = QGridLayout()
        alexa_grid.setSpacing(10)

        self.alexa_email    = field("your@gmail.com")
        self.alexa_password = field("Amazon password", password=True)
        self.alexa_region   = QComboBox()
        self.alexa_region.addItems(["amazon.in", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.co.jp"])
        self.alexa_status   = QLabel("○ NOT TESTED")
        self.alexa_status.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 10px;")

        self.alexa_email.setText(env.get("AMAZON_EMAIL", ""))
        self.alexa_password.setText(env.get("AMAZON_PASSWORD", ""))
        idx = self.alexa_region.findText(env.get("ALEXA_REGION", "amazon.in"))
        if idx >= 0: self.alexa_region.setCurrentIndex(idx)

        alexa_grid.addWidget(QLabel("Email"),    0, 0)
        alexa_grid.addWidget(self.alexa_email,   0, 1)
        alexa_grid.addWidget(QLabel("Password"), 1, 0)
        alexa_grid.addWidget(self.alexa_password,1, 1)
        alexa_grid.addWidget(QLabel("Region"),   2, 0)
        alexa_grid.addWidget(self.alexa_region,  2, 1)

        alexa_btn_row = QHBoxLayout()
        self.alexa_test_btn = btn("Test Connection", CYAN, 160)
        self.alexa_save_btn = btn("Save to .env",    GREEN, 130)
        self.alexa_test_btn.clicked.connect(self._test_alexa)
        self.alexa_save_btn.clicked.connect(self._save_alexa)
        alexa_btn_row.addWidget(self.alexa_test_btn)
        alexa_btn_row.addWidget(self.alexa_save_btn)
        alexa_btn_row.addWidget(self.alexa_status)
        alexa_btn_row.addStretch()

        alexa_frame = QFrame()
        alexa_frame.setStyleSheet(f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 10px; }}")
        al = QVBoxLayout(alexa_frame)
        al.addLayout(alexa_grid)
        al.addLayout(alexa_btn_row)
        layout.addWidget(alexa_frame)

        # ── Google Home ───────────────────────────────────────────────────────
        layout.addWidget(section_label("GOOGLE HOME"))
        google_grid = QGridLayout(); google_grid.setSpacing(10)

        self.gh_email    = field("your@gmail.com")
        self.gh_password = field("Google App Password", password=True)
        self.gh_status   = QLabel("○ NOT TESTED")
        self.gh_status.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 10px;")

        self.gh_email.setText(env.get("GOOGLE_HOME_EMAIL", ""))
        self.gh_password.setText(env.get("GOOGLE_HOME_PASSWORD", ""))

        google_grid.addWidget(QLabel("Gmail"),        0, 0)
        google_grid.addWidget(self.gh_email,          0, 1)
        google_grid.addWidget(QLabel("App Password"), 1, 0)
        google_grid.addWidget(self.gh_password,       1, 1)

        gh_hint = QLabel(
            "ℹ️  Use a Google <b>App Password</b> (not your main password). "
            "Generate at <u>myaccount.google.com/apppasswords</u>"
        )
        gh_hint.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        gh_hint.setOpenExternalLinks(True)

        gh_btn_row = QHBoxLayout()
        self.gh_test_btn = btn("Test Connection", CYAN, 160)
        self.gh_save_btn = btn("Save to .env",    GREEN, 130)
        self.gh_test_btn.clicked.connect(self._test_google)
        self.gh_save_btn.clicked.connect(self._save_google)
        gh_btn_row.addWidget(self.gh_test_btn)
        gh_btn_row.addWidget(self.gh_save_btn)
        gh_btn_row.addWidget(self.gh_status)
        gh_btn_row.addStretch()

        gh_frame = QFrame()
        gh_frame.setStyleSheet(f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 10px; }}")
        gl = QVBoxLayout(gh_frame)
        gl.addLayout(google_grid)
        gl.addWidget(gh_hint)
        gl.addLayout(gh_btn_row)
        layout.addWidget(gh_frame)

        # ── Supabase ──────────────────────────────────────────────────────────
        layout.addWidget(section_label("SUPABASE  (memory + training)"))
        sb_grid = QGridLayout(); sb_grid.setSpacing(10)

        self.sb_url    = field("https://your-project.supabase.co")
        self.sb_key    = field("anon public key", password=True)
        self.sb_status = QLabel("○ NOT TESTED")
        self.sb_status.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 10px;")

        self.sb_url.setText(env.get("SUPABASE_URL", ""))
        self.sb_key.setText(env.get("SUPABASE_ANON_KEY", ""))

        sb_grid.addWidget(QLabel("Project URL"), 0, 0)
        sb_grid.addWidget(self.sb_url,           0, 1)
        sb_grid.addWidget(QLabel("Anon Key"),    1, 0)
        sb_grid.addWidget(self.sb_key,           1, 1)

        sb_sql_hint = QLabel(
            "ℹ️  Run the SQL below once in your Supabase dashboard to create the training table:\n"
            "CREATE TABLE IF NOT EXISTS jarvis_training (\n"
            "  id BIGSERIAL PRIMARY KEY, trigger TEXT NOT NULL,\n"
            "  response TEXT NOT NULL, category TEXT DEFAULT 'general',\n"
            "  enabled BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW()\n);"
        )
        sb_sql_hint.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 9px;")

        sb_btn_row = QHBoxLayout()
        self.sb_test_btn = btn("Test Connection", CYAN, 160)
        self.sb_save_btn = btn("Save to .env",    GREEN, 130)
        self.sb_test_btn.clicked.connect(self._test_supabase)
        self.sb_save_btn.clicked.connect(self._save_supabase)
        sb_btn_row.addWidget(self.sb_test_btn)
        sb_btn_row.addWidget(self.sb_save_btn)
        sb_btn_row.addWidget(self.sb_status)
        sb_btn_row.addStretch()

        sb_frame = QFrame()
        sb_frame.setStyleSheet(f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 10px; }}")
        sl = QVBoxLayout(sb_frame)
        sl.addLayout(sb_grid)
        sl.addWidget(sb_sql_hint)
        sl.addLayout(sb_btn_row)
        layout.addWidget(sb_frame)

        layout.addStretch()

    # ── actions ───────────────────────────────────────────────────────────────

    def _test_alexa(self):
        self.alexa_status.setText("⟳ Connecting…")
        self.alexa_status.setStyleSheet(f"color: {YELLOW}; font-family: Consolas; font-size: 10px;")
        self.alexa_test_btn.setEnabled(False)
        w = TestAlexaWorker(
            self.alexa_email.text(), self.alexa_password.text(),
            self.alexa_region.currentText()
        )
        w.result.connect(self._on_alexa_result)
        w.start(); self._workers.append(w)

    def _on_alexa_result(self, ok: bool, msg: str):
        self.alexa_test_btn.setEnabled(True)
        self.alexa_status.setText(f"{'●' if ok else '○'} {msg[:50]}")
        self.alexa_status.setStyleSheet(f"color: {GREEN if ok else RED}; font-family: Consolas; font-size: 10px;")
        self.status_msg.emit(msg)

    def _save_alexa(self):
        EnvManager.write({
            "AMAZON_EMAIL":    self.alexa_email.text(),
            "AMAZON_PASSWORD": self.alexa_password.text(),
            "ALEXA_REGION":    self.alexa_region.currentText(),
        })
        self.status_msg.emit("Alexa credentials saved to .env")

    def _test_google(self):
        self.gh_status.setText("⟳ Connecting…")
        self.gh_status.setStyleSheet(f"color: {YELLOW}; font-family: Consolas; font-size: 10px;")
        self.gh_test_btn.setEnabled(False)
        w = TestGoogleWorker(self.gh_email.text(), self.gh_password.text())
        w.result.connect(self._on_google_result)
        w.start(); self._workers.append(w)

    def _on_google_result(self, ok: bool, msg: str, devices: list):
        self.gh_test_btn.setEnabled(True)
        self.gh_status.setText(f"{'●' if ok else '○'} {msg[:60]}")
        self.gh_status.setStyleSheet(f"color: {GREEN if ok else RED}; font-family: Consolas; font-size: 10px;")
        self.status_msg.emit(msg)

    def _save_google(self):
        EnvManager.write({
            "GOOGLE_HOME_EMAIL":    self.gh_email.text(),
            "GOOGLE_HOME_PASSWORD": self.gh_password.text(),
        })
        self.status_msg.emit("Google Home credentials saved to .env")

    def _test_supabase(self):
        self.sb_status.setText("⟳ Connecting…")
        self.sb_status.setStyleSheet(f"color: {YELLOW}; font-family: Consolas; font-size: 10px;")
        self.sb_test_btn.setEnabled(False)
        w = TestSupabaseWorker(self.sb_url.text(), self.sb_key.text())
        w.result.connect(self._on_supabase_result)
        w.start(); self._workers.append(w)

    def _on_supabase_result(self, ok: bool, msg: str):
        self.sb_test_btn.setEnabled(True)
        self.sb_status.setText(f"{'●' if ok else '○'} {msg[:60]}")
        self.sb_status.setStyleSheet(f"color: {GREEN if ok else RED}; font-family: Consolas; font-size: 10px;")
        self.status_msg.emit(msg)

    def _save_supabase(self):
        EnvManager.write({
            "SUPABASE_URL":      self.sb_url.text(),
            "SUPABASE_ANON_KEY": self.sb_key.text(),
        })
        self.status_msg.emit("Supabase credentials saved to .env")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: COMMAND CONSOLE
# ─────────────────────────────────────────────────────────────────────────────

class CommandTab(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._workers = []
        self._router  = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(section_label("COMMAND CONSOLE — Send commands to JARVIS"))

        # Chat display
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet(
            f"background: {DARK}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; padding: 10px; font-family: Consolas; font-size: 12px;"
        )
        self.chat.setPlaceholderText("JARVIS responses will appear here…")
        layout.addWidget(self.chat, 1)

        # Input
        input_row = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText(
            'Type a command… e.g. "Turn on living room lights" or "What time is it"'
        )
        self.cmd_input.returnPressed.connect(self._send)

        self.send_btn = btn("SEND", CYAN, 90)
        self.send_btn.clicked.connect(self._send)

        self.clear_btn = btn("CLEAR", MUTED, 80)
        self.clear_btn.clicked.connect(self.chat.clear)

        input_row.addWidget(self.cmd_input)
        input_row.addWidget(self.send_btn)
        input_row.addWidget(self.clear_btn)
        layout.addLayout(input_row)

        # Quick test buttons
        layout.addWidget(section_label("QUICK TEST"))
        quick_row = QHBoxLayout()
        quick_cmds = [
            "What time is it",
            "System status",
            "Turn on lights",
            "Turn off all lights",
            "Lock front door",
        ]
        for cmd in quick_cmds:
            b = btn(cmd, MUTED)
            b.setFixedHeight(30)
            b.clicked.connect(lambda _, c=cmd: self._quick(c))
            quick_row.addWidget(b)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        self._log("JARVIS", "Control panel connected. Type a command to test.")

    def _log(self, role: str, text: str):
        color = CYAN if role == "JARVIS" else "#90caf9"
        self.chat.append(
            f'<span style="color:{MUTED};">[{role}]</span> '
            f'<span style="color:{color};">{text}</span><br>'
        )

    def _quick(self, cmd: str):
        self.cmd_input.setText(cmd)
        self._send()

    def _send(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        self.cmd_input.clear()
        self._log("YOU", text)
        self.send_btn.setEnabled(False)
        self.status_msg.emit("Processing…")

        w = RouterWorker(text)
        w.reply.connect(self._on_reply)
        w.start()
        self._workers.append(w)

    def _on_reply(self, answer: str):
        self._log("JARVIS", answer)
        self.send_btn.setEnabled(True)
        self.status_msg.emit("Ready")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: TRAINING
# ─────────────────────────────────────────────────────────────────────────────

class TrainingTab(QWidget):
    status_msg = pyqtSignal(str)

    CATEGORIES = ["general", "smart_home", "personal", "work", "entertainment", "custom"]

    def __init__(self):
        super().__init__()
        self._trainer = None
        self._init_trainer()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(section_label("TRAIN JARVIS — Add custom command → response pairs"))

        # ── Add new command ───────────────────────────────────────────────────
        add_frame = QFrame()
        add_frame.setStyleSheet(
            f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}"
        )
        add_layout = QGridLayout(add_frame)
        add_layout.setContentsMargins(16, 14, 16, 14)
        add_layout.setSpacing(10)

        add_layout.addWidget(QLabel("Trigger phrase:"), 0, 0)
        self.trig_input = field('e.g. "goodnight" or "good night jarvis"')
        add_layout.addWidget(self.trig_input, 0, 1, 1, 2)

        add_layout.addWidget(QLabel("Response:"), 1, 0)
        self.resp_input = QTextEdit()
        self.resp_input.setFixedHeight(65)
        self.resp_input.setPlaceholderText(
            'e.g. "Goodnight, sir. Turning off all lights and locking the front door."'
        )
        self.resp_input.setStyleSheet(
            f"background: {DARK}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px;"
        )
        add_layout.addWidget(self.resp_input, 1, 1, 1, 2)

        add_layout.addWidget(QLabel("Category:"), 2, 0)
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(self.CATEGORIES)
        self.cat_combo.setEditable(True)
        add_layout.addWidget(self.cat_combo, 2, 1)

        self.add_btn = btn("➕  ADD COMMAND", GREEN, 170)
        self.add_btn.clicked.connect(self._add_command)
        add_layout.addWidget(self.add_btn, 2, 2)

        layout.addWidget(add_frame)

        # ── Commands table ────────────────────────────────────────────────────
        layout.addWidget(section_label("TRAINED COMMANDS"))

        # Filter row
        filter_row = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter commands…")
        self.filter_input.textChanged.connect(self._filter)
        refresh_btn = btn("↻ Refresh", MUTED, 90)
        refresh_btn.clicked.connect(self._load_commands)
        filter_row.addWidget(self.filter_input)
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "TRIGGER", "RESPONSE", "CATEGORY", "ACTIONS"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            self.table.styleSheet() +
            f"QTableWidget {{ alternate-background-color: rgba(0,229,255,0.03); }}"
        )
        layout.addWidget(self.table, 1)

        self._all_commands = []
        self._load_commands()

    def _init_trainer(self):
        try:
            from trainer import JarvisTrainer
            self._trainer = JarvisTrainer()
        except Exception as e:
            self._trainer = None

    def _load_commands(self):
        if not self._trainer or not self._trainer.available:
            self.status_msg.emit("Supabase not configured — add credentials in Authentication tab.")
            return
        cmds = self._trainer.get_commands()
        self._all_commands = cmds
        self._render_commands(cmds)
        self.status_msg.emit(f"Loaded {len(cmds)} trained command(s).")

    def _render_commands(self, cmds: list):
        self.table.setRowCount(0)
        for cmd in cmds:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(str(cmd.get("id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(cmd.get("trigger", "")))
            self.table.setItem(row, 2, QTableWidgetItem(cmd.get("response", "")))
            self.table.setItem(row, 3, QTableWidgetItem(cmd.get("category", "general")))

            # Actions cell
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(4, 2, 4, 2)
            cell_layout.setSpacing(6)

            enabled = cmd.get("enabled", True)
            toggle_btn = btn("Disable" if enabled else "Enable", YELLOW, 70)
            toggle_btn.setFixedHeight(26)
            cid = cmd.get("id")
            toggle_btn.clicked.connect(lambda _, c=cid, e=enabled, b=toggle_btn: self._toggle(c, e, b))

            del_btn = btn("Delete", RED, 60)
            del_btn.setFixedHeight(26)
            del_btn.clicked.connect(lambda _, c=cid, r=row: self._delete(c))

            cell_layout.addWidget(toggle_btn)
            cell_layout.addWidget(del_btn)
            self.table.setCellWidget(row, 4, cell_widget)

            if not enabled:
                for col in range(4):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QColor(MUTED))

        self.table.resizeRowsToContents()

    def _filter(self, text: str):
        text = text.lower()
        filtered = [
            c for c in self._all_commands
            if text in c.get("trigger", "").lower()
            or text in c.get("response", "").lower()
            or text in c.get("category", "").lower()
        ] if text else self._all_commands
        self._render_commands(filtered)

    def _add_command(self):
        trigger  = self.trig_input.text().strip()
        response = self.resp_input.toPlainText().strip()
        category = self.cat_combo.currentText().strip() or "general"

        if not trigger or not response:
            self.status_msg.emit("Both trigger and response are required.")
            return

        if not self._trainer or not self._trainer.available:
            self.status_msg.emit("Supabase not configured — cannot save training data.")
            return

        self.add_btn.setEnabled(False)
        result = self._trainer.add_command(trigger, response, category)

        if result.get("success"):
            self.trig_input.clear()
            self.resp_input.clear()
            self.status_msg.emit(f"Command added: '{trigger}'")
            self._load_commands()
        else:
            self.status_msg.emit(f"Error: {result.get('error')}")

        self.add_btn.setEnabled(True)

    def _toggle(self, cid: int, currently_enabled: bool, btn_ref: QPushButton):
        if not self._trainer:
            return
        new_state = not currently_enabled
        ok = self._trainer.toggle_command(cid, new_state)
        if ok:
            self.status_msg.emit(f"Command {'enabled' if new_state else 'disabled'}.")
            self._load_commands()

    def _delete(self, cid: int):
        if not self._trainer:
            return
        reply = QMessageBox.question(
            self, "Delete Command",
            "Are you sure you want to delete this trained command?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok = self._trainer.delete_command(cid)
            if ok:
                self.status_msg.emit("Command deleted.")
                self._load_commands()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: DEVICES
# ─────────────────────────────────────────────────────────────────────────────

class DevicesTab(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._workers = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(section_label("SMART DEVICES — Discover and test your devices"))

        top_row = QHBoxLayout()
        self.refresh_btn = btn("↻  Scan Alexa Devices", CYAN, 200)
        self.refresh_btn.clicked.connect(self._scan_alexa)
        top_row.addWidget(self.refresh_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        # Devices table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["DEVICE NAME", "TYPE", "SERIAL / ID", "TEST"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        # Quick command
        layout.addWidget(section_label("QUICK DEVICE COMMAND"))
        cmd_row = QHBoxLayout()
        self.dev_input = QLineEdit()
        self.dev_input.setPlaceholderText('e.g. "Turn on living room lights" or "Set bedroom fan to 50 percent"')
        self.dev_input.returnPressed.connect(self._send_device_cmd)
        self.dev_send = btn("SEND", CYAN, 90)
        self.dev_send.clicked.connect(self._send_device_cmd)
        cmd_row.addWidget(self.dev_input)
        cmd_row.addWidget(self.dev_send)
        layout.addLayout(cmd_row)

        self.dev_response = QTextEdit()
        self.dev_response.setReadOnly(True)
        self.dev_response.setFixedHeight(80)
        self.dev_response.setStyleSheet(
            f"background: {DARK}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(self.dev_response)

    def _scan_alexa(self):
        env = EnvManager.read()
        email    = env.get("AMAZON_EMAIL", "")
        password = env.get("AMAZON_PASSWORD", "")
        region   = env.get("ALEXA_REGION", "amazon.in")

        if not email or not password:
            self.status_msg.emit("Set Alexa credentials in Authentication tab first.")
            return

        self.refresh_btn.setEnabled(False)
        self.status_msg.emit("Scanning Alexa devices…")
        w = ListAlexaDevicesWorker(email, password, region)
        w.result.connect(self._on_devices)
        w.start(); self._workers.append(w)

    def _on_devices(self, devices: list):
        self.refresh_btn.setEnabled(True)
        self.table.setRowCount(0)

        for dev in devices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(dev.get("name", "?")))
            self.table.setItem(row, 1, QTableWidgetItem(dev.get("type", "?")))
            self.table.setItem(row, 2, QTableWidgetItem(str(dev.get("serial", ""))))

            name = dev.get("name", "")
            cell = QWidget()
            cl   = QHBoxLayout(cell)
            cl.setContentsMargins(4, 2, 4, 2)
            on_btn  = btn("ON",  GREEN, 44); on_btn.setFixedHeight(24)
            off_btn = btn("OFF", RED,   44); off_btn.setFixedHeight(24)
            on_btn.clicked.connect(lambda _, n=name: self._quick_cmd(f"turn on {n}"))
            off_btn.clicked.connect(lambda _, n=name: self._quick_cmd(f"turn off {n}"))
            cl.addWidget(on_btn); cl.addWidget(off_btn)
            self.table.setCellWidget(row, 3, cell)

        self.table.resizeRowsToContents()
        self.status_msg.emit(f"Found {len(devices)} device(s).")

    def _quick_cmd(self, cmd: str):
        self.dev_input.setText(cmd)
        self._send_device_cmd()

    def _send_device_cmd(self):
        text = self.dev_input.text().strip()
        if not text:
            return
        self.dev_send.setEnabled(False)
        self.dev_response.setPlainText("Processing…")
        w = RouterWorker(text)
        w.reply.connect(lambda ans: (
            self.dev_response.setPlainText(ans),
            self.dev_send.__setattr__("enabled", True),
        ))
        w.start(); self._workers.append(w)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — Control Panel")
        self.resize(1000, 740)
        self.setMinimumSize(860, 600)
        self.setStyleSheet(STYLE_BASE)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

        # Header
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            f"QFrame {{ background: {PANEL}; border-bottom: 1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        title = QLabel("J.A.R.V.I.S  CONTROL PANEL")
        title.setFont(QFont("Consolas", 14, QFont.Bold))
        title.setStyleSheet(f"color: {CYAN}; letter-spacing: 4px;")

        version = QLabel("v2.0  ·  qwen3:4b  ·  LuxTTS")
        version.setStyleSheet(f"color: {MUTED}; font-size: 10px;")

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(version)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        self.auth_tab  = AuthTab()
        self.cmd_tab   = CommandTab()
        self.train_tab = TrainingTab()
        self.dev_tab   = DevicesTab()

        self.tabs.addTab(self.auth_tab,  "🔐  AUTHENTICATION")
        self.tabs.addTab(self.cmd_tab,   "⚡  COMMAND CONSOLE")
        self.tabs.addTab(self.train_tab, "🧠  TRAINING")
        self.tabs.addTab(self.dev_tab,   "📡  DEVICES")

        # Wire status signals
        for tab in (self.auth_tab, self.cmd_tab, self.train_tab, self.dev_tab):
            tab.status_msg.connect(self.status.showMessage)

        # Central
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(header)
        cl.addWidget(self.tabs)
        self.setCentralWidget(central)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(DARK))
    palette.setColor(QPalette.WindowText,      QColor(TEXT))
    palette.setColor(QPalette.Base,            QColor(PANEL))
    palette.setColor(QPalette.Text,            QColor(TEXT))
    palette.setColor(QPalette.Button,          QColor(PANEL))
    palette.setColor(QPalette.ButtonText,      QColor(TEXT))
    palette.setColor(QPalette.Highlight,       QColor("#006064"))
    palette.setColor(QPalette.HighlightedText, QColor("#e0f7fa"))
    app.setPalette(palette)

    win = ControlPanel()
    win.show()
    sys.exit(app.exec_())
