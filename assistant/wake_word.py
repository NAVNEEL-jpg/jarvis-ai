import queue

import numpy as np
import sounddevice as sd
from openwakeword import Model


SAMPLE_RATE = 16000
CHUNK_SIZE = 1280

WAKE_MODEL = "hey_jarvis"
WAKE_THRESHOLD = 0.5


class JarvisWakeWord:
    def __init__(self):
        print("Loading wake-word model...")

        self.model = Model(
            wakeword_models=[WAKE_MODEL],
            inference_framework="onnx",
        )

        print("Wake-word model loaded.")
        print(f'Activation phrase: "Hey Jarvis"')

    def wait(self):
        """
        Blocks until the wake word is detected.
        """

        audio_queue = queue.Queue()

        # Reset prediction history before listening.
        self.model.reset()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"Wake-word audio status: {status}")

            # openWakeWord expects 16-bit PCM audio.
            audio = np.clip(
                indata.reshape(-1),
                -1.0,
                1.0,
            )

            audio = (
                audio * 32767
            ).astype(np.int16)

            audio_queue.put(audio)

        print()
        print('Waiting for "Hey Jarvis"...')

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_SIZE,
            callback=callback,
        ):
            while True:
                audio = audio_queue.get()

                predictions = self.model.predict(audio)

                score = predictions.get(
                    WAKE_MODEL,
                    0.0,
                )

                if score >= WAKE_THRESHOLD:
                    print(
                        f"Wake word detected! "
                        f"(score={score:.2f})"
                    )

                    return True


if __name__ == "__main__":
    wake_word = JarvisWakeWord()

    while True:
        wake_word.wait()

        print("JARVIS ACTIVATED.")