import moviepy.config as mp_config
from moviepy import VideoFileClip
import imageio_ffmpeg


mp_config.FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()


def extract_audio(video_path, audio_path):

    video = VideoFileClip(video_path)

    video.audio.write_audiofile(audio_path)

    video.close()