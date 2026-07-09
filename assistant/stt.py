import os

from faster_whisper import WhisperModel


class JarvisSTT:
    def __init__(
        self,
        model_size="small.en",
        device="cpu",
        compute_type="int8",
    ):
        print(f"Loading Whisper model: {model_size}")
        print(f"Device: {device}")
        print(f"Compute type: {compute_type}")

        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )

            self.device = device

            print("Whisper model loaded successfully.")

        except Exception as error:
            print(f"GPU initialization failed: {error}")
            print("Falling back to CPU...")

            self.model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )

            self.device = "cpu"

            print("Whisper model loaded on CPU.")

    def transcribe(self, audio_path):
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(
                f"Audio file does not exist: {audio_path}"
            )

        print(f"Transcribing: {audio_path}")

        segments, info = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        text_parts = []

        for segment in segments:
            text = segment.text.strip()

            if text:
                text_parts.append(text)

        final_text = " ".join(text_parts).strip()

        print(f"Detected language: {info.language}")
        print(f"Transcription: {final_text}")

        return final_text


if __name__ == "__main__":
    stt = JarvisSTT()

    test_audio = os.path.join(
        os.path.dirname(__file__),
        "test.wav",
    )

    result = stt.transcribe(test_audio)

    print()
    print("FINAL RESULT:")
    print(result)