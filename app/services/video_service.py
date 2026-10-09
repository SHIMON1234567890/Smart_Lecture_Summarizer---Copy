import os
import imageio_ffmpeg

try:
    import moviepy.config as mp_config
    mp_config.FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    pass

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    from moviepy import VideoFileClip


def extract_audio(video_path, audio_path):
    os.makedirs(os.path.dirname(os.path.abspath(audio_path)), exist_ok=True)

    video = VideoFileClip(video_path)
    try:
        if video.audio is None:
            raise ValueError(f"No audio stream found in video file '{video_path}'.")

        video.audio.write_audiofile(audio_path)
    finally:
        video.close()
