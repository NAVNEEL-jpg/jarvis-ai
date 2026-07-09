"""
JARVIS Smart Home Module
========================
Controls smart appliances and devices via three backends:

  1. Alexa (alexapy)       — controls Echo + all Alexa-linked devices
                             (Avita, smart bulbs, plugs, etc.)
  2. Google Home           — controls Nest speakers + Google Home linked devices
  3. Home Assistant (HA)   — optional hub bridge for everything else
  4. Tuya local            — direct local Tuya/Smart Life device control

Configuration (.env):
---------------------
  # --- Alexa ---
  AMAZON_EMAIL=you@gmail.com
  AMAZON_PASSWORD=your_amazon_password
  ALEXA_REGION=amazon.in          # amazon.in / amazon.com / amazon.co.uk

  # --- Google Home ---
  GOOGLE_HOME_EMAIL=you@gmail.com
  GOOGLE_HOME_PASSWORD=your_google_app_password

  # --- Home Assistant (optional) ---
  HA_URL=http://homeassistant.local:8123
  HA_TOKEN=your_long_lived_access_token

  # --- Tuya local (optional) ---
  TUYA_DEVICES={}

Voice commands:
  "Turn on living room lights"
  "Turn off bedroom AC"
  "Set thermostat to 22 degrees"
  "Lock the front door"
  "Play music on Echo"
  "Announce dinner is ready"
  "What is the living room temperature?"
  "List my devices"
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── env ────────────────────────────────────────────────────────────────────────

AMAZON_EMAIL      = os.getenv("AMAZON_EMAIL", "")
AMAZON_PASSWORD   = os.getenv("AMAZON_PASSWORD", "")
ALEXA_REGION      = os.getenv("ALEXA_REGION", "amazon.in")   # amazon.in / amazon.com

GOOGLE_HOME_EMAIL    = os.getenv("GOOGLE_HOME_EMAIL", "")
GOOGLE_HOME_PASSWORD = os.getenv("GOOGLE_HOME_PASSWORD", "")

HA_URL    = os.getenv("HA_URL", "").rstrip("/")
HA_TOKEN  = os.getenv("HA_TOKEN", "")

TUYA_DEVICES_RAW = os.getenv("TUYA_DEVICES", "{}")


# ─────────────────────────────────────────────────────────────────────────────
# ALEXA BRIDGE (alexapy)
# ─────────────────────────────────────────────────────────────────────────────

class AlexaBridge:
    """
    Controls Amazon Alexa and all Alexa-connected devices
    (smart bulbs, plugs, Avita AC, fans, etc.) via alexapy.

    Requires: pip install alexapy
    Config: AMAZON_EMAIL + AMAZON_PASSWORD + ALEXA_REGION in .env
    """

    def __init__(self):
        self.email    = AMAZON_EMAIL
        self.password = AMAZON_PASSWORD
        self.url      = f"https://www.{ALEXA_REGION}"
        self.available = bool(self.email and self.password)
        self._login   = None
        self._api     = None
        self._devices = {}      # name → serial/entity
        self._lock    = threading.Lock()
        self._ready   = False

        if self.available:
            threading.Thread(target=self._init_async, daemon=True).start()

    # ── async init ────────────────────────────────────────────────────────────

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def _init_async(self):
        try:
            from alexapy import AlexaLogin, AlexaAPI

            login = AlexaLogin(
                url=self.url,
                email=self.email,
                password=self.password,
                outputfiles_path=os.path.join(
                    os.path.dirname(__file__), ".alexa_cache"
                ),
                debug=False,
            )
            self._run(login.login())

            if not login.status.get("login_successful"):
                logger.warning("Alexa login failed: %s", login.status)
                return

            self._login = login
            self._api   = AlexaAPI

            # Cache device list
            raw = self._run(AlexaAPI.get_devices(login))
            if raw:
                for d in raw:
                    name = d.get("accountName", "").lower()
                    self._devices[name] = d.get("serialNumber", "")
            self._ready = True
            logger.info("Alexa bridge ready: %d devices", len(self._devices))

        except ImportError:
            logger.warning("alexapy not installed. Run: pip install alexapy")
        except Exception as exc:
            logger.warning("Alexa init error: %s", exc)

    def _get_serial(self, device_name: str) -> Optional[str]:
        """Find closest device by name substring."""
        name = device_name.lower()
        for key, serial in self._devices.items():
            if name in key or key in name:
                return serial
        # Return first Echo if no match (common fallback)
        echo_keys = [k for k in self._devices if "echo" in k]
        return self._devices[echo_keys[0]] if echo_keys else None

    # ── smart home control ────────────────────────────────────────────────────

    def _smart_home_action(self, entity_id: str, action: str, **values) -> bool:
        """Send a smart home command via Alexa's smart home API."""
        if not self._ready or not self._login:
            return False
        try:
            from alexapy import AlexaAPI
            self._run(
                AlexaAPI.set_smart_home_device_state(
                    self._login,
                    entity_id,
                    action,
                    **values,
                )
            )
            return True
        except Exception as exc:
            logger.warning("Alexa smart home %s: %s", action, exc)
            return False

    def turn_on_device(self, device_name: str) -> bool:
        if not self._ready:
            return False
        try:
            from alexapy import AlexaAPI
            smarthome = self._run(
                AlexaAPI.get_smart_home_entities(self._login)
            )
            for entity in (smarthome or []):
                if device_name.lower() in entity.get("name", "").lower():
                    self._run(
                        AlexaAPI.set_smart_home_device_state(
                            self._login, entity["entityId"], "turnOn"
                        )
                    )
                    return True
            return False
        except Exception as exc:
            logger.warning("Alexa turn_on: %s", exc)
            return False

    def turn_off_device(self, device_name: str) -> bool:
        if not self._ready:
            return False
        try:
            from alexapy import AlexaAPI
            smarthome = self._run(
                AlexaAPI.get_smart_home_entities(self._login)
            )
            for entity in (smarthome or []):
                if device_name.lower() in entity.get("name", "").lower():
                    self._run(
                        AlexaAPI.set_smart_home_device_state(
                            self._login, entity["entityId"], "turnOff"
                        )
                    )
                    return True
            return False
        except Exception as exc:
            logger.warning("Alexa turn_off: %s", exc)
            return False

    def set_brightness(self, device_name: str, pct: int) -> bool:
        if not self._ready:
            return False
        try:
            from alexapy import AlexaAPI
            smarthome = self._run(
                AlexaAPI.get_smart_home_entities(self._login)
            )
            for entity in (smarthome or []):
                if device_name.lower() in entity.get("name", "").lower():
                    self._run(
                        AlexaAPI.set_smart_home_device_state(
                            self._login, entity["entityId"],
                            "setBrightness", brightness=pct
                        )
                    )
                    return True
            return False
        except Exception as exc:
            logger.warning("Alexa brightness: %s", exc)
            return False

    def send_command(self, command: str, device_name: str = None) -> bool:
        """
        Send a natural language command to an Echo device.
        Alexa will interpret it as if you spoke it.
        e.g. command='turn on living room lights'
        """
        if not self._ready:
            return False
        try:
            from alexapy import AlexaAPI
            serial = self._get_serial(device_name or "echo")
            if not serial:
                return False
            self._run(
                AlexaAPI.send_sequence_command(
                    self._login, serial, "Alexa.TextCommand",
                    text=command,
                )
            )
            return True
        except Exception as exc:
            logger.warning("Alexa command: %s", exc)
            return False

    def list_devices(self) -> list[str]:
        return list(self._devices.keys())

    def list_smart_home(self) -> list[str]:
        if not self._ready:
            return []
        try:
            from alexapy import AlexaAPI
            entities = self._run(AlexaAPI.get_smart_home_entities(self._login)) or []
            return [e.get("name", "") for e in entities]
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE HOME BRIDGE (glocaltokens)
# ─────────────────────────────────────────────────────────────────────────────

