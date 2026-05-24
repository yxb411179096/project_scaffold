import socket

from flask import Flask
from routes.knowledge_routes import knowledge_bp
from routes.ppt_routes import ppt_bp
from models.database import init_db
from config import DEBUG, HOST, MAX_MANUSCRIPT_FILE_SIZE, PORT, SECRET_KEY


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_MANUSCRIPT_FILE_SIZE
    app.register_blueprint(ppt_bp)
    app.register_blueprint(knowledge_bp)
    init_db()
    return app


def resolve_port(host, preferred_port, search_window=20):
    for candidate in range(preferred_port, preferred_port + search_window):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
            except OSError:
                continue
            return candidate
    return preferred_port


if __name__ == "__main__":
    app = create_app()
    runtime_port = resolve_port(HOST, PORT)
    if runtime_port != PORT:
        print(f"Port {PORT} is in use. Falling back to {runtime_port}.")
    app.run(host=HOST, port=runtime_port, debug=DEBUG)
