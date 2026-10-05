from .services.video_service import extract_audio
from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from .models import get_db
from .ai.whisper_service import transcribe_audio
from .ai.summarizer_service import summarize_text

main = Blueprint("main", __name__)


@main.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        db.close()

        print("USER:", user)
        print("PASSWORD CHECK:", check_password_hash(user["password"], password))

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("main.upload"))

        return "Invalid username or password"

    return render_template("login.html")



@main.route("/upload", methods=["GET", "POST"])
def upload():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if request.method == "POST":

        video = request.files["video"]

        if video.filename == "":
            return "No video selected"

        video_path = "uploads/" + video.filename
        audio_path = "uploads/" + video.filename.rsplit(".", 1)[0] + ".mp3"

        video.save(video_path)

        extract_audio(video_path, audio_path)

        transcript = transcribe_audio(audio_path)

        print("TRANSCRIPT:")
        print(transcript)

        summary = summarize_text(transcript)

        print("SUMMARY:")
        print(summary)

        return "Video uploaded, audio extracted, transcript created, and summary generated successfully!"

    return render_template("upload.html")