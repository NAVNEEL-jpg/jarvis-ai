import re

from memory import JarvisMemory
from tools import JarvisTools


class JarvisRouter:
    def __init__(self, brain):
        self.brain = brain
        self.tools = JarvisTools()
        self.memory = JarvisMemory()

    def route(self, text):
        normalized = text.lower().strip()

        # Remove trailing punctuation Whisper may add.
        normalized = normalized.rstrip(".?!")

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
        # OPEN APPLICATIONS
        # ------------------------------------------

        app_aliases = {
            "notepad": "notepad",
            "calculator": "calculator",
            "calc": "calculator",
            "paint": "paint",
            "file explorer": "file explorer",
            "explorer": "file explorer",
        }

        if normalized.startswith("open "):
            requested = normalized.removeprefix("open ").strip()

            if requested in app_aliases:
                return self.tools.open_app(app_aliases[requested])

        # ------------------------------------------
        # OPEN WEBSITES
        # ------------------------------------------

        website_aliases = {
            "youtube": "youtube",
            "google": "google",
            "spotify": "spotify",
        }

        if normalized.startswith("open "):
            requested = normalized.removeprefix("open ").strip()

            if requested in website_aliases:
                return self.tools.open_website(
                    website_aliases[requested]
                )

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