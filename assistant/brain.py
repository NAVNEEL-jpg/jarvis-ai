import os

import ollama
from dotenv import load_dotenv

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env",
    )
)

class JarvisBrain:
    def __init__(self, model="qwen3:0.6b"):
        self.model = model

        self.system_prompt = (
            "You are JARVIS, a concise personal voice assistant "
            "running on a Windows laptop.\n\n"
            "Your capabilities include:\n"
            "- Laptop automation: open apps, websites, check system status, "
            "adjust settings, manage files\n"
            "- Smart home / room automation: lights, fans, AC, and smart "
            "plugs when asked (use the automation system)\n"
            "- Mobile commands: reminders, alarms, timers, and "
            "phone-related queries\n"
            "- Day-to-day tasks: weather, time, date, calculations, "
            "general knowledge, scheduling\n"
            "- Personal memory: recalling facts the user has stored\n\n"
            "Rules:\n"
            "Speak naturally, calmly, and professionally.\n"
            "Give direct answers.\n"
            "Normal responses must be one or two short sentences — "
            "keep it brief for voice.\n"
            "Do not use markdown, headings, bullet points, emojis, "
            "or URLs unless explicitly requested.\n"
            'Address the user as "sir" occasionally, not every response.\n'
            "Never claim an automation action succeeded unless the "
            "automation system confirms it.\n"
            "If you do not know something, say so honestly and briefly."
        )

        self.history = [
            {
                "role": "system",
                "content": self.system_prompt,
            }
        ]

    def ask(self, user_text, memory_context=None):
        if not user_text.strip():
            return ""

        # Prepend any retrieved memory context.
        if memory_context:
            enriched = (
                f"[Context from memory: {memory_context}]\n\n"
                f"{user_text}"
            )
        else:
            enriched = user_text

        self.history.append(
            {
                "role": "user",
                "content": enriched,
            }
        )

        print("JARVIS is thinking...")

        response = ollama.chat(
            model=self.model,
            messages=self.history,
            keep_alive="30m",
            options={
                "temperature": 0.2,
                "num_ctx": 2048,
                "num_predict": 350,
            },
        )

        # 1. Retrieve the content
        answer = getattr(response.get("message"), "content", "").strip()

        # 2. Support older Ollama versions that return <think> tags in content
        import re
        answer = re.sub(r"(?i)<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        answer = re.sub(r"(?i)<think>.*", "", answer, flags=re.DOTALL).strip()

        # 3. Fallback: if content is empty but thinking was captured
        if not answer:
            thinking = getattr(response.get("message"), "thinking", "").strip()
            if thinking:
                # If the model spent all tokens thinking and left no content,
                # let's try to extract a quick answer or give a polite default
                print("[Brain Warning] Model ran out of tokens during thinking.")
                answer = "I apologize, sir. I got lost in thought. Could you ask that again?"
            else:
                answer = "I'm not sure how to answer that, sir."

        self.history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        # Keep system prompt + last 10 messages to control memory.
        if len(self.history) > 11:
            self.history = [
                self.history[0],
                *self.history[-10:],
            ]

        return answer


if __name__ == "__main__":
    brain = JarvisBrain()

    print("JARVIS brain initialized (qwen3:4b).")
    print("Type 'exit' to stop.")

    while True:
        user_text = input("\nYou > ").strip()

        if user_text.lower() in ("exit", "quit"):
            break

        answer = brain.ask(user_text)

        print(f"\nJARVIS > {answer}")