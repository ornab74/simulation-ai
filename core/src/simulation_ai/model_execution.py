from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .credentials import CredentialVaultError, OpenAICredentialVault
from .model import canonical_json, digest, utc_now
from .prompts import PromptPackError, PromptRegistry


class ModelExecutionError(RuntimeError):
    """Raised when a provider call cannot produce a valid candidate artifact."""

    def __init__(self, code: str, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ModelExecutionConfig:
    endpoint: str = "https://api.openai.com/v1/responses"
    default_model: str = "gpt-5.6"
    default_reasoning_effort: str = "medium"
    default_max_output_tokens: int = 4096
    timeout_seconds: float = 60.0
    max_attempts: int = 2

    @classmethod
    def from_environment(cls) -> "ModelExecutionConfig":
        return cls(
            endpoint=os.environ.get("SIMULATION_AI_OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses").strip(),
            default_model=os.environ.get("SIMULATION_AI_OPENAI_MODEL", "gpt-5.6").strip(),
            default_reasoning_effort=os.environ.get("SIMULATION_AI_OPENAI_REASONING_EFFORT", "medium").strip(),
            default_max_output_tokens=int(os.environ.get("SIMULATION_AI_OPENAI_MAX_OUTPUT_TOKENS", "4096")),
            timeout_seconds=float(os.environ.get("SIMULATION_AI_OPENAI_TIMEOUT", "60")),
            max_attempts=max(1, min(3, int(os.environ.get("SIMULATION_AI_OPENAI_MAX_ATTEMPTS", "2")))),
        )


class OpenAIResponsesExecutor:
    """Execute one rendered prompt through OpenAI's Responses API.

    The executor has no state-commit, branch, capability, runtime, or frame
    authority. It submits a bounded prompt, parses a structured candidate, and
    runs deterministic local JSON-Schema validation before returning a trace.
    """

    def __init__(
        self,
        credentials: OpenAICredentialVault,
        prompts: PromptRegistry,
        *,
        config: ModelExecutionConfig | None = None,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.credentials = credentials
        self.prompts = prompts
        self.config = config or ModelExecutionConfig.from_environment()
        self._opener = opener
        self._sleep = sleep

    def execute(
        self,
        invocation: dict[str, Any],
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if invocation.get("schema") != "nmsr.prompt-invocation/1":
            raise ModelExecutionError("invalid_invocation", "A rendered nmsr.prompt-invocation/1 artifact is required.")
        prompt_id = str(invocation.get("prompt_id", ""))
        self.prompts.get(prompt_id)
        messages = invocation.get("messages", [])
        if not isinstance(messages, list) or len(messages) < 2:
            raise ModelExecutionError("invalid_invocation", "Prompt invocation messages are incomplete.")
        system_text = self._message_content(messages, "system")
        user_text = self._message_content(messages, "user")
        selected_model = (model or self.config.default_model).strip()
        if not selected_model or len(selected_model) > 128:
            raise ModelExecutionError("invalid_model", "A valid model identifier is required.")
        effort = (reasoning_effort or self.config.default_reasoning_effort).strip().lower()
        if effort not in {"none", "minimal", "low", "medium", "high", "xhigh"}:
            raise ModelExecutionError("invalid_reasoning_effort", "Unsupported reasoning effort.")
        token_limit = int(max_output_tokens or self.config.default_max_output_tokens)
        if not 128 <= token_limit <= 100_000:
            raise ModelExecutionError("invalid_token_limit", "max_output_tokens must be between 128 and 100000.")

        api_key, credential_source = self.credentials.resolve_api_key()
        response_format = self._provider_response_format(invocation.get("response_format", {}))
        compatibility = invocation.get("openai_strict_compatibility", {})
        provider_strict = bool(compatibility.get("compatible", False)) if isinstance(compatibility, dict) else False
        response_format["strict"] = provider_strict
        request_body: dict[str, Any] = {
            "model": selected_model,
            "instructions": system_text,
            "input": user_text,
            "text": {"format": response_format},
            "reasoning": {"effort": effort},
            "max_output_tokens": token_limit,
            "store": False,
            "metadata": {
                "simulation_ai_prompt": prompt_id[:64],
                "simulation_ai_pack": str(invocation.get("pack_version", ""))[:64],
                "simulation_ai_invocation": str(invocation.get("invocation_id", ""))[:64],
            },
        }
        request_bytes = canonical_json(request_body).encode("utf-8")
        request_sha = digest({
            "endpoint": self.config.endpoint,
            "model": selected_model,
            "body": request_body,
        })
        started = time.monotonic()
        response_data: dict[str, Any] | None = None
        request_id = ""
        status_code = 0
        last_error: ModelExecutionError | None = None
        attempts = 0
        for attempt in range(1, self.config.max_attempts + 1):
            attempts = attempt
            request = Request(
                self.config.endpoint,
                data=request_bytes,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "simulation-ai-core/0.6",
                },
            )
            try:
                with self._opener(request, timeout=timeout or self.config.timeout_seconds) as response:
                    status_code = int(getattr(response, "status", 200))
                    headers = getattr(response, "headers", {})
                    request_id = self._header(headers, "x-request-id")
                    raw = response.read(16 * 1024 * 1024)
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ModelExecutionError("invalid_provider_response", "OpenAI returned a non-object response.")
                response_data = parsed
                break
            except HTTPError as exc:
                status_code = int(exc.code)
                detail = self._http_error_detail(exc)
                last_error = ModelExecutionError("provider_http_error", detail, status_code=status_code)
                if status_code not in {408, 409, 429, 500, 502, 503, 504} or attempt >= self.config.max_attempts:
                    raise last_error from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = ModelExecutionError(
                    "provider_unreachable",
                    f"OpenAI could not be reached: {type(exc).__name__}.",
                    status_code=status_code,
                )
                if attempt >= self.config.max_attempts:
                    raise last_error from exc
            except json.JSONDecodeError as exc:
                raise ModelExecutionError("invalid_provider_response", "OpenAI returned malformed JSON.") from exc
            self._sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))

        if response_data is None:
            raise last_error or ModelExecutionError("provider_failure", "No provider response was produced.")
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        response_status = str(response_data.get("status", "completed"))
        if response_status not in {"completed", "incomplete"}:
            error = response_data.get("error") or {}
            message = str(error.get("message", "OpenAI did not complete the response.")) if isinstance(error, dict) else "OpenAI did not complete the response."
            raise ModelExecutionError("response_not_completed", message, status_code=status_code)
        output_text = self._extract_output_text(response_data)
        try:
            output = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ModelExecutionError("invalid_model_json", "The model output was not valid JSON.") from exc
        if not isinstance(output, dict):
            raise ModelExecutionError("invalid_model_output", "The model output must be a JSON object.")
        validation = self.prompts.validate_output(prompt_id, output)
        output_sha = str(validation["output_sha256"])
        response_id = str(response_data.get("id", ""))
        run_id = "run_" + digest({
            "invocation_id": invocation.get("invocation_id"),
            "model": selected_model,
            "response_id": response_id,
            "output_sha256": output_sha,
        })[:24]
        usage = response_data.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        return {
            "schema": "nmsr.prompt-run/1",
            "run_id": run_id,
            "kind": "model-prompt",
            "status": "validated" if validation["valid"] else "invalid",
            "provider": "openai",
            "provider_response_id": response_id,
            "provider_request_id": request_id,
            "provider_status": response_status,
            "credential_source": credential_source,
            "prompt_id": prompt_id,
            "prompt_version": invocation.get("prompt_version"),
            "prompt_sha256": invocation.get("prompt_sha256"),
            "pack_id": invocation.get("pack_id"),
            "pack_version": invocation.get("pack_version"),
            "invocation_id": invocation.get("invocation_id"),
            "request_sha256": request_sha,
            "model": selected_model,
            "reasoning_effort": effort,
            "max_output_tokens": token_limit,
            "attempts": attempts,
            "latency_ms": elapsed_ms,
            "usage": self._safe_usage(usage),
            "output": output,
            "output_sha256": output_sha,
            "validation": validation,
            "approval": {
                "status": "pending",
                "reviewed_by": "",
                "note": "",
                "reviewed_at": "",
            },
            "authority": str(invocation.get("authority", "proposal-only")),
            "commit_authority": False,
            "deterministic_gate_required": True,
            "store_requested": False,
            "provider_strict_schema": provider_strict,
            "created_at": utc_now(),
        }


    @classmethod
    def _provider_response_format(cls, value: Any) -> dict[str, Any]:
        """Return a provider-safe copy of a repository response format.

        Repository schemas retain Draft metadata for local validation and
        content addressing. Provider structured-output payloads receive a deep
        copy with transport-irrelevant ``$schema`` and ``$id`` keys removed.
        The original invocation is never mutated.
        """
        if not isinstance(value, dict):
            raise ModelExecutionError("invalid_invocation", "Prompt invocation response_format must be an object.")

        def clean(node: Any) -> Any:
            if isinstance(node, dict):
                return {
                    str(key): clean(child)
                    for key, child in node.items()
                    if key not in {"$schema", "$id"}
                }
            if isinstance(node, list):
                return [clean(child) for child in node]
            return node

        cleaned = clean(value)
        if not isinstance(cleaned, dict):
            raise ModelExecutionError("invalid_invocation", "Prompt invocation response_format is invalid.")
        schema = cleaned.get("schema")
        if not isinstance(schema, dict):
            raise ModelExecutionError("invalid_invocation", "Prompt invocation has no JSON Schema response format.")
        return cleaned

    @staticmethod
    def _message_content(messages: list[Any], role: str) -> str:
        for message in messages:
            if isinstance(message, dict) and message.get("role") == role:
                content = message.get("content")
                if isinstance(content, str) and content:
                    return content
        raise ModelExecutionError("invalid_invocation", f"Prompt invocation has no {role} message.")

    @staticmethod
    def _header(headers: Any, name: str) -> str:
        try:
            return str(headers.get(name, ""))
        except AttributeError:
            return ""

    @staticmethod
    def _http_error_detail(exc: HTTPError) -> str:
        try:
            raw = exc.read(1024 * 1024)
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
                message = str(parsed["error"].get("message", ""))
                if message:
                    return message[:500]
        except Exception:
            pass
        return f"OpenAI returned HTTP {exc.code}."

    @classmethod
    def _extract_output_text(cls, response: dict[str, Any]) -> str:
        direct = response.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        parts: list[str] = []
        for item in response.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                content_type = str(content.get("type", ""))
                if content_type in {"refusal", "output_refusal"}:
                    refusal = str(content.get("refusal") or content.get("text") or "The model refused the request.")
                    raise ModelExecutionError("model_refusal", refusal[:500])
                if content_type in {"output_text", "text"}:
                    text = content.get("text")
                    if isinstance(text, str):
                        parts.append(text)
        combined = "".join(parts).strip()
        if not combined:
            raise ModelExecutionError("empty_model_output", "OpenAI returned no structured text output.")
        return combined

    @staticmethod
    def _safe_usage(usage: dict[str, Any]) -> dict[str, int]:
        safe: dict[str, int] = {}
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(name, 0)
            if isinstance(value, int) and value >= 0:
                safe[name] = value
        return safe
