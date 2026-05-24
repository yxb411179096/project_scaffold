"""LLM service with agent strategy bindings and stable fallback behavior."""

import contextvars
import json
import logging
import re
import time

import requests

from config import LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
from models.database import (
    AI_MODEL_PROVIDERS,
    create_llm_call_log,
    get_agent_model_binding,
    get_ai_model_config,
    get_default_ai_model_config,
)


logger = logging.getLogger(__name__)

_GENERATION_TRACE = contextvars.ContextVar("generation_trace", default=None)
_ACTIVE_MODEL_CONFIG = contextvars.ContextVar("active_model_config", default=None)


class LLMServiceError(Exception):
    """Raised when a model call fails or returns invalid JSON."""


def _normalized_env_provider():
    provider = str(LLM_PROVIDER or "mock").strip().lower()
    return provider or "mock"


def _normalize_task_id(task_id):
    try:
        return int(task_id)
    except (TypeError, ValueError):
        return None


def _mask_secret(value):
    secret = str(value or "").strip()
    if len(secret) <= 8:
        return "****" if secret else ""
    return f"{secret[:3]}-****{secret[-4:]}"


def _can_call_model(config):
    if not config or not config.get("enabled", True):
        return False
    provider = str(config.get("provider") or "").strip().lower()
    if provider == "ollama":
        return bool(config.get("base_url") and config.get("model_name"))
    if provider in {"deepseek", "openai"}:
        return bool(config.get("model_name"))
    return False


def _usable_database_config(config):
    if not config or not config.get("enabled"):
        return False
    provider = str(config.get("provider") or "").strip().lower()
    if provider == "mock":
        return True
    if provider == "ollama":
        return bool(config.get("base_url") and config.get("model_name"))
    if provider in {"deepseek", "openai"}:
        return bool(config.get("model_name"))
    return False


def _mock_model_config(detail="No usable database or env model config was found."):
    return {
        "id": None,
        "name": "Mock Fallback",
        "provider": "mock",
        "base_url": "",
        "model_name": "mock",
        "api_key": "",
        "timeout": 60,
        "enabled": True,
        "is_default": True,
        "purpose": "rule-based fallback",
        "source": "mock",
        "resolution_detail": detail,
    }


def _env_model_config():
    provider = _normalized_env_provider()
    config = {
        "id": None,
        "name": f"ENV {provider}",
        "provider": provider,
        "base_url": str(OLLAMA_BASE_URL or "http://127.0.0.1:11434").rstrip("/"),
        "model_name": str(OLLAMA_MODEL or "qwen2.5:7b").strip() or "qwen2.5:7b",
        "api_key": "",
        "timeout": max(10, int(OLLAMA_TIMEOUT or 120)),
        "enabled": True,
        "is_default": True,
        "purpose": "env fallback",
        "source": "env",
        "resolution_detail": "",
    }

    if provider == "mock":
        config["base_url"] = ""
        config["model_name"] = "mock"
        return config
    if provider == "ollama":
        return config
    if provider in {"deepseek", "openai"}:
        return config

    config["provider"] = "mock"
    config["name"] = "Mock Fallback"
    config["base_url"] = ""
    config["model_name"] = "mock"
    config["resolution_detail"] = f"ENV provider {provider} is not supported."
    return config


def get_active_model_config(force_refresh=False):
    """Resolve the active model config from DB, then env, then mock."""

    if not force_refresh:
        cached = _ACTIVE_MODEL_CONFIG.get()
        if cached is not None:
            return dict(cached)

    db_config = get_default_ai_model_config()
    if db_config and _usable_database_config(db_config):
        resolved = dict(db_config)
        resolved["source"] = "database"
        resolved["resolution_detail"] = ""
        _ACTIVE_MODEL_CONFIG.set(resolved)
        return dict(resolved)

    env_config = _env_model_config()
    if db_config and not _usable_database_config(db_config):
        env_config["resolution_detail"] = (
            f"Database default model {db_config.get('name') or db_config.get('provider')} is not usable."
        )
    if env_config.get("provider") in AI_MODEL_PROVIDERS:
        _ACTIVE_MODEL_CONFIG.set(env_config)
        return dict(env_config)

    mock_config = _mock_model_config()
    _ACTIVE_MODEL_CONFIG.set(mock_config)
    return dict(mock_config)


