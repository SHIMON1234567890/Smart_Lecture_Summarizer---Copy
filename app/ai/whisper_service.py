import whisper
import imageio_ffmpeg
import os

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]


def transcribe_audio(audio_path):

    model = whisper.load_model("small")

    result = model.transcribe(
        audio_path,
        fp16=False
    )

    return result["text"]