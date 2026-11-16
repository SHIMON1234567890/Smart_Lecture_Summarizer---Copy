import os

from flask import Flask
from .models import create_tables


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "smart-lecture-secret-key")
    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        create_tables()

    return app