def describe_runtime_model():
    """Return a redacted snapshot of the runtime model configuration."""

    config = get_active_model_config(force_refresh=True)
    described = dict(config)
    described["api_key_masked"] = _mask_secret(config.get("api_key"))
    return described


def _default_trace():
    config = get_active_model_config()
    provider = str(config.get("provider") or "mock").strip().lower()
    mode = "mock" if provider == "mock" else "ollama" if provider == "ollama" else "fallback"
    return {
        "provider": provider,
        "source": config.get("source"),
        "config_name": config.get("name"),
        "mode": mode,
        "events": [],
    }


def reset_generation_trace():
    """Reset generation trace for the current request or command."""

    _ACTIVE_MODEL_CONFIG.set(None)
    _GENERATION_TRACE.set(_default_trace())


def get_generation_trace():
    """Return the latest generation trace snapshot."""

    trace = _GENERATION_TRACE.get()
    if trace is None:
        trace = _default_trace()
        _GENERATION_TRACE.set(trace)
    return {
        "provider": trace.get("provider"),
        "source": trace.get("source"),
        "config_name": trace.get("config_name"),
        "mode": trace.get("mode"),
        "events": list(trace.get("events", [])),
    }


def _append_trace_event(mode, stage, detail, **extra):
    trace = get_generation_trace()
    events = list(trace.get("events", []))
    event = {
        "mode": mode,
        "stage": stage,
        "detail": str(detail or "").strip(),
    }
    for key, value in extra.items():
        if value is not None:
            event[key] = value
    events.append(event)
    trace["events"] = events
    if mode == "fallback":
        trace["mode"] = "fallback"
    elif mode == "mock" and trace.get("mode") != "fallback":
        trace["mode"] = "mock"
    elif mode == "ollama" and trace.get("mode") != "fallback":
        trace["mode"] = "ollama"
    _GENERATION_TRACE.set(trace)
    return trace


def record_mock_usage(stage, detail="Rule-based generation used."):
    logger.info("LLM stage=%s mode=mock detail=%s", stage, detail)
    return _append_trace_event("mock", stage, detail)


def record_fallback(stage, detail):
    logger.warning("LLM stage=%s mode=fallback detail=%s", stage, detail)
    return _append_trace_event("fallback", stage, detail)


def _record_call_log(task_id, agent_name, provider, model_name, status, duration_ms, error_message="", detail=""):
    normalized_task_id = _normalize_task_id(task_id)
    create_llm_call_log(
        normalized_task_id,
        agent_name,
        provider,
        model_name,
        status,
        int(duration_ms or 0),
        error_message,
    )
    mode = "fallback" if status in {"fallback_rule", "failed"} else "mock" if status == "skipped_rule_only" else "ollama"
    _append_trace_event(
        mode,
        agent_name,
        detail or error_message or status,
        agent_name=agent_name,
        provider=provider,
        model_name=model_name,
        status=status,
        duration_ms=int(duration_ms or 0),
        error_message=error_message or "",
    )


def record_rule_only_agent(agent_name, task_id, detail="Rule-only stage executed."):
    """Record a rule-only agent execution in logs and trace."""

    _record_call_log(
        task_id,
        agent_name,
        "rule",
        "rule",
        "skipped_rule_only",
        0,
        "",
        detail,
    )


def _strip_code_fence(text):
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_json_payload(text):
    cleaned = _strip_code_fence(text)
    if not cleaned:
        raise LLMServiceError("Model returned an empty response.")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(cleaned):
            if char not in "[{":
                continue
            try:
                payload, _ = decoder.raw_decode(cleaned[index:])
                return payload
            except json.JSONDecodeError:
                continue
    raise LLMServiceError("Model returned invalid JSON.")


