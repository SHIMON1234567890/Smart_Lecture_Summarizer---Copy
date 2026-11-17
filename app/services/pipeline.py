"""Turns an upload or a YouTube link into a styled summary, in a background thread.

Stages (stored in summaries.status so the page can show live progress):
    queued -> extracting -> transcribing -> summarizing -> translating -> done | failed
"""
import os
import threading
import traceback

from ..models import update_summary

AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "ogg"}

# One job at a time: the models are large, and two jobs loading them at once
# can exhaust a laptop's memory. Waiting jobs stay "queued".
_JOB_LOCK = threading.Lock()


def stages_for(source_type, media_filename, target_lang):
    """The stages a job passes through, in order (used by the progress page)."""
    stages = []
    if source_type == "file":
        ext = (media_filename or "").rsplit(".", 1)[-1].lower()
        if ext not in AUDIO_EXTENSIONS:
            stages.append("extracting")
    stages += ["transcribing", "summarizing"]
    if target_lang and target_lang != "en":
        stages.append("translating")
    return stages + ["done"]


def _transcript_from_file(summary_id, media_path):
    ext = media_path.rsplit(".", 1)[-1].lower()
    audio_path = media_path

    if ext not in AUDIO_EXTENSIONS:
        update_summary(summary_id, status="extracting")
        # Heavy imports are deferred so the website starts even without ML packages.
        from .video_service import extract_audio
        audio_path = os.path.splitext(media_path)[0] + ".mp3"
        extract_audio(media_path, audio_path)

    update_summary(summary_id, status="transcribing")
    from ..ai.whisper_service import transcribe_audio
    return transcribe_audio(audio_path)


def _transcript_from_youtube(summary_id, url, upload_dir, has_custom_title):
    update_summary(summary_id, status="transcribing")
    from .youtube_service import process_youtube_video
    data = process_youtube_video(url, upload_dir=upload_dir)
    if not has_custom_title and data.get("title"):
        update_summary(summary_id, title=data["title"][:200])
    return data["transcript"]


def _run(summary_id, job):
    try:
        if job["source_type"] == "youtube":
            transcript = _transcript_from_youtube(
                summary_id, job["url"], job["upload_dir"], job["has_custom_title"])
        else:
            transcript = _transcript_from_file(summary_id, job["media_path"])

        transcript = (transcript or "").strip()
        if not transcript:
            raise RuntimeError("No speech was found in this recording.")
        update_summary(summary_id, transcript=transcript)

        update_summary(summary_id, status="summarizing")
        from ..ai.summarizer_service import summarize_text
        summary = summarize_text(transcript, summary_type=job["summary_type"])

        target_lang = job.get("target_lang") or "en"
        if target_lang != "en":
            update_summary(summary_id, status="translating")
            from ..ai.translation_service import translate_text
            summary = translate_text(summary, target_lang=target_lang)

        update_summary(summary_id, status="done", summary=summary, error=None)

    except ModuleNotFoundError as exc:
        update_summary(
            summary_id,
            status="failed",
            error=f"Missing Python package '{exc.name}'. Run: pip install -r requirements.txt",
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        traceback.print_exc()
        update_summary(summary_id, status="failed", error=str(exc) or exc.__class__.__name__)


def _run_one_at_a_time(summary_id, job):
    with _JOB_LOCK:
        _run(summary_id, job)


def start_processing(summary_id, job):
    threading.Thread(target=_run_one_at_a_time, args=(summary_id, job), daemon=True).start()
