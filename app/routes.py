import os
import re
import sqlite3
import uuid
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, session,
    flash, jsonify, abort, current_app, Response,
)
from markupsafe import Markup, escape
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from .models import get_db
from .services.pipeline import start_processing, stages_for, folder_for_subject
from .ai.summary_types import SUMMARY_TYPES
from .ai.translation_service import translate_text, SUPPORTED_LANGUAGES

main = Blueprint("main", __name__)

VIDEO_EXTENSIONS = {"mp4", "mov", "mkv", "webm", "avi", "m4v"}
AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "ogg"}
ALLOWED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

DEFAULT_FOLDER = "General Lectures"

STATUS_LABELS = {
    "queued": "Queued",
    "extracting": "Extracting audio",
    "transcribing": "Transcribing",
    "summarizing": "Summarizing",
    "translating": "Translating",
    "done": "Ready",
    "failed": "Failed",
}


@main.app_context_processor
def inject_globals():
    return {
        "current_user": session.get("username"),
        "status_labels": STATUS_LABELS,
        "summary_types": SUMMARY_TYPES,
        "supported_languages": SUPPORTED_LANGUAGES,
    }


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TODO = re.compile(r"^\d+\.\s*\[ \]\s*")


def render_summary(text):
    """Turn the summarizer's light markdown (###, **bold**, bullets, [ ] tasks) into HTML."""
    html, open_list = [], None

    def close_list():
        nonlocal open_list
        if open_list:
            html.append(f"</{open_list}>")
            open_list = None

    def inline(s):
        return _BOLD.sub(r"<strong>\1</strong>", str(escape(s)))

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            close_list()
            continue
        if line.startswith("#"):
            close_list()
            html.append(f"<h3>{inline(line.lstrip('#').strip())}</h3>")
        elif line[0] in "•-" and len(line) > 1:
            if open_list != "ul":
                close_list()
                html.append("<ul>")
                open_list = "ul"
            html.append(f"<li>{inline(line[1:].strip())}</li>")
        elif _TODO.match(line):
            if open_list != "ol":
                close_list()
                html.append('<ol class="tasks">')
                open_list = "ol"
            html.append(f"<li>{inline(_TODO.sub('', line))}</li>")
        else:
            close_list()
            html.append(f"<p>{inline(line)}</p>")
    close_list()
    return Markup("\n".join(html))


main.add_app_template_filter(render_summary, "render_summary")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Log in to continue."}), 401
            flash("Log in to continue.", "info")
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def _safe_next(target):
    # Only allow redirects to local paths.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.dashboard")


def _user_folders(db, user_id):
    """The user's folders (newest first), creating the default one if there are none."""
    query = """
        SELECT f.id, f.name, f.created_at, COUNT(s.id) AS summary_count
        FROM folders f
        LEFT JOIN summaries s ON f.id = s.folder_id
        WHERE f.user_id = ?
        GROUP BY f.id
        ORDER BY f.created_at DESC, f.id DESC
    """
    folders = db.execute(query, (user_id,)).fetchall()
    if not folders:
        db.execute("INSERT INTO folders (user_id, name) VALUES (?, ?)", (user_id, DEFAULT_FOLDER))
        db.commit()
        folders = db.execute(query, (user_id,)).fetchall()
    return folders


def _get_own_summary(summary_id):
    db = get_db()
    record = db.execute("""
        SELECT s.*, f.name AS folder_name
        FROM summaries s
        LEFT JOIN folders f ON s.folder_id = f.id
        WHERE s.id = ? AND s.user_id = ?
    """, (summary_id, session["user_id"])).fetchone()
    db.close()
    if record is None:
        abort(404)
    return record


def _get_own_folder(db, folder_id):
    folder = db.execute(
        "SELECT * FROM folders WHERE id = ? AND user_id = ?",
        (folder_id, session["user_id"]),
    ).fetchone()
    if folder is None:
        db.close()
        abort(404)
    return folder


def _summary_json(record):
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "status_label": STATUS_LABELS.get(record["status"], record["status"]),
        "summary": record["summary"],
        "error": record["error"],
        "created_at": record["created_at"],
    }


