import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _resolve_path(env_name, default_relative):
    raw_value = os.getenv(env_name, default_relative)
    path = Path(raw_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
HOST = os.getenv("FLASK_HOST", "127.0.0.1")
PORT = int(os.getenv("FLASK_PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

DATABASE_PATH = BASE_DIR / "english_ppt_ai.sqlite3"
EXPORT_PPTX_DIR = BASE_DIR / "exports" / "pptx"
EXPORT_DOCX_DIR = BASE_DIR / "exports" / "docx"
UPLOAD_DIR = BASE_DIR / "uploads"
MANUSCRIPT_UPLOAD_DIR = UPLOAD_DIR / "manuscripts"
KNOWLEDGE_UPLOAD_DIR = UPLOAD_DIR / "knowledge"
KNOWLEDGE_TEXT_DIR = UPLOAD_DIR / "knowledge_text"
MAX_MANUSCRIPT_FILE_SIZE = 20 * 1024 * 1024

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:30b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHROMA_PERSIST_DIR = _resolve_path("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "english_teaching_knowledge")
