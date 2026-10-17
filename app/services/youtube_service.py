import os
import re
import json
import urllib.request
from app.ai.whisper_service import transcribe_audio

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None


def extract_youtube_video_id(url):
    """
    Extracts the 11-character video ID from various YouTube URL formats.
    """
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"youtube\.com\/embed\/([0-9A-Za-z_-]{11})",
        r"youtube\.com\/shorts\/([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_youtube_title(video_url):
    """
    Fetches the video title via YouTube's official oEmbed API without needing API keys.
    """
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("title", "YouTube Lecture")
    except Exception:
        return "YouTube Lecture"


def get_youtube_transcript_from_subtitles(video_id):
    """
    Attempts to fetch official or auto-generated transcripts using youtube_transcript_api.
    """
    if not YouTubeTranscriptApi:
        return None

    try:
        # Try fetching English or auto-generated transcripts
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        full_text = " ".join([entry["text"] for entry in transcript_list])
        return full_text.strip()
    except Exception as e:
        print(f"Subtitle extraction not available for {video_id}: {e}")
        try:
            # Fallback to any available language
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            for transcript in transcript_list:
                data = transcript.fetch()
                return " ".join([entry["text"] for entry in data]).strip()
        except Exception:
            pass
    return None


def download_youtube_audio_and_transcribe(video_url, video_id, upload_dir="uploads"):
    """
    Fallback method: downloads the audio using yt-dlp and runs Whisper transcription.
    """
    os.makedirs(upload_dir, exist_ok=True)
    audio_path = os.path.join(upload_dir, f"yt_{video_id}.mp3")

    try:
        import yt_dlp

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(upload_dir, f"yt_{video_id}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if os.path.exists(audio_path):
            return transcribe_audio(audio_path)
    except Exception as e:
        print(f"yt-dlp download failed: {e}")

    raise RuntimeError(
        "Could not extract transcript from YouTube video. "
        "Ensure subtitles are enabled on the video, or yt-dlp is installed."
    )


def process_youtube_video(video_url, upload_dir="uploads"):
    """
    Main function to process a YouTube URL:
    1. Extracts video ID and title.
    2. Tries fast subtitle extraction.
    3. Falls back to audio download + Whisper if needed.
    """
    video_id = extract_youtube_video_id(video_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube link.")

    title = fetch_youtube_title(video_url)

    # 1. Fast subtitle extraction
    transcript = get_youtube_transcript_from_subtitles(video_id)

    # 2. Fallback to audio download + Whisper
    if not transcript:
        print(f"Subtitles not found for {video_id}. Attempting audio download & Whisper transcription...")
        transcript = download_youtube_audio_and_transcribe(video_url, video_id, upload_dir)

    if not transcript or not transcript.strip():
        raise ValueError("Could not extract any transcript from the provided YouTube video.")

    return {
        "video_id": video_id,
        "title": title,
        "transcript": transcript.strip(),
        "url": video_url
    }