class GoogleHomeBridge:
    """
    Discovers and controls Google Home / Nest devices on local network.
    Can cast TTS announcements and control Chromecast audio.

    Requires: pip install glocaltokens pychromecast
    Config: GOOGLE_HOME_EMAIL + GOOGLE_HOME_PASSWORD (App Password)
    """

    def __init__(self):
        self.email    = GOOGLE_HOME_EMAIL
        self.password = GOOGLE_HOME_PASSWORD
        self.available = bool(self.email and self.password)
        self._devices = {}   # name → HomeMiniInfo
        self._tokens  = {}   # name → local_auth_token
        self._ready   = False

        if self.available:
            threading.Thread(target=self._init, daemon=True).start()

    def _init(self):
        try:
            from glocaltokens.client import GLocalAuthenticationTokens

            client = GLocalAuthenticationTokens(
                username=self.email,
                password=self.password,
            )
            tokens = client.get_google_devices_json()
            if tokens:
                for device in tokens:
                    name = device.get("device_name", "").lower()
                    self._tokens[name] = device.get("local_auth_token", "")
                    self._devices[name] = device
            self._ready = True
            logger.info("Google Home ready: %d devices", len(self._devices))

        except ImportError:
            logger.warning("glocaltokens not installed.")
        except Exception as exc:
            logger.warning("Google Home init: %s", exc)

    def get_device(self, name: str) -> Optional[dict]:
        name = name.lower()
        for key, dev in self._devices.items():
            if name in key or key in name:
                return dev
        return None

    def _cast(self, device_name: str, text: str) -> bool:
        """Announce via text-to-speech on a Google Home speaker."""
        try:
            import pychromecast
            chromecasts, browser = pychromecast.get_chromecasts()
            target = None
            for cc in chromecasts:
                if device_name.lower() in cc.name.lower() or device_name == "all":
                    target = cc
                    break
            if not target and chromecasts:
                target = chromecasts[0]
            if target:
                target.wait()
                mc = target.media_controller
                mc.play_media(
                    f"https://translate.google.com/translate_tts"
                    f"?ie=UTF-8&client=tw-ob&q={text.replace(' ', '+')}&tl=en",
                    "audio/mpeg",
                )
                mc.block_until_active()
                return True
        except Exception as exc:
            logger.warning("Google Cast: %s", exc)
        return False

    def announce(self, message: str, device: str = "all") -> bool:
        return self._cast(device, message)

    def list_devices(self) -> list[str]:
        return list(self._devices.keys())