def _remove_media(record):
    """Delete the uploaded file (and the audio extracted from it), if any."""
    name = record["media_filename"]
    if not name:
        return
    folder = current_app.config["UPLOAD_FOLDER"]
    for path in {name, os.path.splitext(name)[0] + ".mp3"}:
        full = os.path.join(folder, path)
        if os.path.exists(full):
            try:
                os.remove(full)
            except OSError:
                pass


# ---------- Public ----------

@main.route("/")
def index():
    return render_template("index.html")


@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            password_hash = generate_password_hash(password)
            db = get_db()
            try:
                # Insert directly and let the UNIQUE constraint decide: a separate
                # "does it exist?" check races with a second, simultaneous submit.
                cur = db.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, password_hash),
                )
                user_id = cur.lastrowid
                db.execute(
                    "INSERT INTO folders (user_id, name) VALUES (?, ?)",
                    (user_id, DEFAULT_FOLDER),
                )
                db.commit()
                user = {"id": user_id, "username": username}
                message = "Account created. Add your first lecture."
            except sqlite3.IntegrityError:
                db.rollback()
                existing = db.execute(
                    "SELECT * FROM users WHERE username = ?", (username,)
                ).fetchone()
                # Same name and password: a repeated submit of this same sign-up.
                if existing and check_password_hash(existing["password"], password):
                    user = existing
                    message = f"Welcome, {username}."
                else:
                    user = None
            finally:
                db.close()

            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                flash(message, "success")
                return redirect(url_for("main.dashboard"))

            flash("That username is taken. Try another, or log in.", "error")

        return render_template("register.html", username=username), 400

    return render_template("register.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(_safe_next(request.args.get("next")))

        flash("Invalid username or password.", "error")
        return render_template("login.html", username=username), 401

    return render_template("login.html")


@main.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


# ---------- Folders & dashboard ----------

@main.route("/folders")  # Flask links to the route listed last: /dashboard
@main.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    db = get_db()
    folders = _user_folders(db, user_id)
    recent = db.execute("""
        SELECT s.id, s.title, s.status, s.summary, s.source_type, s.summary_type,
               s.created_at, f.name AS folder_name
        FROM summaries s
        LEFT JOIN folders f ON s.folder_id = f.id
        WHERE s.user_id = ?
        ORDER BY s.id DESC
        LIMIT 8
    """, (user_id,)).fetchall()
    total = db.execute("SELECT COUNT(*) FROM summaries WHERE user_id = ?", (user_id,)).fetchone()[0]
    db.close()

    return render_template(
        "folders.html",
        folders=folders,
        recent_summaries=recent,
        total=total,
        selected_folder_id=request.args.get("folder_id", type=int),
    )


@main.route("/folder/create", methods=["POST"])
@login_required
def create_folder():
    name = request.form.get("name", "").strip()[:80]
    if not name:
        flash("Give the folder a name.", "error")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    cur = db.execute(
        "INSERT INTO folders (user_id, name) VALUES (?, ?)",
        (session["user_id"], name),
    )
    db.commit()
    db.close()
    flash(f"Folder “{name}” created.", "success")
    return redirect(url_for("main.view_folder", folder_id=cur.lastrowid))


@main.route("/folder/<int:folder_id>")
@login_required
def view_folder(folder_id):
    db = get_db()
    folder = _get_own_folder(db, folder_id)
    summaries = db.execute("""
        SELECT * FROM summaries
        WHERE folder_id = ? AND user_id = ?
        ORDER BY id DESC
    """, (folder_id, session["user_id"])).fetchall()
    folders = _user_folders(db, session["user_id"])
    db.close()

    return render_template(
        "folder_view.html",
        folder=folder,
        summaries=summaries,
        folders=folders,
        selected_folder_id=folder_id,
    )


@main.route("/folder/delete/<int:folder_id>", methods=["POST"])
@login_required
def delete_folder(folder_id):
    user_id = session["user_id"]
    db = get_db()
    folder = _get_own_folder(db, folder_id)
    count = db.execute("SELECT COUNT(*) FROM folders WHERE user_id = ?", (user_id,)).fetchone()[0]
    if count <= 1:
        db.close()
        flash("You need at least one folder, so the last one can't be deleted.", "error")
        return redirect(url_for("main.view_folder", folder_id=folder_id))

    inside = db.execute(
        "SELECT * FROM summaries WHERE folder_id = ? AND user_id = ?", (folder_id, user_id)
    ).fetchall()
    for record in inside:
        _remove_media(record)
    db.execute("DELETE FROM summaries WHERE folder_id = ? AND user_id = ?", (folder_id, user_id))
    db.execute("DELETE FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id))
    db.commit()
    db.close()

    n = len(inside)
    flash(f"Deleted folder “{folder['name']}” and {n} summar{'y' if n == 1 else 'ies'}.", "info")
    return redirect(url_for("main.dashboard"))


# ---------- Create a summary (file upload or YouTube link) ----------

@main.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        folder_id = request.args.get("folder_id", type=int)
        if folder_id:
            return redirect(url_for("main.view_folder", folder_id=folder_id) + "#new")
        return redirect(url_for("main.dashboard") + "#new")

    wants_json = request.accept_mimetypes.best == "application/json"

    def fail(message):
        if wants_json:
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.dashboard"))

    user_id = session["user_id"]
    source_mode = request.form.get("source_mode", "file")
    summary_type = request.form.get("summary_type", "bullet_points")
    if summary_type not in SUMMARY_TYPES:
        summary_type = "bullet_points"
    target_lang = request.form.get("target_lang", "en")
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "en"
    custom_title = request.form.get("custom_title", "").strip()
    new_folder_name = request.form.get("new_folder_name", "").strip()[:80]
    upload_dir = current_app.config["UPLOAD_FOLDER"]

    job = {"summary_type": summary_type, "target_lang": target_lang, "upload_dir": upload_dir,
           "user_id": user_id, "auto_folder": request.form.get("folder_id") == "auto" and not new_folder_name}

    if source_mode == "youtube":
        url = request.form.get("youtube_url", "").strip()
        from .services.youtube_service import extract_youtube_video_id
        if not url or not extract_youtube_video_id(url):
            return fail("Paste a YouTube link, like https://www.youtube.com/watch?v=… or https://youtu.be/…")
        source_type, source_url, media_filename = "youtube", url, None
        title = custom_title or "YouTube lecture"
        job.update(source_type="youtube", url=url, has_custom_title=bool(custom_title))
    else:
        media = request.files.get("video")
        if media is None or media.filename == "":
            return fail("Choose a video or audio file to upload.")

        original = secure_filename(media.filename) or "lecture.mp4"
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in ALLOWED_EXTENSIONS:
            return fail("Unsupported file type. Use MP4, MOV, MKV, WEBM, AVI, M4V, MP3, WAV, M4A or OGG.")

        stem = original.rsplit(".", 1)[0]
        media_filename = f"{uuid.uuid4().hex[:8]}_{original}"
        media_path = os.path.join(upload_dir, media_filename)
        media.save(media_path)

        source_type, source_url = "file", original
        title = custom_title or stem.replace("_", " ")
        job.update(source_type="file", media_path=media_path)

    db = get_db()
    if new_folder_name:
        cur = db.execute("INSERT INTO folders (user_id, name) VALUES (?, ?)", (user_id, new_folder_name))
        folder_id = cur.lastrowid
    else:
        # "auto": file it in the default folder now; the pipeline moves it once the
        # subject classifier has read the transcript.
        folder_id = request.form.get("folder_id", type=int)
        owned = folder_id and db.execute(
            "SELECT 1 FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id)).fetchone()
        if not owned:
            folder_id = _user_folders(db, user_id)[0]["id"]

    cur = db.execute("""
        INSERT INTO summaries (user_id, folder_id, title, source_type, source_url, summary_type,
                               transcript, summary, status, target_lang, media_filename)
        VALUES (?, ?, ?, ?, ?, ?, '', '', 'queued', ?, ?)
    """, (user_id, folder_id, title[:200], source_type, source_url, summary_type, target_lang, media_filename))
    db.commit()
    summary_id = cur.lastrowid
    db.close()

    start_processing(summary_id, job)

    target = url_for("main.view_summary", summary_id=summary_id)
    if wants_json:
        return jsonify({"id": summary_id, "url": target})
    return redirect(target)


# ---------- A summary ----------

@main.route("/summary/<int:summary_id>")
@login_required
def view_summary(summary_id):
    record = _get_own_summary(summary_id)
    return render_template(
        "summary_view.html",
        summary=record,
        stages=stages_for(record["source_type"], record["media_filename"], record["target_lang"]),
    )


@main.route("/summary/delete/<int:summary_id>", methods=["POST"])
@login_required
def delete_summary(summary_id):
    record = _get_own_summary(summary_id)
    _remove_media(record)
    db = get_db()
    db.execute("DELETE FROM summaries WHERE id = ? AND user_id = ?", (summary_id, session["user_id"]))
    db.commit()
    db.close()
    flash(f"Deleted “{record['title']}”.", "info")
    if record["folder_id"]:
        return redirect(url_for("main.view_folder", folder_id=record["folder_id"]))
    return redirect(url_for("main.dashboard"))


@main.route("/summary/<int:summary_id>/move-to-subject", methods=["POST"])
@login_required
def move_to_subject(summary_id):
    record = _get_own_summary(summary_id)
    if not record["subject"]:
        abort(400)
    folder_id = folder_for_subject(session["user_id"], record["subject"])
    db = get_db()
    db.execute("UPDATE summaries SET folder_id = ? WHERE id = ? AND user_id = ?",
               (folder_id, summary_id, session["user_id"]))
    db.commit()
    db.close()
    flash(f"Moved to “{record['subject']}”.", "success")
    return redirect(url_for("main.view_summary", summary_id=summary_id))


@main.route("/summary/<int:summary_id>/download")
@login_required
def download_summary(summary_id):
    s = _get_own_summary(summary_id)
    style = SUMMARY_TYPES.get(s["summary_type"], {}).get("name", s["summary_type"])
    body = (
        f"{s['title']}\n{'=' * len(s['title'])}\n"
        f"Date: {s['created_at']}\nStyle: {style}\n"
        f"Source: {s['source_url'] or s['source_type']}\n\n"
        f"SUMMARY\n-------\n{s['summary'] or '(not ready)'}\n\n"
        f"TRANSCRIPT{' (English)' if s['transcript_original'] else ''}\n"
        f"----------\n{s['transcript'] or '(not ready)'}\n"
    )
    if s["transcript_original"]:
        heading = f"TRANSCRIPT AS SPOKEN ({s['language_name'] or s['language']})"
        body += f"\n{heading}\n{'-' * len(heading)}\n{s['transcript_original']}\n"
    filename = secure_filename(s["title"]) or "lecture"
    return Response(
        body,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}_summary.txt"'},
    )


@main.route("/api/summaries/<int:summary_id>")
@login_required
def summary_status(summary_id):
    return jsonify(_summary_json(_get_own_summary(summary_id)))


@main.route("/api/translate", methods=["POST"])
@login_required
def translate_summary_api():
    data = request.get_json(silent=True) or {}
    target_lang = data.get("target_lang", "es")
    save = bool(data.get("save"))
    try:
        summary_id = int(data.get("summary_id") or 0)
    except (TypeError, ValueError):
        summary_id = 0

    if target_lang not in SUPPORTED_LANGUAGES:
        return jsonify({"success": False, "error": "Unsupported language."}), 400

    record = _get_own_summary(summary_id)
    if record["status"] != "done" or not record["summary"]:
        return jsonify({"success": False, "error": "This summary isn't ready yet."}), 400

    if save:
        # Store the translation the user is looking at.
        translated = (data.get("text") or "").strip()
        if not translated:
            return jsonify({"success": False, "error": "Nothing to save."}), 400
        db = get_db()
        db.execute(
            "UPDATE summaries SET summary = ?, target_lang = ? WHERE id = ? AND user_id = ?",
            (translated, target_lang, record["id"], session["user_id"]),
        )
        db.commit()
        db.close()
    elif target_lang == record["target_lang"]:
        translated = record["summary"]  # already in that language
    else:
        translated = translate_text(record["summary"], target_lang=target_lang)
        # translate_text hands back the input unchanged when the service can't be reached.
        if translated.strip() == record["summary"].strip():
            return jsonify({
                "success": False,
                "error": "The translation service didn't respond. Check the internet connection and try again.",
            }), 502

    return jsonify({
        "success": True,
        "translated_text": translated,
        "translated_html": str(render_summary(translated)),
        "lang_code": target_lang,
        "lang_name": SUPPORTED_LANGUAGES.get(target_lang, target_lang),
        "saved": save,
    })
