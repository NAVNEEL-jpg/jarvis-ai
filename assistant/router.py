import re

from memory import JarvisMemory
from smart_home import JarvisSmartHome
from trainer import JarvisTrainer
from tools import JarvisTools


class JarvisRouter:
    def __init__(self, brain):
        self.brain   = brain
        self.tools   = JarvisTools()
        self.memory  = JarvisMemory()
        self.home    = JarvisSmartHome()
        self.trainer = JarvisTrainer()

    def route(self, text):
        normalized = text.lower().strip()

        # Remove trailing punctuation Whisper may add.
        normalized = normalized.rstrip(".?!")

        # ------------------------------------------
        # TRAINED COMMANDS (highest priority)
        # Custom trigger → response pairs set via
        # the Control Panel and stored in Supabase.
        # ------------------------------------------

        trained = self.trainer.find_match(normalized)
        if trained:
            return trained

        # ------------------------------------------
        # MEMORY — STORE A FACT
        # "remember that my wifi password is test"
        # "remember my birthday is July 5"
        # ------------------------------------------

        remember_patterns = [
            r"^remember that (.+)$",
            r"^remember (.+)$",
            r"^store (.+)$",
            r"^save that (.+)$",
            r"^note that (.+)$",
        ]

        for pat in remember_patterns:
            m = re.match(pat, normalized)
            if m:
                fact = m.group(1).strip()
                # Try to detect key=value ("my X is Y")
                kv = re.match(
                    r"(?:my\s+)?(.+?)\s+is\s+(.+)", fact
                )
                if kv:
                    key = kv.group(1).strip()
                    value = kv.group(2).strip()
                else:
                    # Store entire fact under the full text as key
                    key = fact[:60]
                    value = fact

                stored = self.memory.store(key, value)

                if stored:
                    return f"Got it, I'll remember that {key} is {value}."
                else:
                    return (
                        "Memory is not configured yet, sir. "
                        "Add your Supabase credentials to the .env file."
                    )

        # ------------------------------------------
        # MEMORY — RECALL A FACT
        # "what's my wifi password"
        # "what did I tell you about my birthday"
        # "recall my home address"
        # ------------------------------------------

        recall_patterns = [
            r"^(?:what(?:'s| is) my |recall my |what do you know about my |"
            r"what did i tell you about (?:my )?)(.+)$",
            r"^(?:tell me my )(.+)$",
        ]

        for pat in recall_patterns:
            m = re.match(pat, normalized)
            if m:
                query = m.group(1).strip().rstrip(".?!")

                # Try exact key first, then search
                value = self.memory.recall(query)

                if value is None:
                    rows = self.memory.search(query)
                    if rows:
                        value = rows[0]["value"]

                if value:
                    return f"Your {query} is {value}."
                else:
                    if self.memory.available:
                        return (
                            f"I don't have any stored information "
                            f"about {query}, sir."
                        )
                    else:
                        # Fall through to brain for normal answer
                        pass

        # ------------------------------------------
        # SMART HOME — TURN ON
        # "turn on living room lights"
        # "turn on the fan"
        # "switch on bedroom lights at 50 percent"
        # ------------------------------------------

        turn_on_pat = re.match(
            r"(?:turn|switch|put)\s+on\s+(?:the\s+)?"
            r"(?:(?P<room>living room|bedroom|kitchen|bathroom|office|all)\s+)?"
            r"(?P<device>lights?|lamp|fan|ac|tv|television|heater|plug|switch|speaker|all lights?)"
            r"(?:\s+(?:at|to)\s+(?P<brightness>\d+)\s*(?:percent|%))?",
            normalized,
        )
        if turn_on_pat:
            g = turn_on_pat.groupdict()
            b = int(g["brightness"]) if g.get("brightness") else None
            return self.home.turn_on(g["device"], g.get("room"), brightness=b)

        # ------------------------------------------
        # SMART HOME — TURN OFF
        # "turn off the lights"
        # "switch off all lights"
        # ------------------------------------------

        turn_off_pat = re.match(
            r"(?:turn|switch|put)\s+off\s+(?:the\s+)?"
            r"(?:(?P<room>living room|bedroom|kitchen|bathroom|office|all)\s+)?"
            r"(?P<device>lights?|lamp|fan|ac|tv|television|heater|plug|switch|speaker|all lights?)",
            normalized,
        )
        if turn_off_pat:
            g = turn_off_pat.groupdict()
            return self.home.turn_off(g["device"], g.get("room"))

        # ------------------------------------------
        # SMART HOME — BRIGHTNESS
        # "set living room lights to 70 percent"
        # "dim bedroom lights to 30"
        # ------------------------------------------

        brightness_pat = re.match(
            r"(?:set|dim|brighten)\s+"
            r"(?:(?P<room>living room|bedroom|kitchen|bathroom|office)\s+)?"
            r"(?P<device>lights?|lamp)\s+"
            r"(?:to|at)\s+(?P<level>\d+)\s*(?:percent|%)?",
            normalized,
        )
        if brightness_pat:
            g = brightness_pat.groupdict()
            return self.home.set_brightness(
                g["device"], g.get("room", ""), int(g["level"])
            )

        # ------------------------------------------
        # SMART HOME — TEMPERATURE
        # "set thermostat to 22 degrees"
        # "set ac to 20"
        # "what is the living room temperature"
        # ------------------------------------------

        set_temp_pat = re.match(
            r"(?:set|put)\s+"
            r"(?:the\s+)?(?P<device>thermostat|ac|air conditioner|heater|climate)\s+"
            r"(?:to|at)\s+(?P<degrees>\d+(?:\.\d+)?)\s*(?:degrees?|°)?",
            normalized,
        )
        if set_temp_pat:
            g = set_temp_pat.groupdict()
            return self.home.set_temperature(g["device"], float(g["degrees"]))

        get_temp_pat = re.match(
            r"(?:what(?:'s| is) the\s+)?"
            r"(?P<room>living room|bedroom|kitchen|bathroom|office|home)?\s*"
            r"(?:temperature|temp|heat)\??",
            normalized,
        )
        if get_temp_pat and any(
            w in normalized for w in ("temperature", "temp", "how hot", "how cold", "warm")
        ):
            g = get_temp_pat.groupdict()
            return self.home.get_temperature(g.get("room") or "thermostat")

        # ------------------------------------------
        # SMART HOME — LOCK / UNLOCK
        # "lock the front door"
        # "unlock front door"
        # ------------------------------------------

        lock_pat = re.match(
            r"(?P<action>lock|unlock)\s+(?:the\s+)?(?P<device>[\w\s]+door|[\w\s]+lock|door)",
            normalized,
        )
        if lock_pat:
            g = lock_pat.groupdict()
            if g["action"] == "lock":
                return self.home.lock_door(g["device"])
            else:
                return self.home.unlock_door(g["device"])

        # ------------------------------------------
        # SMART HOME — DEVICE STATUS
        # "what is the living room light status"
        # "is the bedroom light on"
        # ------------------------------------------

        status_pat = re.match(
            r"(?:what(?:'s| is) the\s+)?(?P<device>[\w\s]+)\s+"
            r"(?:status|state|on\??|off\??|running|working)",
            normalized,
        )
        if status_pat and any(
            w in normalized for w in ("light", "fan", "ac", "heater", "lock", "door", "plug", "switch")
        ):
            return self.home.get_device_status(status_pat.group("device").strip())

        # ------------------------------------------
        # SMART HOME — LIST DEVICES
        # "list my lights"
        # "show all smart devices"
        # ------------------------------------------

        if re.match(r"(?:list|show|what are)\s+(?:my\s+|all\s+)?(?:smart\s+)?(?:devices?|lights?|switches?)", normalized):
            m = re.search(r"(lights?|switches?|locks?|climate|media)", normalized)
            domain = None
            if m:
                d = m.group(1).rstrip("s")
                domain = {"light": "light", "switch": "switch", "lock": "lock",
                          "climat": "climate", "media": "media_player"}.get(d)
            return self.home.list_devices(domain)

        # ------------------------------------------
        # SMART HOME — ANNOUNCE / TTS ON SPEAKER
        # "announce dinner is ready"
        # "say hello on kitchen speaker"
        # ------------------------------------------

        announce_pat = re.match(
            r"(?:announce|say|broadcast|tell everyone)\s+(?:that\s+)?(?P<msg>.+?)(?:\s+on\s+(?P<device>[\w\s]+))?$",
            normalized,
        )
        if announce_pat:
            g = announce_pat.groupdict()
            return self.home.announce(g["msg"], g.get("device") or "all")

        # ------------------------------------------
        # OPEN APPLICATIONS
        # ------------------------------------------

        app_aliases = {
            "notepad": "notepad",
            "calculator": "calculator",
            "calc": "calculator",
            "paint": "paint",
            "file explorer": "file explorer",
            "explorer": "file explorer",
            "chrome": "chrome",
            "google chrome": "google chrome",
            "cmd": "cmd",
            "command prompt": "command prompt",
            "terminal": "cmd",
            "task manager": "task manager",
            "taskmgr": "task manager",
            "snipping tool": "snipping tool",
            "wordpad": "wordpad",
            "device manager": "device manager",
            "settings": "settings",
            "control panel": "settings",
        }

        if normalized.startswith("open "):
            requested = normalized.removeprefix("open ").strip()

            if requested in app_aliases:
                return self.tools.open_app(app_aliases[requested])

        # ------------------------------------------
        # SEARCH GOOGLE OR YOUTUBE
        # ------------------------------------------

        # Google Search
        g_search_pat = re.match(
            r"^(?:search\s+(?:google\s+for|for)?\s*|google\s+)(?P<query>.+)$",
            normalized
        )
        if g_search_pat and not normalized.startswith("open "):
            # Ensure it's not a youtube search request
            query = g_search_pat.group("query").strip()
            if not query.startswith("on youtube") and not query.endswith("on youtube") and not query.startswith("youtube "):
                return self.tools.search_google(query)

        # YouTube Search
        yt_search_pat = re.match(
            r"^(?:search\s+(?:youtube\s+for|for)?\s*|youtube\s+)(?P<query>.+)$",
            normalized
        )
        if yt_search_pat:
            query = yt_search_pat.group("query").strip()
            return self.tools.search_youtube(query)

        # Match "search [query] on google"
        g_on_pat = re.match(r"^search\s+(?P<query>.+?)\s+on\s+google$", normalized)
        if g_on_pat:
            return self.tools.search_google(g_on_pat.group("query").strip())

        # Match "search [query] on youtube"
        yt_on_pat = re.match(r"^search\s+(?P<query>.+?)\s+on\s+youtube$", normalized)
        if yt_on_pat:
            return self.tools.search_youtube(yt_on_pat.group("query").strip())

        # ------------------------------------------
        # OPEN WEBSITES & DOMAINS
        # ------------------------------------------

        website_aliases = {
            "youtube": "youtube",
            "google": "google",
            "spotify": "spotify",
        }

        if normalized.startswith("open "):
            requested = normalized.removeprefix("open ").strip()

            # If it's a known website or it looks like a domain name
            if requested in website_aliases or "." in requested or ":" in requested:
                return self.tools.open_website(
                    website_aliases.get(requested, requested)
                )
            
            # If it's not an app, assume it is a website name and let open_website guess it
            if requested not in app_aliases:
                return self.tools.open_website(requested)

        # ------------------------------------------
        # TIME
        # ------------------------------------------

        time_phrases = (
            "what time is it",
            "tell me the time",
            "current time",
        )

        if any(phrase in normalized for phrase in time_phrases):
            return self.tools.get_time()

        # ------------------------------------------
        # DATE
        # ------------------------------------------

        date_phrases = (
            "what is the date",
            "what's the date",
            "tell me the date",
            "today's date",
            "what day is it",
        )

        if any(phrase in normalized for phrase in date_phrases):
            return self.tools.get_date()

        # ------------------------------------------
        # SYSTEM STATUS
        # ------------------------------------------

        status_phrases = (
            "system status",
            "check system status",
            "how is my computer",
            "cpu usage",
            "memory usage",
            "battery level",
            "how much battery",
            "ram usage",
        )

        # ------------------------------------------
        # WEATHER
        # ------------------------------------------
        weather_loc_pat = re.match(
            r"^(?:what(?:'s| is) the )?weather\s+(?:in|at|for)\s+(?P<loc>.+)$",
            normalized
        )
        if weather_loc_pat:
            return self.tools.get_weather(weather_loc_pat.group("loc").strip())

        weather_phrases = (
            "weather", "how is the weather", "todays weather", "temperature outside", "is it raining", "weather forecast"
        )
        if any(phrase in normalized for phrase in weather_phrases):
            return self.tools.get_weather()

        # ------------------------------------------
        # NEWS HEADLINES
        # ------------------------------------------
        news_phrases = ("news", "latest news", "headlines", "what's in the news", "tell me the news")
        if any(phrase in normalized for phrase in news_phrases):
            return self.tools.get_news()

        # ------------------------------------------
        # WORD DEFINITION
        # ------------------------------------------
        def_pat = re.match(
            r"^(?:define|what is the meaning of|what does)\s+(?P<word>\w+)(?:\s+mean)?$",
            normalized
        )
        if def_pat:
            return self.tools.define_word(def_pat.group("word").strip())

        # ------------------------------------------
        # CURRENCY CONVERSION
        # ------------------------------------------
        curr_pat = re.match(
            r"^(?:convert|how much is)\s+(?P<amt>\d+(?:\.\d+)?)\s*(?P<from>[a-zA-Z]{3})\s+(?:to|in)\s+(?P<to>[a-zA-Z]{3})$",
            normalized
        )
        if curr_pat:
            g = curr_pat.groupdict()
            return self.tools.convert_currency(float(g["amt"]), g["from"], g["to"])

        if any(phrase in normalized for phrase in status_phrases):
            return self.tools.get_system_status()

        # ------------------------------------------
        # FALLBACK — LOCAL AI WITH MEMORY CONTEXT
        # ------------------------------------------

        memory_context = None

        if self.memory.available:
            # Do a quick search to see if any stored facts are
            # relevant to the question.
            words = [w for w in normalized.split() if len(w) > 3]

            for word in words[:4]:
                rows = self.memory.search(word)
                if rows:
                    snippets = [
                        f"{r['key']} = {r['value']}"
                        for r in rows[:3]
                    ]
                    memory_context = "; ".join(snippets)
                    break

        answer = self.brain.ask(text, memory_context=memory_context)

        # Log conversation to Supabase if available.
        self.memory.log("user", text)
        if answer:
            self.memory.log("assistant", answer)

        return answer