# ─────────────────────────────────────────────────────────────────────────────
# HOME ASSISTANT BRIDGE (optional hub for everything else)
# ─────────────────────────────────────────────────────────────────────────────

class HomeAssistantBridge:
    def __init__(self):
        self.base  = HA_URL
        self.token = HA_TOKEN
        self.available = bool(self.base and self.token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type":  "application/json",
        }

    def _post(self, path: str, data: dict = None) -> Optional[Any]:
        if not self.available:
            return None
        try:
            import urllib.request
            body = json.dumps(data or {}).encode()
            req  = urllib.request.Request(
                f"{self.base}/api/{path}", data=body,
                headers=self._headers(), method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            logger.warning("HA POST %s: %s", path, exc)
            return None

    def _get(self, path: str) -> Optional[Any]:
        if not self.available:
            return None
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base}/api/{path}", headers=self._headers()
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            logger.warning("HA GET %s: %s", path, exc)
            return None

    def turn_on(self, entity_id: str, **kwargs) -> bool:
        return self._post("services/homeassistant/turn_on",
                          {"entity_id": entity_id, **kwargs}) is not None

    def turn_off(self, entity_id: str) -> bool:
        return self._post("services/homeassistant/turn_off",
                          {"entity_id": entity_id}) is not None

    def find_entity(self, keyword: str, domain: str = None) -> Optional[str]:
        states = self._get("states") or []
        keyword = keyword.lower()
        for s in states:
            eid = s.get("entity_id", "")
            if domain and not eid.startswith(domain + "."):
                continue
            fn = s.get("attributes", {}).get("friendly_name", "")
            if keyword in fn.lower() or keyword in eid.lower():
                return eid
        return None

    def list_entities(self, domain: str = None) -> list:
        states = self._get("states") or []
        if domain:
            return [s["entity_id"] for s in states
                    if s["entity_id"].startswith(domain + ".")]
        return [s["entity_id"] for s in states]

    def get_state(self, entity_id: str) -> Optional[dict]:
        return self._get(f"states/{entity_id}")


# ─────────────────────────────────────────────────────────────────────────────
# TUYA LOCAL BRIDGE
# ─────────────────────────────────────────────────────────────────────────────

