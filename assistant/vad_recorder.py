import os
import queue
import time
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf
import torch

from silero_vad import load_silero_vad, get_speech_timestamps


SAMPLE_RATE = 16000

# Silero VAD works well with 512-sample chunks at 16 kHz.
CHUNK_SIZE = 512

# Wait up to 10 seconds for speech to begin.
MAX_WAIT_SECONDS = 10.0

# Stop after this much continuous silence.
END_SILENCE_SECONDS = 1.0

# Safety limit.
MAX_RECORD_SECONDS = 60.0

# Keep audio immediately before speech begins.
PRE_ROLL_SECONDS = 0.5

# Silero speech probability threshold.
SPEECH_THRESHOLD = 0.5


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "vad_test.wav",
)


class SileroRecorder:

    def __init__(self):

        print("Loading Silero VAD...")

        self.model = load_silero_vad()

        print("Silero VAD loaded successfully.")


    def is_speech(self, audio_chunk):

        # Convert microphone chunk to mono float32.
        audio = np.asarray(
            audio_chunk,
            dtype=np.float32,
        ).reshape(-1)

        tensor = torch.from_numpy(audio)

        with torch.no_grad():

            speech_probability = self.model(
                tensor,
                SAMPLE_RATE,
            ).item()

        return (
            speech_probability >= SPEECH_THRESHOLD,
            speech_probability,
        )


    def record(self, output_file=OUTPUT_FILE):

        print()
        print("Listening... Speak naturally.")

        audio_queue = queue.Queue()

        pre_roll_chunks = deque(
            maxlen=max(
                1,
                int(
                    PRE_ROLL_SECONDS
                    * SAMPLE_RATE
                    / CHUNK_SIZE
                ),
            )
        )

        recorded_chunks = []

        speech_started = False

        silence_start = None

        listening_start = time.perf_counter()


        def callback(
            indata,
            frames,
            time_info,
            status,
        ):

            if status:
                print(f"Audio status: {status}")

            audio_queue.put(
                indata.copy()
            )


        # Reset Silero's internal state before every recording.
        self.model.reset_states()


        try:

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):

                while True:

                    chunk = audio_queue.get()

                    now = time.perf_counter()

                    elapsed = (
                        now - listening_start
                    )

                    speech, probability = self.is_speech(
                        chunk
                    )


                    # ----------------------------------
                    # Waiting for speech
                    # ----------------------------------

                    if not speech_started:

                        pre_roll_chunks.append(
                            chunk
                        )

                        if speech:

                            speech_started = True

                            recorded_chunks.extend(
                                list(pre_roll_chunks)
                            )

                            pre_roll_chunks.clear()

                            recorded_chunks.append(
                                chunk
                            )

                            silence_start = None

                            print(
                                "Speech detected "
                                f"(probability={probability:.2f})"
                            )


                        elif elapsed >= MAX_WAIT_SECONDS:

                            print("No speech detected.")

                            return None


                    # ----------------------------------
                    # Recording speech
                    # ----------------------------------

                    else:

                        recorded_chunks.append(
                            chunk
                        )


                        if speech:

                            silence_start = None


                        else:

                            if silence_start is None:

                                silence_start = now


                            silence_duration = (
                                now - silence_start
                            )


                            if (
                                silence_duration
                                >= END_SILENCE_SECONDS
                            ):

                                print(
                                    "End of speech detected."
                                )

                                break


                    # ----------------------------------
                    # Safety timeout
                    # ----------------------------------

                    if elapsed >= MAX_RECORD_SECONDS:

                        print(
                            "Maximum recording time reached."
                        )

                        break


        except Exception as error:

            print(
                f"Recording error: {error}"
            )

            return None


        if not recorded_chunks:

            print("No usable audio recorded.")

            return None


        audio = np.concatenate(
            recorded_chunks,
            axis=0,
        )


        sf.write(
            output_file,
            audio,
            SAMPLE_RATE,
        )


        duration = (
            len(audio)
            / SAMPLE_RATE
        )


        print(
            f"Saved: {output_file}"
        )

        print(
            f"Audio duration: {duration:.2f}s"
        )


        return output_file


if __name__ == "__main__":

    recorder = SileroRecorder()

    print()
    print("Silero VAD recorder ready.")

    input(
        "Press ENTER, then speak > "
    )

    recorder.record()