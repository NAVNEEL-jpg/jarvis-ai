"""
JARVIS Desktop GUI
==================
Iron Man-style PyQt5 desktop interface for the JARVIS voice assistant.

Inspired by: https://github.com/Hasan-Ikbal/Jarvis_AI_GUI
Backend:     qwen3:4b via Ollama (JarvisRouter / JarvisBrain)
TTS:         JarvisLuxTTS server at port 8765
STT:         faster-whisper (JarvisSTT)

Run:
    .venv\Scripts\python.exe ui\jarvis_desktop.py
"""

import os
import sys
import tempfile
import threading
import time

import numpy as np
import requests

# ── path setup ──────────────────────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_ASSISTANT_DIR = os.path.join(_PROJECT_ROOT, "assistant")

for _p in [_PROJECT_ROOT, _ASSISTANT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# ── Qt ───────────────────────────────────────────────────────────────────────
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QFrame, QSizePolicy, QGraphicsDropShadowEffect,
    QScrollArea,
)
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QLinearGradient, QGradient,
    QPainter, QPen, QBrush, QIcon,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPointF, QRectF, QSize,
    QPropertyAnimation, QEasingCurve,
)

# ── JARVIS backend (lazy-loaded in worker threads) ───────────────────────────
TTS_SPEAK_URL  = "http://127.0.0.1:8765/speak"
TTS_HEALTH_URL = "http://127.0.0.1:8765/health"

SAMPLE_RATE   = 16000   # Hz for STT recording
RECORD_SECS   = 8       # max recording seconds per command
SILENCE_LIMIT = 1.5     # seconds of silence before stopping


# ─────────────────────────────────────────────────────────────────────────────
# ARC REACTOR WIDGET
# ─────────────────────────────────────────────────────────────────────────────
class ArcReactor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self._angle = 0
        self._pulse  = 0.0
        self._pulse_dir = 1

        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick)
        self._spin_timer.start(25)

    def _tick(self):
        self._angle = (self._angle + 2) % 360
        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        alpha_core = int(180 + 75 * self._pulse)

        # outer glow ring
        pen = QPen(QColor(0, 229, 255, 60), 2)
        p.setPen(pen)
        p.drawEllipse(QRectF(4, 4, 172, 172))

        # spinning dashed ring 1
        pen = QPen(QColor(0, 229, 255, 180), 2.5, Qt.DashLine)
        pen.setDashPattern([6, 12])
        p.setPen(pen)
        p.save()
        p.translate(cx, cy)
        p.rotate(self._angle)
        p.drawEllipse(QRectF(-74, -74, 148, 148))
        p.restore()

        # spinning dashed ring 2 (opposite direction)
        pen = QPen(QColor(0, 180, 220, 140), 1.5, Qt.DashLine)
        pen.setDashPattern([4, 20])
        p.setPen(pen)
        p.save()
        p.translate(cx, cy)
        p.rotate(-self._angle * 1.4)
        p.drawEllipse(QRectF(-54, -54, 108, 108))
        p.restore()

        # middle ring (static)
        pen = QPen(QColor(0, 229, 255, 200), 2)
        p.setPen(pen)
        p.drawEllipse(QRectF(34, 34, 112, 112))

        # cross-hair lines
        pen = QPen(QColor(0, 229, 255, 120), 1)
        p.setPen(pen)
        p.drawLine(int(cx), 38, int(cx), 55)
        p.drawLine(int(cx), 125, int(cx), 142)
        p.drawLine(38, int(cy), 55, int(cy))
        p.drawLine(125, int(cy), 142, int(cy))

        # core glow
        core_brush = QBrush(QColor(0, 229, 255, alpha_core))
        p.setBrush(core_brush)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - 16, cy - 16, 32, 32))

        # core white dot
        p.setBrush(QBrush(Qt.white))
        p.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12))

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# WAVEFORM WIDGET
# ─────────────────────────────────────────────────────────────────────────────
class Waveform(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._bars  = [0.0] * 30
        self._active = False
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def set_active(self, val: bool):
        self._active = val

    def _tick(self):
        if self._active:
            new = [abs(np.random.normal(0, 0.5)) for _ in range(30)]
            new = [min(1.0, v) for v in new]
        else:
            new = [max(0.0, v * 0.85) for v in self._bars]
        self._bars = new
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bar_w = w / len(self._bars)
        for i, val in enumerate(self._bars):
            bar_h = max(3, int(val * h * 0.9))
            x = int(i * bar_w + bar_w * 0.15)
            y = (h - bar_h) // 2
            alpha = int(100 + 155 * val)
            p.setBrush(QBrush(QColor(0, 229, 255, alpha)))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, y, max(2, int(bar_w * 0.7)), bar_h, 2, 2)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# WORKER THREADS