def _call_ollama_payload(model_config, system_prompt, user_prompt, timeout, temperature, max_tokens, json_required):
    base_url = str(model_config.get("base_url") or "").rstrip("/")
    endpoint = f"{base_url}/api/generate"
    payload = {
        "model": model_config.get("model_name"),
        "system": str(system_prompt or "").strip(),
        "prompt": str(user_prompt or "").strip(),
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if json_required:
        payload["format"] = "json"

    with requests.Session() as session:
        session.trust_env = False
        response = session.post(
            endpoint,
            json=payload,
            timeout=timeout,
        )
    response.raise_for_status()
    response_json = response.json()
    return _parse_json_payload(response_json.get("response"))


def _call_model_json_with_config(
    agent_name,
    model_config,
    task_id,
    system_prompt,
    user_prompt,
    timeout,
    temperature,
    max_tokens,
    json_required,
    success_status="success",
    detail="",
):
    provider = str(model_config.get("provider") or "").strip().lower()
    model_name = str(model_config.get("model_name") or provider).strip() or provider
    started_at = time.perf_counter()

    try:
        if provider == "ollama":
            result = _call_ollama_payload(
                model_config,
                system_prompt,
                user_prompt,
                timeout,
                temperature,
                max_tokens,
                json_required,
            )
        elif provider in {"deepseek", "openai"}:
            raise LLMServiceError(f"{provider} provider is not implemented yet.")
        else:
            raise LLMServiceError(f"Provider {provider or 'unknown'} cannot be used for model calls.")

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _record_call_log(
            task_id,
            agent_name,
            provider,
            model_name,
            success_status,
            duration_ms,
            "",
            detail or f"{provider}:{model_name}",
        )
        logger.info(
            "LLM agent=%s provider=%s model=%s status=%s duration_ms=%s",
            agent_name,
            provider,
            model_name,
            success_status,
            duration_ms,
        )
        return result
    except (requests.RequestException, ValueError, LLMServiceError) as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _record_call_log(
            task_id,
            agent_name,
            provider,
            model_name,
            "failed",
            duration_ms,
            str(exc),
            detail or str(exc),
        )
        logger.warning(
            "LLM agent=%s provider=%s model=%s status=failed duration_ms=%s error=%s",
            agent_name,
            provider,
            model_name,
            duration_ms,
            exc,
        )
        raise LLMServiceError(str(exc)) from exc


def _resolve_model_config(config_id):
    if not config_id:
        return None
    config = get_ai_model_config(config_id)
    if not config or not config.get("enabled"):
        return None
    return config


def get_model_for_agent(agent_name):
    """Resolve effective model strategy for one agent."""

    binding = get_agent_model_binding(agent_name)
    default_model = get_active_model_config(force_refresh=True)

    if binding is None:
        primary = default_model if _can_call_model(default_model) else None
        return {
            "agent_name": agent_name,
            "mode": "model_first" if primary else "rule_only",
            "primary_model_config": primary,
            "fallback_model_config": None,
            "timeout_override": None,
            "temperature": 0.3,
            "max_tokens": 2048,
            "json_required": True,
            "fallback_to_rule": True,
            "enabled": True,
            "source": "default_model",
            "binding": None,
        }

    primary = _resolve_model_config(binding.get("primary_model_config_id"))
    fallback_model = _resolve_model_config(binding.get("fallback_model_config_id"))
    if primary is None and _can_call_model(default_model):
        primary = default_model

    return {
        "agent_name": agent_name,
        "mode": binding.get("mode") or "rule_only",
        "primary_model_config": primary,
        "fallback_model_config": fallback_model,
        "timeout_override": binding.get("timeout_override"),
        "temperature": binding.get("temperature") if binding.get("temperature") is not None else 0.3,
        "max_tokens": binding.get("max_tokens") if binding.get("max_tokens") is not None else 2048,
        "json_required": bool(binding.get("json_required")),
        "fallback_to_rule": bool(binding.get("fallback_to_rule")),
        "enabled": bool(binding.get("enabled")),
        "source": "binding",
        "binding": binding,
    }


def _run_rule_fallback(agent_name, task_id, fallback_fn, status, detail):
    if fallback_fn is None:
        raise LLMServiceError(detail)
    started_at = time.perf_counter()
    result = fallback_fn()
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    _record_call_log(
        task_id,
        agent_name,
        "rule",
        "rule",
        status,
        duration_ms,
        "",
        detail,
    )
    return result


def call_agent_json(agent_name, prompt, fallback_fn=None):
    """Call one agent according to its binding strategy."""

    prompt = prompt if isinstance(prompt, dict) else {"user_prompt": str(prompt or "")}
    system_prompt = prompt.get("system_prompt") or ""
    user_prompt = prompt.get("user_prompt") or ""
    task_id = prompt.get("task_id")
    stage_note = str(prompt.get("stage_note") or "").strip()

    strategy = get_model_for_agent(agent_name)
    mode = strategy.get("mode") or "rule_only"
    if not strategy.get("enabled"):
        mode = "disabled"

    temperature = prompt.get("temperature")
    if temperature is None:
        temperature = strategy.get("temperature", 0.3)
    max_tokens = prompt.get("max_tokens")
    if max_tokens is None:
        max_tokens = strategy.get("max_tokens", 2048)
    timeout = prompt.get("timeout_override")
    if timeout is None:
        timeout = strategy.get("timeout_override") or (
            strategy.get("primary_model_config") or get_active_model_config()
        ).get("timeout")
    timeout = max(10, int(timeout or 120))
    json_required = prompt.get("json_required")
    if json_required is None:
        json_required = strategy.get("json_required", True)

    if mode in {"rule_only", "disabled"}:
        return _run_rule_fallback(
            agent_name,
            task_id,
            fallback_fn,
            "skipped_rule_only",
            stage_note or f"Agent mode is {mode}.",
        )

    primary_model = strategy.get("primary_model_config")
    fallback_model = strategy.get("fallback_model_config")
    fallback_to_rule = bool(strategy.get("fallback_to_rule"))

    if not _can_call_model(primary_model):
        detail = stage_note or "No usable primary model is available."
        if mode == "model_then_fallback_model" and _can_call_model(fallback_model):
            fallback_timeout = max(
                10,
                int(
                    prompt.get("timeout_override")
                    or strategy.get("timeout_override")
                    or fallback_model.get("timeout")
                    or 120
                ),
            )
            return _call_model_json_with_config(
                agent_name,
                fallback_model,
                task_id,
                system_prompt,
                user_prompt,
                fallback_timeout,
                temperature,
                max_tokens,
                json_required,
                success_status="fallback_model",
                detail=detail,
            )
        if fallback_to_rule and fallback_fn is not None:
            return _run_rule_fallback(agent_name, task_id, fallback_fn, "fallback_rule", detail)
        raise LLMServiceError(detail)

    try:
        return _call_model_json_with_config(
            agent_name,
            primary_model,
            task_id,
            system_prompt,
            user_prompt,
            timeout,
            temperature,
            max_tokens,
            json_required,
            success_status="success",
            detail=stage_note,
        )
    except LLMServiceError as primary_error:
        if mode == "model_then_fallback_model" and _can_call_model(fallback_model):
            try:
                fallback_timeout = max(
                    10,
                    int(
                        prompt.get("timeout_override")
                        or strategy.get("timeout_override")
                        or fallback_model.get("timeout")
                        or 120
                    ),
                )
                return _call_model_json_with_config(
                    agent_name,
                    fallback_model,
                    task_id,
                    system_prompt,
                    user_prompt,
                    fallback_timeout,
                    temperature,
                    max_tokens,
                    json_required,
                    success_status="fallback_model",
                    detail=stage_note or f"Fallback model after primary error: {primary_error}",
                )
            except LLMServiceError as fallback_error:
                if fallback_to_rule and fallback_fn is not None:
                    detail = stage_note or (
                        f"Primary model failed: {primary_error}; fallback model failed: {fallback_error}"
                    )
                    return _run_rule_fallback(
                        agent_name,
                        task_id,
                        fallback_fn,
                        "fallback_rule",
                        detail,
                    )
                raise

        if mode != "model_only" and fallback_to_rule and fallback_fn is not None:
            return _run_rule_fallback(
                agent_name,
                task_id,
                fallback_fn,
                "fallback_rule",
                stage_note or f"Primary model failed: {primary_error}",
            )
        raise


def should_use_ollama():
    """Backward-compatible helper for callers that inspect the default model."""

    return get_active_model_config().get("provider") == "ollama"


def ollama_settings():
    """Expose the current default Ollama settings."""

    config = get_active_model_config()
    return {
        "base_url": str(config.get("base_url") or "http://127.0.0.1:11434").rstrip("/"),
        "model": str(config.get("model_name") or "qwen2.5:7b").strip() or "qwen2.5:7b",
        "timeout": max(10, int(config.get("timeout") or 120)),
    }


def call_ollama_json(stage, system_prompt, user_prompt, temperature=0.3):
    """Backward-compatible direct Ollama call using the default runtime model."""

    config = get_active_model_config(force_refresh=True)
    if not _can_call_model(config):
        raise LLMServiceError("No usable default Ollama model is available.")
    return _call_model_json_with_config(
        stage,
        config,
        None,
        system_prompt,
        user_prompt,
        max(10, int(config.get("timeout") or 120)),
        temperature,
        2048,
        True,
        success_status="success",
        detail=f"default runtime model {config.get('name')}",
    )


def _log_generation_summary():
    trace = get_generation_trace()
    stages = ", ".join(
        f"{event.get('agent_name', event['stage'])}:{event.get('status', event['mode'])}"
        for event in trace.get("events", [])
    )
    logger.info(
        "Generation summary mode=%s provider=%s stages=%s",
        trace.get("mode"),
        trace.get("provider"),
        stages or "none",
    )


def test_model_connection(model_config):
    """Test whether a model configuration is reachable."""

    provider = str(model_config.get("provider") or "mock").strip().lower()
    timeout = max(5, int(model_config.get("timeout") or 30))

    if provider == "mock":
        return {
            "status": "available",
            "message": "Mock provider is always available for local fallback.",
            "details": {},
        }

    if provider == "ollama":
        base_url = str(model_config.get("base_url") or "").rstrip("/")
        if not base_url:
            return {
                "status": "unavailable",
                "message": "Ollama base_url is empty.",
                "details": {},
            }
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(f"{base_url}/api/tags", timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            models = [item.get("name") for item in payload.get("models", []) if item.get("name")]
            message = "Ollama service is reachable."
            if models:
                message = f"Ollama service is reachable. Models: {', '.join(models[:6])}"
            return {
                "status": "available",
                "message": message,
                "details": {"models": models},
            }
        except (requests.RequestException, ValueError) as exc:
            return {
                "status": "unavailable",
                "message": f"Ollama test failed: {exc}",
                "details": {},
            }

    if provider in {"deepseek", "openai"}:
        return {
            "status": "untested",
            "message": f"{provider} connection test is a placeholder for now.",
            "details": {},
        }

    return {
        "status": "unavailable",
        "message": f"Unsupported provider: {provider}",
        "details": {},
    }


def generate_slides_from_manuscript(task, manuscript_text):
    """Generate slides from a user manuscript through the manuscript pipeline."""

    reset_generation_trace()
    active_config = get_active_model_config(force_refresh=True)
    if active_config.get("resolution_detail"):
        record_fallback("config", active_config["resolution_detail"])
    if active_config.get("provider") == "mock":
        record_mock_usage("manuscript_pipeline", "Active provider is mock.")

    try:
        from services.manuscript_pipeline_service import run_manuscript_pipeline

        result = run_manuscript_pipeline(task, manuscript_text)
        slides = result.get("ppt_json") or []
        if not slides:
            raise ValueError("The manuscript pipeline returned no slides.")
        _log_generation_summary()
        return result
    except Exception as exc:
        from services.manuscript_pipeline_service import build_rule_based_manuscript_result

        record_fallback("manuscript_pipeline", f"Unexpected manuscript pipeline error: {exc}")
        result = build_rule_based_manuscript_result(task, manuscript_text)
        slides = result.get("ppt_json") or []
        if not slides:
            record_fallback("manuscript_pipeline", "Rule-based manuscript fallback also returned no slides.")
        _log_generation_summary()
        return result


def generate_slides(task):
    """Generate slides through the hybrid pipeline."""

    if str(task.get("generation_mode") or "").startswith("manuscript"):
        result = generate_slides_from_manuscript(task, str(task.get("manuscript_raw_text") or ""))
        return result.get("ppt_json") or []

    reset_generation_trace()
    active_config = get_active_model_config(force_refresh=True)
    if active_config.get("resolution_detail"):
        record_fallback("config", active_config["resolution_detail"])
    if active_config.get("provider") == "mock":
        record_mock_usage("pipeline", "Active provider is mock.")

    try:
        from services.pipeline_service import generate_ppt_json

        slides = generate_ppt_json(task)
        if not slides:
            raise ValueError("The generation pipeline returned no slides.")
        _log_generation_summary()
        return slides
    except Exception as exc:
        from services.mock_ai_service import generate_mock_slides

        record_fallback("pipeline", f"Unexpected pipeline error: {exc}")
        slides = generate_mock_slides(task)
        if not slides:
            record_fallback("pipeline", "Mock fallback also returned no slides.")
        _log_generation_summary()
        return slides


def regenerate_slide(task, current_slide):
    """Regenerate one slide through the hybrid pipeline."""

    if str(task.get("generation_mode") or "").startswith("manuscript"):
        reset_generation_trace()
        active_config = get_active_model_config(force_refresh=True)
        if active_config.get("resolution_detail"):
            record_fallback("config", active_config["resolution_detail"])
        if active_config.get("provider") == "mock":
            record_mock_usage("manuscript_regenerate", "Active provider is mock.")

        try:
            from services.manuscript_pipeline_service import regenerate_slide_from_manuscript

            slide = regenerate_slide_from_manuscript(task, current_slide)
            _log_generation_summary()
            return slide
        except Exception as exc:
            record_fallback("manuscript_regenerate", f"Unexpected manuscript regenerate error: {exc}")
            from services.manuscript_pipeline_service import build_rule_based_manuscript_result

            result = build_rule_based_manuscript_result(task, str(task.get("manuscript_raw_text") or ""))
            slides = result.get("ppt_json") or []
            if not slides:
                raise
            target_index = int(current_slide.get("slide_index") or 1)
            slide = slides[min(max(target_index - 1, 0), len(slides) - 1)]
            _log_generation_summary()
            return slide

    reset_generation_trace()
    active_config = get_active_model_config(force_refresh=True)
    if active_config.get("resolution_detail"):
        record_fallback("config", active_config["resolution_detail"])
    if active_config.get("provider") == "mock":
        record_mock_usage("regenerate", "Active provider is mock.")

    try:
        from services.pipeline_service import regenerate_slide_with_pipeline

        slide = regenerate_slide_with_pipeline(task, current_slide)
        _log_generation_summary()
        return slide
    except Exception as exc:
        from services.mock_ai_service import regenerate_mock_slide

        record_fallback("regenerate", f"Unexpected pipeline error: {exc}")
        slide = regenerate_mock_slide(task, current_slide)
        _log_generation_summary()
        return slide
