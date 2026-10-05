from flask import Flask
from .models import get_db, create_tables


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = "smart-lecture-secret-key"

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        create_tables()

    return app