import os
import shutil

whisper = None

try:
    import whisper
except ImportError:
    pass

try:
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(ffmpeg_exe):
        try:
            shutil.copyfile(ffmpeg_path, ffmpeg_exe)
        except Exception as copy_err:
            pass
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass



_model = None


def get_whisper_model():
    global _model
    if _model is None:
        try:
            _model = whisper.load_model("small")
        except Exception as e:
            print(f"Failed to load 'small' Whisper model ({e}), falling back to 'base' model...")
            _model = whisper.load_model("base")
    return _model



def transcribe_audio(audio_path):
    if whisper is None:
        raise ImportError("whisper is not installed. Please run: pip install openai-whisper")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at: {audio_path}")


    model = get_whisper_model()

    result = model.transcribe(
        audio_path,
        fp16=False
    )

    return result.get("text", "").strip()
