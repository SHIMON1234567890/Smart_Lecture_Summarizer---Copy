import os
import re
import json
import urllib.parse
import urllib.request
from app.ai.whisper_service import transcribe_multilingual

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
        oembed_url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(video_url, safe="")
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("title", "YouTube Lecture")
    except Exception:
        return "YouTube Lecture"


def _snippet_text(entry):
    # youtube-transcript-api < 1.0 returns dicts, >= 1.0 returns snippet objects.
    return entry["text"] if isinstance(entry, dict) else entry.text


def _caption_text(transcript):
    return " ".join(_snippet_text(e) for e in transcript.fetch()).strip()


def _translate_long_to_english(text, piece_chars=1500):
    """Translate long caption text with the app's translation service, piece by piece.
    Returns None if the service couldn't be reached."""
    from app.ai.translation_service import translate_chunk

    words, pieces, current = text.split(), [], ""
    for w in words:
        if current and len(current) + len(w) + 1 > piece_chars:
            pieces.append(current)
            current = w
        else:
            current = f"{current} {w}" if current else w
    if current:
        pieces.append(current)

    out = []
    for piece in pieces:
        translated = translate_chunk(piece, target_lang="en")
        if not translated or translated == piece:  # service unreachable
            return None
        out.append(translated)
    return " ".join(out)


def get_youtube_transcript_from_subtitles(video_id):
    """
    Fetches captions with youtube_transcript_api.

    Returns {"language", "language_name", "original", "english"} or None. English
    captions are preferred; otherwise the first caption track is used, with
    an English translation of it (YouTube's own, else the translation service).
    Returns None when there are no captions or no English version can be made
    (the caller then uses Whisper).
    """
    if not YouTubeTranscriptApi:
        return None

    try:
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):  # versions before 1.0
            tracks = YouTubeTranscriptApi.list_transcripts(video_id)
        else:
            tracks = YouTubeTranscriptApi().list(video_id)
    except Exception as e:
        print(f"No subtitles available for {video_id}: {e}")
        return None

    try:
        en = tracks.find_transcript(["en", "en-US", "en-GB", "en-IN"])
        text = _caption_text(en)
        if text:
            return {"language": "en", "language_name": "English", "original": text, "english": text}
    except Exception:
        pass  # no English track

    for track in tracks:
        try:
            original = _caption_text(track)
            if not original:
                continue
            english = None
            if track.is_translatable:
                try:
                    english = _caption_text(track.translate("en"))
                except Exception as e:
                    print(f"YouTube couldn't translate {video_id} captions: {e}")
            if not english:
                english = _translate_long_to_english(original)
            if not english:
                print(f"Captions for {video_id} ({track.language_code}) couldn't be translated to English.")
                return None
            code = track.language_code.split("-")[0]
            name = track.language.replace(" (auto-generated)", "")
            return {"language": code, "language_name": name, "original": original, "english": english or original}
        except Exception as e:
            print(f"Could not use {track.language_code} captions for {video_id}: {e}")
            return None
    return None


def download_youtube_audio_and_transcribe(video_url, video_id, upload_dir="uploads"):
    """
    Fallback method: downloads the audio using yt-dlp and runs Whisper transcription.
    The audio is kept in its original format (Whisper decodes it with FFmpeg), so
    no separate ffprobe install is needed.
    """
    os.makedirs(upload_dir, exist_ok=True)

    try:
        import yt_dlp

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(upload_dir, f"yt_{video_id}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            audio_path = ydl.prepare_filename(info)

        if os.path.exists(audio_path):
            return transcribe_multilingual(audio_path)
    except Exception as e:
        print(f"yt-dlp download failed: {e}")

    raise RuntimeError(
        "Could not get a transcript for this YouTube video. It has no captions, "
        "and its audio could not be downloaded."
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
    result = get_youtube_transcript_from_subtitles(video_id)

    # 2. Fallback to audio download + Whisper
    if not result:
        print(f"Subtitles not usable for {video_id}. Attempting audio download & Whisper transcription...")
        result = download_youtube_audio_and_transcribe(video_url, video_id, upload_dir)

    if not result or not (result.get("english") or "").strip():
        raise ValueError("Could not extract any transcript from the provided YouTube video.")

    return {
        "video_id": video_id,
        "title": title,
        "transcript": result["english"].strip(),  # English, for the summarizer
        "transcript_original": result["original"].strip(),
        "language": result["language"],
        "language_name": result["language_name"],
        "url": video_url,
    }
