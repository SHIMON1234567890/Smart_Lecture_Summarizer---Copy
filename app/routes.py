import os
import sqlite3
import uuid
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, session,
    flash, jsonify, abort, current_app, Response,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from .models import get_db
from .services.pipeline import start_processing

main = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"mp4", "mov", "mkv", "webm", "avi", "m4v"}

STATUS_LABELS = {
    "queued": "Queued",
    "extracting": "Extracting audio",
    "transcribing": "Transcribing",
    "summarizing": "Summarizing",
    "done": "Ready",
    "failed": "Failed",
}


@main.app_context_processor
def inject_globals():
    return {
        "current_user": session.get("username"),
        "status_labels": STATUS_LABELS,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Log in to continue.", "info")
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def _get_own_lecture(lecture_id):
    db = get_db()
    lecture = db.execute(
        "SELECT * FROM lectures WHERE id = ? AND user_id = ?",
        (lecture_id, session["user_id"]),
    ).fetchone()
    db.close()
    if lecture is None:
        abort(404)
    return lecture


def _lecture_json(lecture):
    return {
        "id": lecture["id"],
        "title": lecture["title"],
        "status": lecture["status"],
        "status_label": STATUS_LABELS.get(lecture["status"], lecture["status"]),
        "transcript": lecture["transcript"],
        "summary": lecture["summary"],
        "error": lecture["error"],
        "created_at": lecture["created_at"],
    }


def _safe_next(target):
    # Only allow redirects to local paths.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.dashboard")


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
                db.commit()
                user = {"id": cur.lastrowid, "username": username}
                message = "Account created. Upload your first lecture."
            except sqlite3.IntegrityError:
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


# ---------- App ----------

@main.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    lectures = db.execute(
        "SELECT id, title, status, summary, created_at FROM lectures "
        "WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("dashboard.html", lectures=lectures)


@main.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return redirect(url_for("main.dashboard"))

    wants_json = request.accept_mimetypes.best == "application/json"

    def fail(message):
        if wants_json:
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.dashboard"))

    video = request.files.get("video")

    if video is None or video.filename == "":
        return fail("Choose a video to upload.")

    original = secure_filename(video.filename) or "lecture.mp4"
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED_EXTENSIONS:
        return fail("Unsupported file type. Use MP4, MOV, MKV, WEBM, AVI or M4V.")

    stem = original.rsplit(".", 1)[0]
    unique = f"{uuid.uuid4().hex[:8]}_{original}"
    folder = current_app.config["UPLOAD_FOLDER"]
    video_path = os.path.join(folder, unique)
    audio_path = os.path.join(folder, unique.rsplit(".", 1)[0] + ".mp3")

    video.save(video_path)

    title = request.form.get("title", "").strip() or stem.replace("_", " ")

    db = get_db()
    cur = db.execute(
        "INSERT INTO lectures (user_id, title, video_filename) VALUES (?, ?, ?)",
        (session["user_id"], title[:200], unique),
    )
    db.commit()
    lecture_id = cur.lastrowid
    db.close()

    start_processing(lecture_id, video_path, audio_path)

    if wants_json:
        return jsonify({"id": lecture_id, "url": url_for("main.lecture", lecture_id=lecture_id)})

    return redirect(url_for("main.lecture", lecture_id=lecture_id))


@main.route("/lecture/<int:lecture_id>")
@login_required
def lecture(lecture_id):
    return render_template("lecture.html", lecture=_get_own_lecture(lecture_id))


@main.route("/lecture/<int:lecture_id>/delete", methods=["POST"])
@login_required
def delete_lecture(lecture_id):
    lecture = _get_own_lecture(lecture_id)
    folder = current_app.config["UPLOAD_FOLDER"]
    for name in (lecture["video_filename"],
                 lecture["video_filename"].rsplit(".", 1)[0] + ".mp3"):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    db = get_db()
    db.execute("DELETE FROM lectures WHERE id = ?", (lecture_id,))
    db.commit()
    db.close()
    flash(f"Deleted “{lecture['title']}”.", "info")
    return redirect(url_for("main.dashboard"))


@main.route("/lecture/<int:lecture_id>/download")
@login_required
def download_lecture(lecture_id):
    lecture = _get_own_lecture(lecture_id)
    body = (
        f"{lecture['title']}\n{'=' * len(lecture['title'])}\n\n"
        f"SUMMARY\n-------\n{lecture['summary'] or '(not ready)'}\n\n"
        f"TRANSCRIPT\n----------\n{lecture['transcript'] or '(not ready)'}\n"
    )
    filename = secure_filename(lecture["title"]) or "lecture"
    return Response(
        body,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.txt"'},
    )


@main.route("/api/lectures/<int:lecture_id>")
@login_required
def lecture_status(lecture_id):
    return jsonify(_lecture_json(_get_own_lecture(lecture_id)))
