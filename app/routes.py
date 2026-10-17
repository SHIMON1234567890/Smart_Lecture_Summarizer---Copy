import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from .models import get_db
from .services.video_service import extract_audio
from .services.youtube_service import process_youtube_video
from .ai.whisper_service import transcribe_audio
from .ai.summarizer_service import summarize_text, SUMMARY_TYPES

main = Blueprint("main", __name__)


@main.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("main.folders_dashboard"))
    return redirect(url_for("main.login"))


@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("register.html", error="Username and password are required")

        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            user_id = cur.lastrowid

            # Create default 'General' folder for new user
            db.execute(
                "INSERT INTO folders (user_id, name) VALUES (?, ?)",
                (user_id, "General Lectures")
            )
            db.commit()
        except Exception:
            db.close()
            return render_template("register.html", error="Username already exists. Please choose another.")
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
            return redirect(url_for("main.folders_dashboard"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# ==========================================
# FOLDERS & DASHBOARD ROUTES
# ==========================================

@main.route("/folders")
@main.route("/dashboard")
def folders_dashboard():
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_id = session["user_id"]
    db = get_db()

    # Ensure user has at least one folder
    existing = db.execute("SELECT id FROM folders WHERE user_id = ?", (user_id,)).fetchall()
    if not existing:
        db.execute("INSERT INTO folders (user_id, name) VALUES (?, ?)", (user_id, "General Lectures"))
        db.commit()

    # Get folders with summary counts
    folders = db.execute("""
        SELECT f.id, f.name, f.created_at, COUNT(s.id) AS summary_count
        FROM folders f
        LEFT JOIN summaries s ON f.id = s.folder_id
        WHERE f.user_id = ?
        GROUP BY f.id
        ORDER BY f.created_at DESC
    """, (user_id,)).fetchall()

    # Get recent summaries across all folders
    recent_summaries = db.execute("""
        SELECT s.id, s.title, s.source_type, s.summary_type, s.created_at, f.name AS folder_name
        FROM summaries s
        LEFT JOIN folders f ON s.folder_id = f.id
        WHERE s.user_id = ?
        ORDER BY s.created_at DESC
        LIMIT 6
    """, (user_id,)).fetchall()

    db.close()

    return render_template(
        "folders.html",
        folders=folders,
        recent_summaries=recent_summaries,
        summary_types=SUMMARY_TYPES
    )


@main.route("/folder/create", methods=["POST"])
def create_folder():
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    folder_name = request.form.get("name", "").strip()
    if folder_name:
        db = get_db()
        db.execute(
            "INSERT INTO folders (user_id, name) VALUES (?, ?)",
            (session["user_id"], folder_name)
        )
        db.commit()
        db.close()

    return redirect(url_for("main.folders_dashboard"))


@main.route("/folder/<int:folder_id>")
def view_folder(folder_id):
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_id = session["user_id"]
    db = get_db()

    folder = db.execute(
        "SELECT * FROM folders WHERE id = ? AND user_id = ?",
        (folder_id, user_id)
    ).fetchone()

    if not folder:
        db.close()
        return "Folder not found or unauthorized", 404

    summaries = db.execute("""
        SELECT * FROM summaries
        WHERE folder_id = ? AND user_id = ?
        ORDER BY created_at DESC
    """, (folder_id, user_id)).fetchall()

    db.close()

    return render_template(
        "folder_view.html",
        folder=folder,
        summaries=summaries,
        summary_types=SUMMARY_TYPES
    )


@main.route("/folder/delete/<int:folder_id>", methods=["POST"])
def delete_folder(folder_id):
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    db = get_db()
    db.execute(
        "DELETE FROM folders WHERE id = ? AND user_id = ?",
        (folder_id, session["user_id"])
    )
    db.commit()
    db.close()

    return redirect(url_for("main.folders_dashboard"))


# ==========================================
# SUMMARY VIEW & DELETION
# ==========================================

from .ai.translation_service import translate_text, SUPPORTED_LANGUAGES


@main.route("/summary/<int:summary_id>")
def view_summary(summary_id):
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_id = session["user_id"]
    db = get_db()

    summary_record = db.execute("""
        SELECT s.*, f.name AS folder_name
        FROM summaries s
        LEFT JOIN folders f ON s.folder_id = f.id
        WHERE s.id = ? AND s.user_id = ?
    """, (summary_id, user_id)).fetchone()

    db.close()

    if not summary_record:
        return "Summary not found or unauthorized", 404

    return render_template(
        "summary_view.html",
        summary=summary_record,
        summary_types=SUMMARY_TYPES,
        supported_languages=SUPPORTED_LANGUAGES
    )


@main.route("/api/translate", methods=["POST"])
def translate_summary_api():
    if "user_id" not in session:
        return {"success": False, "error": "Unauthorized"}, 401

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    target_lang = data.get("target_lang", "es")
    summary_id = data.get("summary_id")
    save = data.get("save", False)

    if not text:
        return {"success": False, "error": "No text provided to translate"}, 400

    try:
        translated = translate_text(text, target_lang=target_lang)

        if save and summary_id:
            db = get_db()
            db.execute(
                "UPDATE summaries SET summary = ? WHERE id = ? AND user_id = ?",
                (translated, summary_id, session["user_id"])
            )
            db.commit()
            db.close()

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        return {
            "success": True,
            "translated_text": translated,
            "lang_code": target_lang,
            "lang_name": lang_name
        }
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@main.route("/summary/delete/<int:summary_id>", methods=["POST"])
def delete_summary(summary_id):
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    folder_id = request.form.get("folder_id")
    db = get_db()
    db.execute(
        "DELETE FROM summaries WHERE id = ? AND user_id = ?",
        (summary_id, session["user_id"])
    )
    db.commit()
    db.close()

    if folder_id:
        return redirect(url_for("main.view_folder", folder_id=folder_id))
    return redirect(url_for("main.folders_dashboard"))



# ==========================================
# UPLOAD & SUMMARIZATION (FILE & YOUTUBE)
# ==========================================

@main.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_id = session["user_id"]
    db = get_db()
    folders = db.execute(
        "SELECT * FROM folders WHERE user_id = ? ORDER BY name ASC",
        (user_id,)
    ).fetchall()

    selected_folder_id = request.args.get("folder_id", type=int)

    if request.method == "POST":
        source_mode = request.form.get("source_mode", "file")
        summary_type = request.form.get("summary_type", "bullet_points")
        folder_id = request.form.get("folder_id")
        custom_folder_name = request.form.get("new_folder_name", "").strip()

        # Check if creating a new folder on the fly
        if custom_folder_name:
            cur = db.execute(
                "INSERT INTO folders (user_id, name) VALUES (?, ?)",
                (user_id, custom_folder_name)
            )
            db.commit()
            folder_id = cur.lastrowid
        elif folder_id:
            folder_id = int(folder_id)
        else:
            folder_id = folders[0]["id"] if folders else None

        transcript = ""
        summary = ""
        title = ""
        source_type = "video"
        source_url = ""

        upload_dir = os.path.abspath("uploads")
        os.makedirs(upload_dir, exist_ok=True)

        try:
            # Mode A: YouTube URL
            if source_mode == "youtube":
                youtube_url = request.form.get("youtube_url", "").strip()
                if not youtube_url:
                    db.close()
                    return render_template("upload.html", folders=folders, summary_types=SUMMARY_TYPES, error="Please enter a valid YouTube link.")

                yt_data = process_youtube_video(youtube_url, upload_dir=upload_dir)
                transcript = yt_data["transcript"]
                title = yt_data["title"]
                source_type = "youtube"
                source_url = youtube_url

            # Mode B: Video or Audio File Upload
            else:
                if "video" not in request.files or request.files["video"].filename == "":
                    db.close()
                    return render_template("upload.html", folders=folders, summary_types=SUMMARY_TYPES, error="No file selected.")

                video = request.files["video"]
                filename = secure_filename(video.filename)
                base_name, ext = os.path.splitext(filename)
                file_path = os.path.join(upload_dir, filename)
                video.save(file_path)

                title = request.form.get("custom_title", "").strip() or base_name.replace("_", " ").title()
                source_type = "file"
                source_url = filename

                # If already an audio file (.mp3, .wav), transcribe directly
                if ext.lower() in [".mp3", ".wav", ".m4a", ".ogg"]:
                    transcript = transcribe_audio(file_path)
                else:
                    audio_path = os.path.join(upload_dir, f"{base_name}.mp3")
                    extract_audio(file_path, audio_path)
                    transcript = transcribe_audio(audio_path)

            # Generate multi-style summary
            summary = summarize_text(transcript, summary_type=summary_type)

            # Check if user selected a target language on upload
            target_lang = request.form.get("target_lang", "en")
            if target_lang and target_lang != "en":
                summary = translate_text(summary, target_lang=target_lang)

            # Save summary record to database
            cur = db.execute("""
                INSERT INTO summaries (user_id, folder_id, title, source_type, source_url, summary_type, transcript, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, folder_id, title, source_type, source_url, summary_type, transcript, summary))
            db.commit()
            summary_id = cur.lastrowid
            db.close()

            return redirect(url_for("main.view_summary", summary_id=summary_id))

        except Exception as e:
            db.close()
            print(f"Error during summarization: {e}")
            return render_template(
                "upload.html",
                folders=folders,
                summary_types=SUMMARY_TYPES,
                supported_languages=SUPPORTED_LANGUAGES,
                error=f"Processing failed: {str(e)}"
            )

    db.close()
    return render_template(
        "upload.html",
        folders=folders,
        summary_types=SUMMARY_TYPES,
        supported_languages=SUPPORTED_LANGUAGES,
        selected_folder_id=selected_folder_id
    )


