"""
LLM provider abstraction for Niv AI.

Fallback order by capability:
  - Structured agent JSON: Groq -> Gemini -> OpenRouter
  - Final synthesis: Gemini -> Groq -> OpenRouter
  - Search grounding: Gemini grounded -> Groq -> OpenRouter
  - Document/multimodal: Gemini first, then text fallback when caller already has extracted text
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from groq import APITimeoutError, APIConnectionError, AsyncGroq, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.utils.prompting import apply_bias_hardening

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    import google.api_core.exceptions
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False


class LLMProviderError(RuntimeError):
    """Raised when a provider call fails."""


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str


class LLMClient:
    def __init__(self) -> None:
        def _clean_env(name: str, default: str | None = None) -> str | None:
            value = os.getenv(name, default)
            if value is None:
                return None
            value = value.strip()
            return value or None

        self._groq = None
        self._gemini_model = None
        self._openrouter_client: Optional[httpx.AsyncClient] = None
        self._openrouter_api_key = _clean_env("OPENROUTER_API_KEY")
        self._last_call_metadata: dict[str, Any] = {}

        self._groq_agent_model = _clean_env("GROQ_MODEL_AGENT", "llama-3.1-8b-instant") or "llama-3.1-8b-instant"
        self._groq_final_model = _clean_env("GROQ_MODEL_FINAL", "llama-3.1-8b-instant") or "llama-3.1-8b-instant"
        self._gemini_agent_model_name = _clean_env("GEMINI_MODEL_AGENT", "gemini-2.0-flash") or "gemini-2.0-flash"
        self._gemini_final_model_name = _clean_env("GEMINI_MODEL_FINAL", "gemini-2.0-flash") or "gemini-2.0-flash"
        self._openrouter_agent_model = _clean_env("OPENROUTER_MODEL_AGENT", "qwen/qwen-2.5-7b-instruct") or "qwen/qwen-2.5-7b-instruct"
        self._openrouter_final_model = _clean_env("OPENROUTER_MODEL_FINAL", "qwen/qwen-2.5-7b-instruct") or "qwen/qwen-2.5-7b-instruct"

        groq_key = _clean_env("GROQ_API_KEY")
        if groq_key:
            self._groq = AsyncGroq(api_key=groq_key)

        if _GEMINI_AVAILABLE:
            gemini_key = _clean_env("GEMINI_API_KEY")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                self._gemini_model = genai.GenerativeModel(self._gemini_agent_model_name)

        if self._openrouter_api_key:
            self._openrouter_client = httpx.AsyncClient(
                base_url="https://openrouter.ai/api/v1",
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self._openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.getenv("FRONTEND_URL", "http://localhost"),
                    "X-Title": "NIV AI",
                },
            )

        if not any([self._groq, self._gemini_model, self._openrouter_client]):
            raise RuntimeError(
                "At least one LLM provider key is required: GROQ_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY"
            )

    def get_last_call_metadata(self) -> dict[str, Any]:
        return dict(self._last_call_metadata)

    def _record_success(self, provider: str, model: str, failure_chain: list[dict[str, str]]) -> None:
        self._last_call_metadata = {
            "provider": provider,
            "model": model,
            "fallback_count": len(failure_chain),
            "fallback_chain": failure_chain,
        }

    @staticmethod
    def _compact_error_message(raw_error: str) -> str:
        text = " ".join(str(raw_error or "").split())
        text = re.sub(r"https?://\S+", "", text).strip()
        if "401" in text or "unauthorized" in text.lower():
            return "authentication failed — check API key"
        if "quota exceeded" in text.lower() or "rate limit" in text.lower():
            return "quota or rate limit reached"
        if "not configured" in text.lower():
            return "not configured"
        if "timed out" in text.lower():
            return "request timed out"
        return text[:180]

    def _build_user_facing_failure(self, failure_chain: list[dict[str, str]]) -> str:
        parts = []
        for item in failure_chain:
            provider = item.get("provider", "provider")
            err = self._compact_error_message(item.get("error", "unknown failure"))
            parts.append(f"{provider}: {err}")
        joined = "; ".join(parts) if parts else "no providers available"
        return f"All AI providers are temporarily unavailable. {joined}."

    @staticmethod
    def _normalize_json_prompt(user_message: str) -> str:
        return (
            f"{user_message}\n\n"
            "IMPORTANT: Return only a valid JSON object. No markdown fences. No prose outside JSON."
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError, httpx.HTTPError)),
        reraise=True,
    )
    async def _call_groq(
        self,
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 3000,
        model: str,
    ) -> ProviderResult:
        if not self._groq:
            raise LLMProviderError("Groq not configured")
        response = await self._groq.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._normalize_json_prompt(user_message) if json_mode else user_message},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if json_mode else None,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if content is None:
            raise LLMProviderError("Groq returned empty response")
        return ProviderResult(text=content, provider="groq", model=model)

    async def _call_gemini(
        self,
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 3000,
        model_name: Optional[str] = None,
    ) -> ProviderResult:
        if not _GEMINI_AVAILABLE or self._gemini_model is None:
            raise LLMProviderError("Gemini not configured")
        try:
            model = genai.GenerativeModel(model_name or self._gemini_agent_model_name)
            response = model.generate_content(
                f"{system_prompt}\n\n{self._normalize_json_prompt(user_message) if json_mode else user_message}",
                generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=max_tokens),
            )
            text = response.text if response and response.text else None
            if not text:
                raise LLMProviderError("Gemini returned empty response")
            return ProviderResult(text=text, provider="gemini", model=model_name or self._gemini_agent_model_name)
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc

    async def _call_openrouter(
        self,
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 3000,
        model: str,
    ) -> ProviderResult:
        if not self._openrouter_client:
            raise LLMProviderError("OpenRouter not configured")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._normalize_json_prompt(user_message) if json_mode else user_message},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        response = await self._openrouter_client.post("/chat/completions", json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise LLMProviderError("OpenRouter authentication failed — check OPENROUTER_API_KEY") from exc
            if exc.response.status_code == 429:
                raise LLMProviderError("OpenRouter quota or rate limit reached") from exc
            raise
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("OpenRouter response missing content") from exc
        if not content:
            raise LLMProviderError("OpenRouter returned empty response")
        return ProviderResult(text=content, provider="openrouter", model=model)

    async def _run_provider_chain(
        self,
        providers: list[dict[str, Any]],
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        hardened_prompt = apply_bias_hardening(system_prompt)
        failure_chain: list[dict[str, str]] = []
        for provider in providers:
            name = provider["name"]
            model = provider["model"]
            try:
                if name == "groq":
                    result = await self._call_groq(
                        hardened_prompt, user_message, json_mode=json_mode, max_tokens=max_tokens, model=model
                    )
                elif name == "gemini":
                    result = await self._call_gemini(
                        hardened_prompt, user_message, json_mode=json_mode, max_tokens=max_tokens, model_name=model
                    )
                elif name == "openrouter":
                    result = await self._call_openrouter(
                        hardened_prompt, user_message, json_mode=json_mode, max_tokens=max_tokens, model=model
                    )
                else:
                    raise LLMProviderError(f"Unknown provider: {name}")
                self._record_success(result.provider, result.model, failure_chain)
                return result.text
            except Exception as exc:
                logger.warning("%s model %s failed: %s", name, model, exc)
                failure_chain.append({"provider": name, "model": model, "error": str(exc)})
        self._last_call_metadata = {
            "provider": None,
            "model": None,
            "fallback_count": len(failure_chain),
            "fallback_chain": failure_chain,
        }
        raise RuntimeError(self._build_user_facing_failure(failure_chain))

    async def run_agent(self, system_prompt: str, user_message: str, max_tokens: int = 3000) -> str:
        """Structured JSON call for agents and text-extraction analyzers."""
        providers = [
            {"name": "groq", "model": self._groq_agent_model},
            {"name": "gemini", "model": self._gemini_agent_model_name},
            {"name": "openrouter", "model": self._openrouter_agent_model},
        ]
        return await self._run_provider_chain(providers, system_prompt, user_message, json_mode=True, max_tokens=max_tokens)

    async def run_final_agent(self, system_prompt: str, user_message: str) -> str:
        """Final synthesis call: Gemini first, then cheaper Groq/OpenRouter fallbacks."""
        providers = [
            {"name": "gemini", "model": self._gemini_final_model_name},
            {"name": "groq", "model": self._groq_final_model},
            {"name": "groq", "model": self._groq_agent_model},
            {"name": "openrouter", "model": self._openrouter_final_model},
            {"name": "openrouter", "model": self._openrouter_agent_model},
        ]
        return await self._run_provider_chain(providers, system_prompt, user_message, json_mode=True, max_tokens=900)

    async def run_with_search_grounding(
        self,
        system_prompt: str,
        user_message: str,
        location_area: str = "",
    ) -> Optional[str]:
        """
        Runs Gemini inference with Google Search grounding enabled.
        Falls back to the standard agent chain if search grounding fails.
        """
        hardened_prompt = apply_bias_hardening(system_prompt)
        failure_chain: list[dict[str, str]] = []
        if _GEMINI_AVAILABLE and self._gemini_model is not None:
            try:
                search_model = genai.GenerativeModel(
                    self._gemini_agent_model_name,
                    tools=[genai.Tool(google_search_retrieval=genai.GoogleSearchRetrieval())],
                )
                grounded_prompt = (
                    f"{hardened_prompt}\n\n"
                    f"Location context for search: {location_area}, Mumbai, India\n\n"
                    f"{self._normalize_json_prompt(user_message)}"
                )
                response = search_model.generate_content(
                    grounded_prompt,
                    generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=4000),
                )
                text = response.text if response and response.text else None
                if text:
                    self._record_success("gemini_grounded", self._gemini_agent_model_name, failure_chain)
                    return text
                raise LLMProviderError("Gemini grounded search returned empty response")
            except Exception as exc:
                logger.warning("Gemini grounded search failed: %s", exc)
                failure_chain.append(
                    {"provider": "gemini_grounded", "model": self._gemini_agent_model_name, "error": str(exc)}
                )
        text = await self._run_provider_chain(
            [
                {"name": "groq", "model": self._groq_agent_model},
                {"name": "gemini", "model": self._gemini_agent_model_name},
                {"name": "openrouter", "model": self._openrouter_agent_model},
            ],
            system_prompt=hardened_prompt,
            user_message=user_message,
            json_mode=True,
            max_tokens=4000,
        )
        if failure_chain:
            meta = self.get_last_call_metadata()
            meta["fallback_chain"] = failure_chain + meta.get("fallback_chain", [])
            meta["fallback_count"] = len(meta["fallback_chain"])
            self._last_call_metadata = meta
        return text

    async def run_document_analysis(
        self,
        file_bytes: bytes,
        content_type: str,
        analysis_prompt: str,
    ) -> Optional[str]:
        """
        Uses Gemini multimodal to analyze documents from raw bytes.
        Returns None when Gemini document analysis is unavailable or fails.
        """
        if not _GEMINI_AVAILABLE or self._gemini_model is None:
            return None
        uploaded_file = None
        tmp_path = None
        try:
            suffix = ".pdf" if content_type == "application/pdf" else ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            uploaded_file = genai.upload_file(tmp_path, mime_type=content_type)
            doc_model = genai.GenerativeModel("gemini-1.5-pro")
            response = doc_model.generate_content(
                [uploaded_file, apply_bias_hardening(analysis_prompt)],
                generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=4000),
            )
            result_text = response.text if response.text else None
            if result_text:
                self._record_success("gemini_document", "gemini-1.5-pro", [])
            return result_text
        except Exception as exc:
            logger.warning("Gemini document analysis failed: %s", exc)
            self._last_call_metadata = {
                "provider": None,
                "model": "gemini-1.5-pro",
                "fallback_count": 1,
                "fallback_chain": [{"provider": "gemini_document", "model": "gemini-1.5-pro", "error": str(exc)}],
            }
            return None
        finally:
            if uploaded_file is not None:
                try:
                    genai.delete_file(uploaded_file.name)
                except Exception:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    @staticmethod
    def parse_json(raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM JSON: %s...", cleaned[:200])
            return {"error": "Failed to parse agent response", "raw": cleaned[:500]}
