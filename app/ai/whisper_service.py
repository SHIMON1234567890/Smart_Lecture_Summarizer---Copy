import os

import imageio_ffmpeg
import whisper

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]

_model = None


def _get_model():
    # Loading Whisper takes several seconds; do it once per process.
    global _model
    if _model is None:
        _model = whisper.load_model("small")
    return _model


def transcribe_audio(audio_path):

    result = _get_model().transcribe(
        audio_path,
        fp16=False
    )

    return result["text"].strip()
