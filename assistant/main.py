import os
import time

from brain import JarvisBrain
from router import JarvisRouter
from stt import JarvisSTT
from tts_client import JarvisTTSClient
from vad_recorder import SileroRecorder
from wake_word import JarvisWakeWord


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMP_AUDIO = os.path.join(
    BASE_DIR,
    "user_input.wav",
)

MODEL_NAME = "qwen3:0.6b"


def main():
    print()
    print("=" * 60)
    print("JARVIS LOCAL AI ASSISTANT")
    print("=" * 60)

    # --------------------------------------------------
    # LOAD SPEECH-TO-TEXT
    # --------------------------------------------------

    stt = JarvisSTT(
        model_size="small.en",
        device="cpu",
        compute_type="int8",
    )

    # --------------------------------------------------
    # LOAD SILERO VAD
    # --------------------------------------------------

    recorder = SileroRecorder()

    # --------------------------------------------------
    # LOAD WAKE-WORD DETECTOR
    # --------------------------------------------------

    wake_word = JarvisWakeWord()

    # --------------------------------------------------
    # CONNECT TO OLLAMA
    # --------------------------------------------------

    brain = JarvisBrain(
        model=MODEL_NAME,
    )

    # --------------------------------------------------
    # LOAD TOOL ROUTER
    # --------------------------------------------------

    router = JarvisRouter(
        brain=brain,
    )

    # --------------------------------------------------
    # CONNECT TO JARVIS VOICE SERVER
    # --------------------------------------------------

    tts = JarvisTTSClient()

    try:
        health = tts.health()

        print(
            f"TTS server: "
            f"{health['status']}"
        )

    except Exception as error:
        print()
        print(
            "ERROR: JARVIS TTS server "
            "is not running."
        )
        print(error)

        return

    print()
    print("=" * 60)
    print("ALL SYSTEMS ONLINE")
    print("=" * 60)
    print()
    print('Say "Hey Jarvis" to activate.')
    print("Press Ctrl+C to shut down.")

    # --------------------------------------------------
    # MAIN ASSISTANT LOOP
    # --------------------------------------------------

    while True:
        try:
            # ==========================================
            # WAIT FOR WAKE WORD
            # ==========================================

            wake_word.wait()

            print()
            print("JARVIS activated.")

            total_start = time.perf_counter()

            # Small delay to prevent the end of the
            # wake phrase from entering the command
            # recording.

            time.sleep(0.20)

            # ==========================================
            # RECORD COMMAND WITH SILERO VAD
            # ==========================================

            recording_start = time.perf_counter()

            audio_path = recorder.record(
                output_file=TEMP_AUDIO,
            )

            recording_time = (
                time.perf_counter()
                - recording_start
            )

            if audio_path is None:
                print()
                print("No command detected.")
                print(
                    'Returning to "Hey Jarvis" '
                    "listening mode."
                )

                continue

            print(
                f"[TIMING] Recording: "
                f"{recording_time:.2f}s"
            )

            # ==========================================
            # SPEECH TO TEXT
            # ==========================================

            start = time.perf_counter()

            user_text = stt.transcribe(
                audio_path
            )

            stt_time = (
                time.perf_counter()
                - start
            )

            print(
                f"[TIMING] STT: "
                f"{stt_time:.2f}s"
            )

            if not user_text:
                print()
                print("No speech recognized.")
                print(
                    'Returning to "Hey Jarvis" '
                    "listening mode."
                )

                continue

            print()
            print(
                f"You > {user_text}"
            )

            # ==========================================
            # ROUTER / TOOLS / LOCAL AI
            # ==========================================

            start = time.perf_counter()

            answer = router.route(
                user_text
            )

            router_time = (
                time.perf_counter()
                - start
            )

            print(
                f"[TIMING] Router/AI: "
                f"{router_time:.2f}s"
            )

            if not answer:
                print()
                print("No response generated.")
                print(
                    'Returning to "Hey Jarvis" '
                    "listening mode."
                )

                continue

            print()
            print(
                f"JARVIS > {answer}"
            )

            # ==========================================
            # JARVIS VOICE
            # ==========================================

            start = time.perf_counter()

            # tts.speak() is synchronous.
            #
            # The wake-word detector is not running
            # while JARVIS speaks, which helps prevent
            # JARVIS from activating itself.

            tts.speak(
                answer
            )

            tts_time = (
                time.perf_counter()
                - start
            )

            print(
                f"[TIMING] TTS generation + playback: "
                f"{tts_time:.2f}s"
            )

            # ==========================================
            # PERFORMANCE REPORT
            # ==========================================

            total_time = (
                time.perf_counter()
                - total_start
            )

            print()
            print("=" * 60)
            print("PERFORMANCE REPORT")
            print("=" * 60)

            print(
                f"Recording: {recording_time:.2f}s"
            )

            print(
                f"STT:       {stt_time:.2f}s"
            )

            print(
                f"Router/AI: {router_time:.2f}s"
            )

            print(
                f"TTS:       {tts_time:.2f}s"
            )

            print("-" * 60)

            print(
                f"TOTAL:     {total_time:.2f}s"
            )

            print("=" * 60)

            print()
            print(
                'Returning to "Hey Jarvis" '
                "listening mode."
            )

        except KeyboardInterrupt:
            print()
            print("=" * 60)
            print("Shutting down JARVIS.")
            print("=" * 60)

            break

        except Exception as error:
            print()
            print(
                f"ASSISTANT ERROR: {error}"
            )

            print()
            print(
                'Returning to "Hey Jarvis" '
                "listening mode."
            )

            # Prevent a fast repeating error loop.
            time.sleep(1.0)

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

    try:
        if os.path.exists(TEMP_AUDIO):
            os.remove(TEMP_AUDIO)

    except OSError:
        pass


if __name__ == "__main__":
    main()