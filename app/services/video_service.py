import os

VideoFileClip = None

try:
    import imageio_ffmpeg
    try:
        import moviepy.config as mp_config
        mp_config.FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
except Exception:
    pass

try:
    from moviepy import VideoFileClip
except Exception:
    try:
        from moviepy.editor import VideoFileClip
    except Exception:
        VideoFileClip = None


def extract_audio(video_path, audio_path):
    if VideoFileClip is None:
        raise ImportError(
            "moviepy is not installed or the virtual environment is not active. "
            "Please run the app using 'python run.py' or activate the virtual environment."
        )

    os.makedirs(os.path.dirname(os.path.abspath(audio_path)), exist_ok=True)

    video = VideoFileClip(video_path)
    try:
        if video.audio is None:
            raise ValueError(f"No audio stream found in video file '{video_path}'.")

        video.audio.write_audiofile(audio_path)
    finally:
        video.close()