class TuyaBridge:
    def __init__(self):
        try:
            self._devices = json.loads(TUYA_DEVICES_RAW)
        except Exception:
            self._devices = {}
        self.available = bool(self._devices)

    def _get_device(self, name: str):
        try:
            import tinytuya
        except ImportError:
            return None
        for k, cfg in self._devices.items():
            if name.lower() in k.lower():
                return tinytuya.OutletDevice(
                    dev_id=cfg["id"], address=cfg["ip"],
                    local_key=cfg["key"], version=cfg.get("version", 3.3),
                )
        return None

    def turn_on(self, name: str) -> bool:
        dev = self._get_device(name)
        if dev:
            try:
                dev.turn_on(); return True
            except Exception:
                pass
        return False

    def turn_off(self, name: str) -> bool:
        dev = self._get_device(name)
        if dev:
            try:
                dev.turn_off(); return True
            except Exception:
                pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
# JARVIS SMART HOME — HIGH-LEVEL INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

class JarvisSmartHome:
    """
    High-level smart home interface.
    Priority: Alexa → Google Home → Home Assistant → Tuya
    """

    def __init__(self):
        self.alexa  = AlexaBridge()
        self.google = GoogleHomeBridge()
        self.ha     = HomeAssistantBridge()
        self.tuya   = TuyaBridge()

    @property
    def available(self) -> bool:
        return (
            self.alexa.available
            or self.google.available
            or self.ha.available
            or self.tuya.available
        )

    @property
    def active_backends(self) -> list[str]:
        active = []
        if self.alexa.available:  active.append("Alexa")
        if self.google.available: active.append("Google Home")
        if self.ha.available:     active.append("Home Assistant")
        if self.tuya.available:   active.append("Tuya")
        return active

    # ── TURN ON ───────────────────────────────────────────────────────────────

    def turn_on(self, device: str, room: str = None, brightness: int = None) -> str:
        target = self._target(device, room)

        # Try Alexa first (controls Alexa-linked devices like Avita)
        if self.alexa.available and self.alexa._ready:
            if brightness is not None:
                ok = self.alexa.set_brightness(target, brightness)
                if ok:
                    return f"Turning on {target} at {brightness}% brightness."
            ok = self.alexa.turn_on_device(target)
            if ok:
                return f"Turning on {target}."
            # Fall back to sending voice command to Echo
            ok = self.alexa.send_command(f"turn on {target}")
            if ok:
                return f"Told Alexa to turn on {target}."

        # Try HA if Alexa didn't work
        if self.ha.available:
            entity = self.ha.find_entity(target)
            if entity:
                kw = {}
                if brightness is not None:
                    kw["brightness_pct"] = brightness
                ok = self.ha.turn_on(entity, **kw)
                return (f"Turning on {target}." if ok
                        else f"Could not reach {target}.")

        # Tuya fallback
        if self.tuya.available:
            ok = self.tuya.turn_on(target)
            return f"Turning on {target}." if ok else f"Could not reach {target}."

        if self.alexa.available and not self.alexa._ready:
            return "Alexa is still signing in, sir. Please try again in a moment."

        return self._not_configured()

    # ── TURN OFF ──────────────────────────────────────────────────────────────

    def turn_off(self, device: str, room: str = None) -> str:
        target = self._target(device, room)

        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.turn_off_device(target)
            if ok:
                return f"Turning off {target}."
            ok = self.alexa.send_command(f"turn off {target}")
            if ok:
                return f"Told Alexa to turn off {target}."

        if self.ha.available:
            if "all" in target:
                for e in self.ha.list_entities("light"):
                    self.ha.turn_off(e)
                return "All lights are now off, sir."
            entity = self.ha.find_entity(target)
            if entity:
                ok = self.ha.turn_off(entity)
                return f"Turning off {target}." if ok else f"Could not reach {target}."

        if self.tuya.available:
            ok = self.tuya.turn_off(target)
            return f"Turning off {target}." if ok else f"Could not reach {target}."

        if self.alexa.available and not self.alexa._ready:
            return "Alexa is still signing in, sir. Please try again in a moment."

        return self._not_configured()

    # ── BRIGHTNESS ────────────────────────────────────────────────────────────

    def set_brightness(self, device: str, room: str, level: int) -> str:
        target = self._target(device, room)
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.set_brightness(target, level)
            if ok:
                return f"Setting {target} brightness to {level}%."
            ok = self.alexa.send_command(f"set {target} to {level} percent")
            if ok:
                return f"Told Alexa to set {target} to {level}%."
        if self.ha.available:
            entity = self.ha.find_entity(target, domain="light")
            if entity:
                ok = self.ha.turn_on(entity, brightness_pct=level)
                return f"Setting {target} to {level}%." if ok else "Could not adjust."
        return self._not_configured()

    # ── TEMPERATURE ───────────────────────────────────────────────────────────

    def set_temperature(self, device: str, degrees: float) -> str:
        cmd = f"set {device} to {degrees} degrees"
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.send_command(cmd)
            if ok:
                return f"Told Alexa to set {device} to {degrees}°."
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="climate")
            if entity:
                ok = self.ha._post(
                    "services/climate/set_temperature",
                    {"entity_id": entity, "temperature": degrees}
                ) is not None
                return f"Setting {device} to {degrees}°." if ok else "Could not reach thermostat."
        return self._not_configured()

    def get_temperature(self, device: str) -> str:
        if self.ha.available:
            entity = (
                self.ha.find_entity(device, domain="climate") or
                self.ha.find_entity(device, domain="sensor")
            )
            if entity:
                state = self.ha.get_state(entity)
                if state:
                    val  = state.get("state", "unknown")
                    unit = state.get("attributes", {}).get("unit_of_measurement", "°")
                    fn   = state.get("attributes", {}).get("friendly_name", device)
                    return f"The {fn} temperature is {val}{unit}."
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.send_command(f"what is the {device} temperature")
            if ok:
                return "Asked Alexa for the temperature, sir. Check your Echo."
        return "No temperature sensor found."

    # ── LOCK / UNLOCK ─────────────────────────────────────────────────────────

    def lock_door(self, device: str = "front door") -> str:
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.send_command(f"lock {device}")
            if ok:
                return f"Told Alexa to lock {device}."
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="lock")
            if entity:
                ok = self.ha._post("services/lock/lock", {"entity_id": entity}) is not None
                return f"{device} locked." if ok else "Could not lock."
        return self._not_configured()

    def unlock_door(self, device: str = "front door") -> str:
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.send_command(f"unlock {device}")
            if ok:
                return f"Told Alexa to unlock {device}."
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="lock")
            if entity:
                ok = self.ha._post("services/lock/unlock", {"entity_id": entity}) is not None
                return f"{device} unlocked." if ok else "Could not unlock."
        return self._not_configured()

    # ── ANNOUNCE ──────────────────────────────────────────────────────────────

    def announce(self, message: str, device: str = "all") -> str:
        announced = []
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.send_command(f"announce {message}")
            if ok:
                announced.append("Alexa")
        if self.google.available and self.google._ready:
            ok = self.google.announce(message, device)
            if ok:
                announced.append("Google Home")
        if announced:
            return f"Announcing on {' and '.join(announced)}: \"{message}\""
        return self._not_configured()

    # ── LIST DEVICES ──────────────────────────────────────────────────────────

    def list_devices(self, domain: str = None) -> str:
        names = []
        if self.alexa.available and self.alexa._ready:
            smart = self.alexa.list_smart_home()
            if smart:
                names.extend(smart[:8])
        if self.ha.available:
            entities = self.ha.list_entities(domain)
            for e in entities[:8]:
                state = self.ha.get_state(e)
                fn = state.get("attributes", {}).get("friendly_name", e) if state else e
                if fn not in names:
                    names.append(fn)
        if names:
            return "I found these devices: " + ", ".join(names[:10]) + "."
        return self._not_configured()

    def get_device_status(self, device: str) -> str:
        if self.ha.available:
            entity = self.ha.find_entity(device)
            if entity:
                state = self.ha.get_state(entity)
                if state:
                    s = state.get("state", "unknown")
                    fn = state.get("attributes", {}).get("friendly_name", device)
                    return f"{fn} is currently {s}."
        if self.alexa.available and self.alexa._ready:
            ok = self.alexa.send_command(f"is {device} on")
            if ok:
                return f"Asked Alexa about {device}. Check your Echo."
        return f"I couldn't find the status for {device}, sir."

    # ── helpers ───────────────────────────────────────────────────────────────

    def _target(self, device: str, room: str = None) -> str:
        parts = [p for p in [room, device] if p]
        return " ".join(p.lower() for p in parts)

    def _not_configured(self) -> str:
        return (
            "Smart home is not configured yet, sir. "
            "Add AMAZON_EMAIL and AMAZON_PASSWORD to your .env file to control "
            "Alexa-linked devices, or GOOGLE_HOME_EMAIL and GOOGLE_HOME_PASSWORD "
            "for Google Home devices."
        )