# ─────────────────────────────────────────────────────────────────────────────
class RouterWorker(QThread):
    """Runs the JARVIS router in a background thread."""
    reply_ready  = pyqtSignal(str)
    error        = pyqtSignal(str)

    def __init__(self, text, router):
        super().__init__()
        self.text   = text
        self.router = router

    def run(self):
        try:
            answer = self.router.route(self.text)
            self.reply_ready.emit(answer or "")
        except Exception as exc:
            self.error.emit(str(exc))


class TTSWorker(QThread):
    """Sends text to the LuxTTS server in a background thread."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            requests.post(
                TTS_SPEAK_URL,
                json={"text": self.text},
                timeout=120,
            )
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class ListenWorker(QThread):
    """Records from microphone and transcribes via faster-whisper."""
    transcript_ready = pyqtSignal(str)
    error            = pyqtSignal(str)

    def run(self):
        try:
            import sounddevice as sd
            from stt import JarvisSTT

            stt = JarvisSTT(model_size="small.en", device="cpu", compute_type="int8")

            # Record for up to RECORD_SECS seconds, 16 kHz mono
            audio = sd.rec(
                int(RECORD_SECS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
            )
            sd.wait()

            audio = audio.flatten()

            # Write to a temp WAV
            import wave, struct
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()

            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                pcm = (audio * 32767).astype(np.int16)
                wf.writeframes(pcm.tobytes())

            text = stt.transcribe(tmp.name)

            try:
                os.remove(tmp.name)
            except OSError:
                pass

            self.transcript_ready.emit(text or "")

        except Exception as exc:
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# CHAT BUBBLE
# ─────────────────────────────────────────────────────────────────────────────
def make_bubble(role: str, text: str) -> QWidget:
    """Create a styled chat bubble for user or JARVIS."""
    container = QWidget()
    layout    = QHBoxLayout(container)
    layout.setContentsMargins(8, 4, 8, 4)

    bubble = QLabel(text)
    bubble.setWordWrap(True)
    bubble.setMaximumWidth(540)
    bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)

    if role == "user":
        bubble.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0d3b6e, stop:1 #0d47a1);"
            "color: #e3f2fd;"
            "border: 1px solid rgba(144,202,249,0.3);"
            "border-radius: 14px 14px 4px 14px;"
            "padding: 10px 14px;"
            "font-size: 13px;"
        )
        layout.addStretch()
        layout.addWidget(bubble)
    else:
        bubble.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #041825, stop:1 #071e30);"
            "color: #cde8f5;"
            "border: 1px solid rgba(0,229,255,0.22);"
            "border-radius: 14px 14px 14px 4px;"
            "padding: 10px 14px;"
            "font-size: 13px;"
        )
        layout.addWidget(bubble)
        layout.addStretch()

    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(12)
    shadow.setColor(QColor(0, 229, 255, 60) if role == "jarvis" else QColor(13, 71, 161, 80))
    shadow.setOffset(0, 2)
    bubble.setGraphicsEffect(shadow)

    return container


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────
class JarvisWindow(QWidget):

    STATUS_IDLE      = "idle"
    STATUS_LISTENING = "listening"
    STATUS_THINKING  = "thinking"
    STATUS_SPEAKING  = "speaking"

    def __init__(self):
        super().__init__()
        self._status   = self.STATUS_IDLE
        self._router   = None   # lazy-loaded
        self._workers  = []     # keep refs alive

        self._build_ui()
        self._init_backend_async()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("J.A.R.V.I.S — Intelligent Assistant")
        self.setMinimumSize(920, 680)
        self.resize(1050, 720)

        # global dark background
        self.setStyleSheet("QWidget { background-color: #020b14; color: #cde8f5; }")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT SIDEBAR ─────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(
            "QFrame { background-color: #041825; border-right: 1px solid rgba(0,229,255,0.15); }"
        )
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(16, 24, 16, 24)
        sb_layout.setSpacing(16)

        # Logo / brand
        brand = QLabel("J.A.R.V.I.S")
        brand.setFont(QFont("Consolas", 18, QFont.Bold))
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet("color: #00e5ff; letter-spacing: 4px;")
        self._add_glow(brand, QColor(0, 229, 255, 100), 20)

        sub = QLabel("Intelligent Assistant")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #5c8fa5; font-size: 10px; letter-spacing: 1px;")

        # Arc reactor
        self.arc = ArcReactor()

        # Status label
        self.status_label = QLabel("● STANDBY")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #00e676; font-family: Consolas; font-size: 11px; letter-spacing: 2px;"
        )

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: rgba(0,229,255,0.15);")

        # Stat rows
        self.stat_model   = self._stat_row("MODEL",   "qwen3:4b")
        self.stat_tts     = self._stat_row("VOICE",   "LuxTTS")
        self.stat_memory  = self._stat_row("MEMORY",  "checking…")

        sb_layout.addWidget(brand)
        sb_layout.addWidget(sub)
        sb_layout.addWidget(self.arc, alignment=Qt.AlignCenter)
        sb_layout.addWidget(self.status_label)
        sb_layout.addWidget(div)
        sb_layout.addWidget(self.stat_model)
        sb_layout.addWidget(self.stat_tts)
        sb_layout.addWidget(self.stat_memory)
        sb_layout.addStretch()

        # ── RIGHT PANEL ──────────────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top bar
        topbar = QFrame()
        topbar.setFixedHeight(52)
        topbar.setStyleSheet(
            "QFrame { background: rgba(4,24,37,0.95); border-bottom: 1px solid rgba(0,229,255,0.15); }"
        )
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("CHAT INTERFACE")
        title.setFont(QFont("Consolas", 11))
        title.setStyleSheet("color: #00e5ff; letter-spacing: 3px;")

        self.tts_status = QLabel("◎ TTS OFFLINE")
        self.tts_status.setStyleSheet("color: #ff3d5a; font-family: Consolas; font-size: 10px;")

        tb_layout.addWidget(title)
        tb_layout.addStretch()
        tb_layout.addWidget(self.tts_status)

        # Chat scroll area
        self.chat_area  = QWidget()
        self.chat_area.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(6)
        self.chat_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self.chat_area)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: #020b14; }"
            "QScrollBar:vertical { width: 4px; background: #020b14; }"
            "QScrollBar::handle:vertical { background: rgba(0,229,255,0.3); border-radius: 2px; }"
        )
        self._scroll = scroll

        # Waveform
        self.waveform = Waveform()

        # Input bar
        input_bar = QFrame()
        input_bar.setStyleSheet(
            "QFrame { background: rgba(4,24,37,0.97); border-top: 1px solid rgba(0,229,255,0.15); }"
        )
        input_bar.setFixedHeight(74)
        ib_layout = QHBoxLayout(input_bar)
        ib_layout.setContentsMargins(16, 10, 16, 10)
        ib_layout.setSpacing(10)

        self.text_input = QTextEdit()
        self.text_input.setFixedHeight(50)
        self.text_input.setPlaceholderText(
            'Ask JARVIS anything… "Open Spotify", "Remember my WiFi is…", "System status"'
        )
        self.text_input.setStyleSheet(
            "QTextEdit {"
            "  background: #041825;"
            "  color: #cde8f5;"
            "  border: 1px solid rgba(0,229,255,0.2);"
            "  border-radius: 10px;"
            "  padding: 8px 14px;"
            "  font-family: Consolas;"
            "  font-size: 13px;"
            "}"
            "QTextEdit:focus { border: 1px solid rgba(0,229,255,0.6); }"
        )

        self.mic_btn = self._icon_btn("🎤", "#00e5ff", tooltip="Hold to speak")
        self.mic_btn.setCheckable(True)
        self.mic_btn.clicked.connect(self._on_mic)

        self.send_btn = QPushButton("SEND")
        self.send_btn.setFixedSize(80, 50)
        self.send_btn.setFont(QFont("Consolas", 10, QFont.Bold))
        self.send_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #00838f, stop:1 #006064);"
            "  color: #e0f7fa;"
            "  border: 1px solid #00bcd4;"
            "  border-radius: 10px;"
            "  letter-spacing: 2px;"
            "}"
            "QPushButton:hover { background: #0097a7; }"
            "QPushButton:pressed { background: #006064; }"
            "QPushButton:disabled { opacity: 0.4; }"
        )
        self.send_btn.clicked.connect(self._on_send)

        ib_layout.addWidget(self.mic_btn)
        ib_layout.addWidget(self.text_input)
        ib_layout.addWidget(self.send_btn)

        right_layout.addWidget(topbar)
        right_layout.addWidget(scroll, 1)
        right_layout.addWidget(self.waveform)
        right_layout.addWidget(input_bar)

        root.addWidget(sidebar)
        root.addWidget(right, 1)

        # Welcome message
        self._append("jarvis", "Good day, sir. All systems initialising. Please stand by.")
        self._set_status(self.STATUS_IDLE, "INITIALISING…")

        # Check TTS server
        self._check_tts_timer = QTimer(self)
        self._check_tts_timer.timeout.connect(self._poll_tts)
        self._check_tts_timer.start(3000)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _stat_row(self, label: str, value: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: rgba(0,229,255,0.05); border: 1px solid rgba(0,229,255,0.12); border-radius: 6px;")
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 6, 10, 6)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 9px; letter-spacing: 1px; color: #5c8fa5;")
        val = QLabel(value)
        val.setStyleSheet("font-family: Consolas; font-size: 11px; color: #00e5ff;")
        val.setObjectName(f"stat_{label.lower()}")
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(val)
        # keep ref to val for updates
        setattr(self, f"_val_{label.lower()}", val)
        return w

    def _icon_btn(self, icon: str, color: str, tooltip="") -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(50, 50)
        btn.setToolTip(tooltip)
        btn.setFont(QFont("Segoe UI Emoji", 18))
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: rgba(0,229,255,0.08);"
            f"  border: 1px solid rgba(0,229,255,0.2);"
            f"  border-radius: 10px;"
            f"  color: {color};"
            f"}}"
            f"QPushButton:hover {{ background: rgba(0,229,255,0.15); border-color: {color}; }}"
            f"QPushButton:checked {{ background: rgba(255,61,90,0.2); border-color: #ff3d5a; color: #ff3d5a; }}"
        )
        return btn

    def _add_glow(self, widget, color, radius=16):
        fx = QGraphicsDropShadowEffect()
        fx.setBlurRadius(radius)
        fx.setColor(color)
        fx.setOffset(0, 0)
        widget.setGraphicsEffect(fx)

    def _append(self, role: str, text: str):
        bubble = make_bubble(role, text)
        # insert before the trailing stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        # scroll to bottom
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _set_status(self, status: str, label: str = None):
        self._status = status
        colours = {
            self.STATUS_IDLE:      ("#00e676", "● STANDBY"),
            self.STATUS_LISTENING: ("#ff3d5a", "⬤ LISTENING"),
            self.STATUS_THINKING:  ("#ffea00", "⬤ THINKING"),
            self.STATUS_SPEAKING:  ("#00e5ff", "⬤ SPEAKING"),
        }
        colour, default_label = colours.get(status, ("#5c8fa5", "● OFFLINE"))
        self.status_label.setText(label or default_label)
        self.status_label.setStyleSheet(
            f"color: {colour}; font-family: Consolas; font-size: 11px; letter-spacing: 2px;"
        )
        self.waveform.set_active(status == self.STATUS_LISTENING)

    def _set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.mic_btn.setEnabled(not busy)
        self.text_input.setReadOnly(busy)

    # ── backend init ──────────────────────────────────────────────────────────

    def _init_backend_async(self):
        def _load():
            from brain import JarvisBrain
            from router import JarvisRouter
            brain = JarvisBrain()
            router = JarvisRouter(brain=brain)
            return router

        class LoadWorker(QThread):
            done  = pyqtSignal(object)
            error = pyqtSignal(str)
            def run(self_):
                try:
                    self_.done.emit(_load())
                except Exception as exc:
                    self_.error.emit(str(exc))

        w = LoadWorker(self)
        w.done.connect(self._on_backend_ready)
        w.error.connect(lambda e: self._append("jarvis", f"⚠ Backend load error: {e}"))
        w.start()
        self._workers.append(w)

    def _on_backend_ready(self, router):
        self._router = router
        mem = router.memory.available
        self._val_memory.setText("SUPABASE" if mem else "LOCAL")
        self._append("jarvis", "All systems online. How may I assist you, sir?")
        self._set_status(self.STATUS_IDLE)

    # ── TTS health check ──────────────────────────────────────────────────────

    def _poll_tts(self):
        try:
            r = requests.get(TTS_HEALTH_URL, timeout=1)
            if r.status_code == 200:
                self.tts_status.setText("◉ TTS ONLINE")
                self.tts_status.setStyleSheet("color: #00e676; font-family: Consolas; font-size: 10px;")
                self._check_tts_timer.setInterval(15000)
            else:
                self._tts_offline()
        except Exception:
            self._tts_offline()

    def _tts_offline(self):
        self.tts_status.setText("◎ TTS OFFLINE")
        self.tts_status.setStyleSheet("color: #ff3d5a; font-family: Consolas; font-size: 10px;")

    # ── user input ────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self._on_send()
        else:
            super().keyPressEvent(event)

    def _on_send(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            return
        if self._router is None:
            self._append("jarvis", "Still initialising, sir. Please wait a moment.")
            return

        self.text_input.clear()
        self._append("user", text)
        self._process(text)

    def _on_mic(self):
        if self._status != self.STATUS_IDLE:
            self.mic_btn.setChecked(False)
            return

        self._set_status(self.STATUS_LISTENING)
        self._set_busy(True)
        self._append("jarvis", "Listening…")

        w = ListenWorker()
        w.transcript_ready.connect(self._on_transcript)
        w.error.connect(self._on_listen_error)
        w.start()
        self._workers.append(w)

    def _on_transcript(self, text: str):
        self.mic_btn.setChecked(False)
        self._set_busy(False)

        if not text.strip():
            self._append("jarvis", "I didn't catch anything, sir.")
            self._set_status(self.STATUS_IDLE)
            return

        self._append("user", text)
        self._process(text)

    def _on_listen_error(self, err: str):
        self.mic_btn.setChecked(False)
        self._set_busy(False)
        self._append("jarvis", f"Microphone error: {err}")
        self._set_status(self.STATUS_IDLE)

    # ── AI processing ─────────────────────────────────────────────────────────

    def _process(self, text: str):
        self._set_status(self.STATUS_THINKING)
        self._set_busy(True)

        w = RouterWorker(text, self._router)
        w.reply_ready.connect(self._on_reply)
        w.error.connect(self._on_route_error)
        w.start()
        self._workers.append(w)

    def _on_reply(self, answer: str):
        if not answer:
            answer = "I'm not sure how to respond to that, sir."

        self._append("jarvis", answer)
        self._set_status(self.STATUS_SPEAKING)

        tts = TTSWorker(answer)
        tts.finished.connect(self._on_tts_done)
        tts.error.connect(lambda e: (
            self._append("jarvis", f"[TTS error: {e}]"),
            self._on_tts_done()
        ))
        tts.start()
        self._workers.append(tts)

    def _on_route_error(self, err: str):
        self._append("jarvis", f"⚠ Error: {err}")
        self._set_status(self.STATUS_IDLE)
        self._set_busy(False)

    def _on_tts_done(self):
        self._set_status(self.STATUS_IDLE)
        self._set_busy(False)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Inter", 10))
    app.setStyle("Fusion")

    # Apply dark palette globally
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor("#020b14"))
    palette.setColor(QPalette.WindowText,      QColor("#cde8f5"))
    palette.setColor(QPalette.Base,            QColor("#041825"))
    palette.setColor(QPalette.AlternateBase,   QColor("#071e30"))
    palette.setColor(QPalette.Text,            QColor("#cde8f5"))
    palette.setColor(QPalette.Button,          QColor("#041825"))
    palette.setColor(QPalette.ButtonText,      QColor("#cde8f5"))
    palette.setColor(QPalette.Highlight,       QColor("#006064"))
    palette.setColor(QPalette.HighlightedText, QColor("#e0f7fa"))
    palette.setColor(QPalette.ToolTipBase,     QColor("#041825"))
    palette.setColor(QPalette.ToolTipText,     QColor("#00e5ff"))
    app.setPalette(palette)

    win = JarvisWindow()
    win.show()

    sys.exit(app.exec_())
