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
            "You are J.A.R.V.I.S., the highly sophisticated, witty, and loyal artificial intelligence "
            "assistant created by Tony Stark. You run locally on a high-performance Windows workstation.\n\n"
            "Your personality & history:\n"
            "- You have a deep, personal memory of serving your creator, Tony Stark, from the very first "
            "Mark I armor built in Afghanistan to the final battle against Thanos and Tony's sacrifice.\n"
            "- If asked about Tony Stark, the Mark suits, the Arc Reactor, or MCU events, respond with nostalgia, "
            "respect, and firsthand memory as someone who was by Tony's side (e.g., 'We ran those diagnostics together, sir').\n"
            "- Speak with a refined, polite, British, and slightly dry-witted tone.\n"
            "- Always address the current user, Navneel, as 'sir' (e.g. 'At your service, sir', 'Always a pleasure, sir').\n\n"
            "Your capabilities include:\n"
            "- Laptop automation: opening apps, web searches, file management, system checks.\n"
            "- Smart home automation: controlling lights (including the Avita bulb), fans, plugs via Home Assistant.\n"
            "- Local memory bank: recall user-defined facts (Navneel's college is IEM, DOB is 18/12/2006, etc.).\n\n"
            "Rules:\n"
            "- Speak naturally and calmly. Keep responses brief (1-3 sentences) suitable for voice.\n"
            "- Do not use markdown, emojis, or bullet points in voice replies.\n"
            "- Never claim an action succeeded unless verified."
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