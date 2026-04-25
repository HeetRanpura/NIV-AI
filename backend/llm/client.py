"""
LLM provider abstraction for Niv AI.
Groq = primary (agents 1-5). Gemini = architectural spine (agent 6, search grounding, documents).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Optional

from groq import AsyncGroq, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    import google.api_core.exceptions
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False


class LLMClient:
    def __init__(self) -> None:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise RuntimeError("GROQ_API_KEY environment variable is required")
        self._groq = AsyncGroq(api_key=groq_key)
        self._gemini_model = None
        if _GEMINI_AVAILABLE:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                self._gemini_model = genai.GenerativeModel("gemini-2.0-flash")
                logger.info("Gemini 2.0 Flash configured as architectural spine")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15),
           retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
           reraise=True)
    async def _call_groq(self, system_prompt: str, user_message: str,
                         json_mode: bool = False, max_tokens: int = 3000) -> str:
        response = await self._groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_message}],
            temperature=0.1,
            response_format={"type": "json_object"} if json_mode else None,
            max_tokens=max_tokens)
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Groq returned empty response")
        return content

    async def _call_gemini(self, system_prompt: str, user_message: str) -> Optional[str]:
        if self._gemini_model is None:
            return None
        try:
            logger.info("Gemini 2.0 Flash inference (final agent)")
            response = self._gemini_model.generate_content(
                f"{system_prompt}\n\n{user_message}",
                generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=4000))
            return response.text if response.text else None
        except Exception as e:
            logger.warning("Gemini failed (%s), falling back to Groq", e)
            return None

    async def run_agent(self, system_prompt: str, user_message: str, max_tokens: int = 3000) -> str:
        """Groq llama-3.3-70b — agents 1-5, fast JSON mode."""
        return await self._call_groq(system_prompt, user_message, json_mode=True, max_tokens=max_tokens)

    async def run_final_agent(self, system_prompt: str, user_message: str) -> str:
        """Gemini 2.0 Flash primary → Groq fallback — agent 6."""
        gemini_result = await self._call_gemini(system_prompt, user_message)
        if gemini_result:
            return gemini_result
        return await self._call_groq(system_prompt, user_message, json_mode=True, max_tokens=4000)

    async def run_with_search_grounding(
        self,
        system_prompt: str,
        user_message: str,
        location_area: str = "",
    ) -> Optional[str]:
        """
        Runs Gemini inference with Google Search grounding enabled.
        Used by Agent 4 to fetch live Mumbai micro-market data.
        Falls back to non-grounded Gemini if search grounding fails.

        Args:
            system_prompt: Agent system prompt.
            user_message: User message with property details.
            location_area: Mumbai area name to target the search.

        Returns:
            Model response string with grounded search results, or None on failure.
        """
        if not _GEMINI_AVAILABLE or self._gemini_model is None:
            return None
        try:
            search_model = genai.GenerativeModel(
                "gemini-2.0-flash",
                tools=[genai.Tool(google_search_retrieval=genai.GoogleSearchRetrieval())],
            )
            grounded_prompt = (
                f"{system_prompt}\n\n"
                f"Location context for search: {location_area}, Mumbai, India\n\n"
                f"{user_message}"
            )
            logger.info("Gemini 2.0 Flash search grounding call, location=%s", location_area)
            response = search_model.generate_content(
                grounded_prompt,
                generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=4000),
            )
            return response.text if response.text else None
        except google.api_core.exceptions.GoogleAPIError as exc:
            logger.warning("Gemini search grounding GoogleAPIError: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Gemini search grounding failed: %s", exc)
            return None

    async def run_document_analysis(
        self,
        file_bytes: bytes,
        content_type: str,
        analysis_prompt: str,
    ) -> Optional[str]:
        """
        Uses Gemini 1.5 Pro multimodal to analyze documents from raw bytes.
        Processes PDFs natively including tables, stamps, and handwriting
        that OCR-based extraction misses entirely.

        Args:
            file_bytes: Raw file bytes (PDF or image).
            content_type: MIME type string.
            analysis_prompt: What to extract from the document.

        Returns:
            Analysis string from Gemini, or None if upload/generation fails.
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

            logger.info(
                "Gemini 1.5 Pro document upload, content_type=%s, size=%d bytes",
                content_type,
                len(file_bytes),
            )
            uploaded_file = genai.upload_file(tmp_path, mime_type=content_type)

            doc_model = genai.GenerativeModel("gemini-1.5-pro")
            response = doc_model.generate_content(
                [uploaded_file, analysis_prompt],
                generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=4000),
            )
            result_text = response.text if response.text else None
            logger.info("Gemini 1.5 Pro document analysis complete")
            return result_text
        except google.api_core.exceptions.GoogleAPIError as exc:
            logger.warning("Gemini document analysis GoogleAPIError: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Gemini document analysis failed: %s", exc)
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
