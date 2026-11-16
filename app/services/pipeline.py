"""Runs the video -> audio -> transcript -> summary pipeline in a background thread."""
import threading
import traceback

from ..models import update_lecture


def _run(lecture_id, video_path, audio_path):
    try:
        update_lecture(lecture_id, status="extracting")
        # Heavy imports are deferred so the website starts even without ML packages.
        from .video_service import extract_audio
        extract_audio(video_path, audio_path)

        update_lecture(lecture_id, status="transcribing")
        from ..ai.whisper_service import transcribe_audio
        transcript = transcribe_audio(audio_path)
        update_lecture(lecture_id, transcript=transcript)

        if not transcript:
            raise RuntimeError("No speech was found in this video.")

        update_lecture(lecture_id, status="summarizing")
        from ..ai.summarizer_service import summarize_text
        summary = summarize_text(transcript)

        update_lecture(lecture_id, status="done", summary=summary, error=None)

    except ModuleNotFoundError as exc:
        update_lecture(
            lecture_id,
            status="failed",
            error=f"Missing Python package '{exc.name}'. Run: pip install -r requirements.txt",
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        traceback.print_exc()
        update_lecture(lecture_id, status="failed", error=str(exc) or exc.__class__.__name__)


def start_processing(lecture_id, video_path, audio_path):
    thread = threading.Thread(
        target=_run,
        args=(lecture_id, video_path, audio_path),
        daemon=True,
    )
    thread.start()
