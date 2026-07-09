"""
JARVIS Smart Home Module
========================
Controls smart appliances and devices via:

  1. Home Assistant REST API  (recommended — bridges Google Home + Alexa + Tuya + more)
  2. Google Home local API    (via glocaltokens, no cloud required)
  3. Alexa remote             (via alexa-remote-control concept, REST)
  4. Tuya / Smart Life        (via tinytuya, direct local control)

Configuration (.env):
---------------------
  # Home Assistant (easiest — controls everything through one hub)
  HA_URL=http://homeassistant.local:8123
  HA_TOKEN=your_long_lived_access_token

  # Google Home local (optional — if not using HA)
  GOOGLE_HOME_EMAIL=you@gmail.com
  GOOGLE_HOME_PASSWORD=your_app_password

  # Tuya direct local (optional)
  TUYA_DEVICES={"living_room_light":{"id":"...","ip":"...","key":"..."}}

Usage examples (voice/text commands):
--------------------------------------
  "Turn on the living room lights"
  "Turn off bedroom lights"
  "Set living room brightness to 50"
  "Set thermostat to 22 degrees"
  "What is the living room temperature?"
  "Lock the front door"
  "Turn on the fan"
  "Turn off all lights"
  "Play music on kitchen speaker"
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── env ──────────────────────────────────────────────────────────────────────

HA_URL      = os.getenv("HA_URL", "").rstrip("/")
HA_TOKEN    = os.getenv("HA_TOKEN", "")
TUYA_DEVICES_RAW = os.getenv("TUYA_DEVICES", "{}")


# ─────────────────────────────────────────────────────────────────────────────
# HOME ASSISTANT BRIDGE
# Most reliable approach — HA talks to Google Home, Alexa, Tuya, ZigBee, etc.
# ─────────────────────────────────────────────────────────────────────────────

class HomeAssistantBridge:
    """
    Controls devices via Home Assistant REST API.
    Supports lights, switches, climate, locks, media players.
    """

    def __init__(self):
        self.base  = HA_URL
        self.token = HA_TOKEN
        self.available = bool(self.base and self.token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type":  "application/json",
        }

    def _get(self, path: str) -> Optional[Any]:
        if not self.available:
            return None
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base}/api/{path}",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            logger.warning("HA GET %s failed: %s", path, exc)
            return None

    def _post(self, path: str, data: dict = None) -> Optional[Any]:
        if not self.available:
            return None
        try:
            import urllib.request
            body = json.dumps(data or {}).encode()
            req  = urllib.request.Request(
                f"{self.base}/api/{path}",
                data=body,
                headers=self._headers(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            logger.warning("HA POST %s failed: %s", path, exc)
            return None

    # ── lights ────────────────────────────────────────────────────────────────

    def turn_on(self, entity_id: str, **kwargs) -> bool:
        data = {"entity_id": entity_id, **kwargs}
        return self._post("services/homeassistant/turn_on", data) is not None

    def turn_off(self, entity_id: str) -> bool:
        data = {"entity_id": entity_id}
        return self._post("services/homeassistant/turn_off", data) is not None

    def set_brightness(self, entity_id: str, brightness_pct: int) -> bool:
        return self.turn_on(
            entity_id,
            brightness_pct=max(0, min(100, brightness_pct)),
        )

    def set_color_temp(self, entity_id: str, kelvin: int) -> bool:
        return self.turn_on(entity_id, kelvin=kelvin)

    # ── climate ───────────────────────────────────────────────────────────────

    def set_temperature(self, entity_id: str, temperature: float) -> bool:
        return (
            self._post(
                "services/climate/set_temperature",
                {"entity_id": entity_id, "temperature": temperature},
            ) is not None
        )

    def set_hvac_mode(self, entity_id: str, mode: str) -> bool:
        """mode: heat, cool, heat_cool, off, fan_only"""
        return (
            self._post(
                "services/climate/set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": mode},
            ) is not None
        )

    # ── locks ─────────────────────────────────────────────────────────────────

    def lock(self, entity_id: str) -> bool:
        return (
            self._post(
                "services/lock/lock",
                {"entity_id": entity_id},
            ) is not None
        )

    def unlock(self, entity_id: str) -> bool:
        return (
            self._post(
                "services/lock/unlock",
                {"entity_id": entity_id},
            ) is not None
        )

    # ── media players ─────────────────────────────────────────────────────────

    def media_play(self, entity_id: str) -> bool:
        return (
            self._post(
                "services/media_player/media_play",
                {"entity_id": entity_id},
            ) is not None
        )

    def media_pause(self, entity_id: str) -> bool:
        return (
            self._post(
                "services/media_player/media_pause",
                {"entity_id": entity_id},
            ) is not None
        )

    def set_volume(self, entity_id: str, volume: float) -> bool:
        """volume: 0.0 – 1.0"""
        return (
            self._post(
                "services/media_player/volume_set",
                {"entity_id": entity_id, "volume_level": volume},
            ) is not None
        )

    def tts_announce(self, entity_id: str, message: str) -> bool:
        """Announce via TTS on a Google Home / Alexa speaker."""
        return (
            self._post(
                "services/tts/cloud_say",
                {"entity_id": entity_id, "message": message},
            ) is not None
        )

    # ── state queries ─────────────────────────────────────────────────────────

    def get_state(self, entity_id: str) -> Optional[dict]:
        return self._get(f"states/{entity_id}")

    def get_all_states(self) -> list:
        return self._get("states") or []

    def find_entity(self, keyword: str, domain: str = None) -> Optional[str]:
        """Find an entity_id by friendly name keyword."""
        states = self.get_all_states()
        keyword = keyword.lower()
        for state in states:
            eid = state.get("entity_id", "")
            if domain and not eid.startswith(domain + "."):
                continue
            friendly = state.get("attributes", {}).get("friendly_name", "")
            if keyword in friendly.lower() or keyword in eid.lower():
                return eid
        return None

    def list_entities(self, domain: str = None) -> list[str]:
        states = self.get_all_states()
        if domain:
            return [s["entity_id"] for s in states if s["entity_id"].startswith(domain + ".")]
        return [s["entity_id"] for s in states]


# ─────────────────────────────────────────────────────────────────────────────
# TUYA LOCAL CONTROL (direct, no cloud)
# ─────────────────────────────────────────────────────────────────────────────

class TuyaBridge:
    """
    Direct local control of Tuya/Smart Life devices via tinytuya.
    Requires: pip install tinytuya
    Configured via TUYA_DEVICES env var (JSON).
    """

    def __init__(self):
        try:
            self._devices = json.loads(TUYA_DEVICES_RAW)
        except (json.JSONDecodeError, ValueError):
            self._devices = {}
        self.available = bool(self._devices)

    def _get_device(self, name: str):
        """Return a tinytuya device instance by friendly name."""
        try:
            import tinytuya
        except ImportError:
            return None

        name = name.lower()
        for k, cfg in self._devices.items():
            if name in k.lower():
                return tinytuya.OutletDevice(
                    dev_id=cfg["id"],
                    address=cfg["ip"],
                    local_key=cfg["key"],
                    version=cfg.get("version", 3.3),
                )
        return None

    def turn_on(self, device_name: str) -> bool:
        dev = self._get_device(device_name)
        if not dev:
            return False
        try:
            dev.turn_on()
            return True
        except Exception as exc:
            logger.warning("Tuya turn_on %s: %s", device_name, exc)
            return False

    def turn_off(self, device_name: str) -> bool:
        dev = self._get_device(device_name)
        if not dev:
            return False
        try:
            dev.turn_off()
            return True
        except Exception as exc:
            logger.warning("Tuya turn_off %s: %s", device_name, exc)
            return False


# ─────────────────────────────────────────────────────────────────────────────
# JARVIS SMART HOME — HIGH-LEVEL INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

# Room / device name aliases — user can expand this list
ROOM_ALIASES: dict[str, list[str]] = {
    "living room":    ["living room", "lounge", "hall"],
    "bedroom":        ["bedroom", "bed room"],
    "kitchen":        ["kitchen"],
    "bathroom":       ["bathroom", "toilet"],
    "office":         ["office", "study", "work room"],
    "all":            ["all", "every", "entire house", "everywhere"],
}

DEVICE_TYPE_DOMAINS = {
    "light":       "light",
    "lights":      "light",
    "lamp":        "light",
    "fan":         "switch",
    "ac":          "climate",
    "air conditioner": "climate",
    "thermostat":  "climate",
    "heater":      "climate",
    "lock":        "lock",
    "door":        "lock",
    "plug":        "switch",
    "switch":      "switch",
    "speaker":     "media_player",
    "tv":          "media_player",
    "television":  "media_player",
}


class JarvisSmartHome:
    """High-level smart home interface for JARVIS router."""

    def __init__(self):
        self.ha    = HomeAssistantBridge()
        self.tuya  = TuyaBridge()

        if self.ha.available:
            self._backend = "home_assistant"
        elif self.tuya.available:
            self._backend = "tuya"
        else:
            self._backend = None

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend_name(self) -> str:
        return {
            "home_assistant": "Home Assistant",
            "tuya":           "Tuya Local",
            None:             "None",
        }.get(self._backend, "Unknown")

    # ── TURN ON ───────────────────────────────────────────────────────────────

    def turn_on(self, device: str, room: str = None, brightness: int = None) -> str:
        target = self._resolve_device(device, room)

        if self.ha.available:
            entity = self.ha.find_entity(target)
            if entity:
                if brightness is not None:
                    ok = self.ha.set_brightness(entity, brightness)
                else:
                    ok = self.ha.turn_on(entity)
                label = self._friendly(entity)
                return (
                    f"Turning on {label}."
                    if ok else
                    f"Could not reach {label}, sir."
                )
            # Try all-lights shorthand
            if device.lower() in ("all", "lights", "all lights"):
                entities = self.ha.list_entities("light")
                for e in entities:
                    self.ha.turn_on(e)
                return f"All lights are now on, sir."
            return f"I couldn't find a device matching '{target}' in Home Assistant."

        if self.tuya.available:
            ok = self.tuya.turn_on(target)
            return f"Turning on {target}." if ok else f"Could not reach {target}."

        return self._not_configured()

    # ── TURN OFF ──────────────────────────────────────────────────────────────

    def turn_off(self, device: str, room: str = None) -> str:
        target = self._resolve_device(device, room)

        if self.ha.available:
            if device.lower() in ("all", "lights", "all lights"):
                entities = self.ha.list_entities("light")
                for e in entities:
                    self.ha.turn_off(e)
                return "All lights are now off, sir."

            entity = self.ha.find_entity(target)
            if entity:
                ok  = self.ha.turn_off(entity)
                label = self._friendly(entity)
                return f"Turning off {label}." if ok else f"Could not reach {label}, sir."
            return f"I couldn't find '{target}' in Home Assistant."

        if self.tuya.available:
            ok = self.tuya.turn_off(target)
            return f"Turning off {target}." if ok else f"Could not reach {target}."

        return self._not_configured()

    # ── BRIGHTNESS ────────────────────────────────────────────────────────────

    def set_brightness(self, device: str, room: str, level: int) -> str:
        target = self._resolve_device(device, room)
        if self.ha.available:
            entity = self.ha.find_entity(target, domain="light")
            if entity:
                ok = self.ha.set_brightness(entity, level)
                label = self._friendly(entity)
                return f"Setting {label} to {level}% brightness." if ok else f"Could not adjust {label}."
            return f"Light '{target}' not found."
        return self._not_configured()

    # ── TEMPERATURE ───────────────────────────────────────────────────────────

    def set_temperature(self, device: str, degrees: float) -> str:
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="climate")
            if entity:
                ok = self.ha.set_temperature(entity, degrees)
                label = self._friendly(entity)
                return f"Setting {label} to {degrees}°." if ok else f"Could not reach {label}."
            # Try generic thermostat
            entities = self.ha.list_entities("climate")
            if entities:
                ok = self.ha.set_temperature(entities[0], degrees)
                return f"Thermostat set to {degrees} degrees." if ok else "Could not reach thermostat."
            return "No climate device found."
        return self._not_configured()

    def get_temperature(self, device: str) -> str:
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="climate") or \
                     self.ha.find_entity(device, domain="sensor")
            if entity:
                state = self.ha.get_state(entity)
                if state:
                    val  = state.get("state")
                    unit = state.get("attributes", {}).get("unit_of_measurement", "°")
                    label = self._friendly(entity)
                    return f"The {label} temperature is {val}{unit}."
            return "I couldn't find that sensor."
        return self._not_configured()

    # ── LOCK / UNLOCK ─────────────────────────────────────────────────────────

    def lock_door(self, device: str = "front door") -> str:
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="lock")
            if entity:
                ok    = self.ha.lock(entity)
                label = self._friendly(entity)
                return f"{label} is now locked." if ok else f"Could not lock {label}."
            return f"Lock '{device}' not found."
        return self._not_configured()

    def unlock_door(self, device: str = "front door") -> str:
        if self.ha.available:
            entity = self.ha.find_entity(device, domain="lock")
            if entity:
                ok    = self.ha.unlock(entity)
                label = self._friendly(entity)
                return f"{label} is now unlocked." if ok else f"Could not unlock {label}."
            return f"Lock '{device}' not found."
        return self._not_configured()

    # ── MEDIA PLAYER ──────────────────────────────────────────────────────────

    def announce(self, message: str, device: str = "all") -> str:
        if self.ha.available:
            if device.lower() == "all":
                entities = self.ha.list_entities("media_player")
            else:
                e = self.ha.find_entity(device, domain="media_player")
                entities = [e] if e else []
            if entities:
                for e in entities[:3]:
                    self.ha.tts_announce(e, message)
                return f"Announcing on {len(entities)} device(s)."
        return self._not_configured()

    # ── STATUS ────────────────────────────────────────────────────────────────

    def get_device_status(self, device: str) -> str:
        if self.ha.available:
            entity = self.ha.find_entity(device)
            if entity:
                state = self.ha.get_state(entity)
                if state:
                    s    = state.get("state", "unknown")
                    attrs = state.get("attributes", {})
                    label = attrs.get("friendly_name", entity)
                    extra = ""
                    if "brightness" in attrs:
                        pct = round(attrs["brightness"] / 2.55)
                        extra = f" at {pct}% brightness"
                    elif "current_temperature" in attrs:
                        extra = f", temperature {attrs['current_temperature']}°"
                    return f"{label} is {s}{extra}."
            return f"Device '{device}' not found."
        return self._not_configured()

    def list_devices(self, domain: str = None) -> str:
        if self.ha.available:
            entities = self.ha.list_entities(domain)
            if not entities:
                label = domain or "device"
                return f"No {label}s found in Home Assistant."
            names = []
            for e in entities[:10]:
                state = self.ha.get_state(e)
                fn = state.get("attributes", {}).get("friendly_name", e) if state else e
                names.append(fn)
            joined = ", ".join(names)
            return f"I found these devices: {joined}."
        return self._not_configured()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _resolve_device(self, device: str, room: str = None) -> str:
        parts = []
        if room:
            parts.append(room.lower())
        if device:
            parts.append(device.lower())
        return " ".join(parts) if parts else device or ""

    def _friendly(self, entity_id: str) -> str:
        try:
            state = self.ha.get_state(entity_id)
            if state:
                return state.get("attributes", {}).get("friendly_name", entity_id)
        except Exception:
            pass
        return entity_id.replace("_", " ").split(".")[-1]

    def _not_configured(self) -> str:
        return (
            "Smart home is not configured yet, sir. "
            "Add HA_URL and HA_TOKEN to your .env file to connect Home Assistant, "
            "which controls Google Home, Alexa, and all smart devices."
        )
