import whisper
import imageio_ffmpeg
import os

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]


_model = None


def get_whisper_model():
    global _model
    if _model is None:
        _model = whisper.load_model("small")
    return _model


def transcribe_audio(audio_path):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at: {audio_path}")

    model = get_whisper_model()

    result = model.transcribe(
        audio_path,
        fp16=False
    )

    return result.get("text", "").strip()
