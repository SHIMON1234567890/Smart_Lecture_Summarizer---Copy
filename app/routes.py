import os
from werkzeug.utils import secure_filename
from .services.video_service import extract_audio
from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from .models import get_db
from .ai.whisper_service import transcribe_audio
from .ai.summarizer_service import summarize_text

main = Blueprint("main", __name__)


@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return "Username and password are required"

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            db.commit()
        except Exception:
            db.close()
            return "Username already exists. Please choose another or login."
        db.close()

        return redirect(url_for("main.login"))

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

            return redirect(url_for("main.upload"))

        return "Invalid username or password"

    return render_template("login.html")


@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main.route("/upload", methods=["GET", "POST"])
def upload():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if request.method == "POST":

        if "video" not in request.files:
            return "No video file provided"

        video = request.files["video"]

        if video.filename == "":
            return "No video selected"

        upload_dir = os.path.abspath("uploads")
        os.makedirs(upload_dir, exist_ok=True)

        filename = secure_filename(video.filename)
        base_name, _ = os.path.splitext(filename)

        video_path = os.path.join(upload_dir, filename)
        audio_path = os.path.join(upload_dir, f"{base_name}.mp3")

        video.save(video_path)

        extract_audio(video_path, audio_path)

        transcript = transcribe_audio(audio_path)

        print("TRANSCRIPT:")
        print(transcript)

        summary = summarize_text(transcript)

        print("SUMMARY:")
        print(summary)

        return render_template(
            "upload.html",
            transcript=transcript,
            summary=summary,
            success=True
        )

    return render_template("upload.html")
