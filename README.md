# JARVIS — Local AI Voice Assistant

> **J**ust **A** **R**ather **V**ery **I**ntelligent **S**ystem  
> A fully local, privacy-first Windows voice assistant with a web UI.

---

## Features

| Feature | Detail |
|---|---|
| 🎙 **Wake word** | `"Hey Jarvis"` via openWakeWord |
| 🎤 **Speech-to-text** | faster-whisper (`small.en`, CPU) |
| 🧠 **AI Brain** | Ollama `qwen3:4b` — runs 100% offline |
| 🔊 **Voice** | JARVIS Lux TTS (custom neural voice) |
| 🖥 **Automation** | Open apps, websites, system status |
| 💾 **Memory** | Supabase-backed persistent memory |
| 🌐 **Web UI** | Browser dashboard at `http://localhost:3000` |
| 🔲 **System tray** | Windows tray controller |

---

## Architecture

```
jarvis-ai/
├── assistant/
│   ├── main.py             # Main voice assistant loop
│   ├── wake_word.py        # openWakeWord "hey_jarvis"
│   ├── vad_recorder.py     # Silero VAD command recording
│   ├── stt.py              # faster-whisper STT
│   ├── brain.py            # Ollama qwen3:4b LLM
│   ├── router.py           # Deterministic tool router + memory
│   ├── memory.py           # Supabase memory layer
│   ├── tools.py            # Windows automation tools
│   ├── tts_client.py       # JARVIS TTS server client
│   └── jarvis_controller.py# System tray controller
│
├── ui/
│   ├── ui_server.py        # FastAPI Web UI (port 3000)
│   └── static/
│       └── index.html      # JARVIS dashboard
│
├── external/
│   └── JarvisLuxTTS/       # Neural TTS server (port 8765)
│       └── .venv-tts/
│
├── .venv/                  # Main Python environment
├── .env                    # Secrets (not committed)
├── .env.example            # Env template
└── jarvis_controller.py    # Root launcher
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- `qwen3:4b` model pulled: `ollama pull qwen3:4b`

### 1. Install dependencies
```powershell
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Configure environment (optional — for Supabase memory)
```powershell
copy .env.example .env
# Edit .env and add your Supabase URL and anon key
```

### 3. Start via system tray controller
```powershell
.\.venv\Scripts\python.exe assistant\jarvis_controller.py
```

Right-click the tray icon → **Start JARVIS**

### 4. Open Web UI
Right-click tray icon → **Open Web UI**  
Or navigate to: `http://localhost:3000`

---

## Supabase Memory Setup

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run:

```sql
CREATE TABLE jarvis_memory (
    id         BIGSERIAL PRIMARY KEY,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE jarvis_log (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT 'default',
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

3. Add credentials to `.env`:
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

### Memory commands (say or type to JARVIS)
| Command | Action |
|---|---|
| `"Remember that my WiFi password is test123"` | Stores key=value |
| `"What's my WiFi password?"` | Recalls stored value |
| `"What do you know about my birthday?"` | Searches memory |

---

## Web UI Features
- 💬 Real-time WebSocket chat
- 🎤 Voice input (browser Web Speech API)
- 🔊 Text-to-speech output (browser TTS)
- 📋 Stored memory panel
- ⚡ Quick command buttons
- 📡 Live JARVIS status

---

## License
MIT
