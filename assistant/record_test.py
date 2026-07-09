import os

import sounddevice as sd
import soundfile as sf


SAMPLE_RATE = 16000
DURATION_SECONDS = 5


output_file = os.path.join(
    os.path.dirname(__file__),
    "test.wav",
)

print()
print("Speak now. Recording for 5 seconds...")

audio = sd.rec(
    int(DURATION_SECONDS * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
)

sd.wait()

sf.write(
    output_file,
    audio,
    SAMPLE_RATE,
)

print(f"Recording saved to: {output_file}")