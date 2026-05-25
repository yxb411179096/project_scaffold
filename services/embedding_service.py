"""Embedding helpers using the local Ollama embedding endpoint."""

from __future__ import annotations

import logging
import re

import requests

from config import EMBEDDING_BASE_URL, EMBEDDING_MODEL, EMBEDDING_PROVIDER


logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    """Raised when embeddings cannot be generated."""


def _normalized_provider():
    return str(EMBEDDING_PROVIDER or "ollama").strip().lower() or "ollama"


def _normalized_base_url():
    return str(EMBEDDING_BASE_URL or "http://127.0.0.1:11434").strip().rstrip("/")


def _normalized_model_name():
    return str(EMBEDDING_MODEL or "nomic-embed-text").strip() or "nomic-embed-text"


def _build_error_message(exc, model_name):
    message = str(exc or "").strip()
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        if response is not None and response.status_code in {404, 400}:
            return f"Embedding 模型不可用，请先运行：ollama pull {model_name}"
        if response is not None and response.text:
            text = response.text.strip()
            if re.search(r"model.+not found|not found", text, re.I):
                return f"Embedding 模型不可用，请先运行：ollama pull {model_name}"
            return f"Ollama embedding 请求失败：{text}"
    if "model" in message.lower() and "not found" in message.lower():
        return f"Embedding 模型不可用，请先运行：ollama pull {model_name}"
    if message:
        return f"Embedding 请求失败：{message}"
    return f"Embedding 请求失败，请确认 Ollama 已运行并安装 {model_name}。"


def _call_ollama_embeddings(prompt, timeout=120):
    base_url = _normalized_base_url()
    endpoint = f"{base_url}/api/embeddings"
    payload = {
        "model": _normalized_model_name(),
        "prompt": str(prompt or ""),
    }
    with requests.Session() as session:
        session.trust_env = False
        response = session.post(endpoint, json=payload, timeout=max(10, int(timeout or 120)))
    response.raise_for_status()
    data = response.json()
    embedding = data.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise EmbeddingServiceError("Embedding 响应缺少 embedding 向量。")
    return embedding


def embed_text(text, timeout=120):
    """Generate a single embedding vector."""

    vectors = embed_texts([text], timeout=timeout)
    return vectors[0] if vectors else []


def embed_texts(texts, timeout=120):
    """Generate embeddings for a batch of texts."""

    provider = _normalized_provider()
    if provider != "ollama":
        raise EmbeddingServiceError(f"当前 embedding provider={provider} 不支持。")

    prepared_texts = [str(text or "").strip() for text in texts or [] if str(text or "").strip()]
    if not prepared_texts:
        return []

    vectors = []
    for text in prepared_texts:
        try:
            vectors.append(_call_ollama_embeddings(text, timeout=timeout))
        except (requests.RequestException, ValueError, EmbeddingServiceError) as exc:
            logger.warning("Embedding generation failed: %s", exc)
            raise EmbeddingServiceError(_build_error_message(exc, _normalized_model_name())) from exc
    return vectors


def test_embedding_connection(timeout=30):
    """Probe the configured embedding model and return a user-facing status dict."""

    try:
        vector = embed_text("Embedding connection test.", timeout=timeout)
        return {
            "status": "available",
            "message": "Embedding service is reachable.",
            "provider": _normalized_provider(),
            "base_url": _normalized_base_url(),
            "model_name": _normalized_model_name(),
            "dimension": len(vector),
        }
    except EmbeddingServiceError as exc:
        return {
            "status": "unavailable",
            "message": str(exc),
            "provider": _normalized_provider(),
            "base_url": _normalized_base_url(),
            "model_name": _normalized_model_name(),
            "dimension": 0,
        }
