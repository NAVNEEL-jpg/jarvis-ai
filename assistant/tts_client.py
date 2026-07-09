import requests


class JarvisTTSClient:
    def __init__(
        self,
        server_url="http://127.0.0.1:8765",
        timeout=120,
    ):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout

    def health(self):
        response = requests.get(
            f"{self.server_url}/health",
            timeout=5,
        )

        response.raise_for_status()
        return response.json()

    def speak(self, text):
        if not text.strip():
            return

        print("Sending response to JARVIS voice...")

        response = requests.post(
            f"{self.server_url}/speak",
            json={"text": text},
            timeout=self.timeout,
        )

        response.raise_for_status()

        print("JARVIS finished speaking.")


if __name__ == "__main__":
    client = JarvisTTSClient()

    print(client.health())

    client.speak(
        "Good evening, sir. The voice interface is connected."
    )