"""
BrochureAnalyzerAgent — Extracts structured property data from a developer
brochure image or PDF page using Gemini's multimodal capability.

This agent does NOT inherit from BaseAgent because it uses Gemini's
multimodal API (image + text input) rather than the standard chat API.
It always uses Gemini regardless of the USE_OLLAMA flag — there is no
Ollama equivalent for multimodal document analysis.

What it does:
    A user uploads a property brochure image or PDF screenshot.
    The agent reads the image using Gemini Vision and extracts every
    financial and legal detail visible in the document.
    The frontend uses the extracted data to pre-fill the financial form
    so the user does not have to manually type property details.

Extracted fields:
    property_price      — base price in rupees
    state               — Indian state for stamp duty lookup
    city                — city name
    property_type       — under_construction or ready_to_move
    area_sqft           — carpet area in square feet
    builder_name        — developer name
    rera_number         — RERA registration number if visible
    possession_date     — expected possession date
    hidden_charges      — any additional charges mentioned beyond base price
    annual_interest_rate — if any bank tie-up rate is mentioned
    confidence          — 0-100 how confident the extraction is
    extraction_notes    — what was found and any ambiguities

Supported file types:
    JPEG, PNG, WebP — direct image analysis
    PDF             — first page analyzed as image (send page as image from frontend)
"""

import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Supported MIME types for Gemini Vision
SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}

EXTRACTION_PROMPT = """
You are analyzing an Indian real estate property brochure, advertisement,
or listing document. Your job is to extract every piece of financial and
legal information that is visible in this document.

Extract the following fields. If a field is not visible or cannot be
determined from the document, use null for that field.

property_price: the base/starting price in rupees as a number only.
    Examples: 8000000 for ₹80 Lakhs, 15000000 for ₹1.5 Crore.
    Do not include GST or other charges — base price only.
    If a price range is shown, use the lower number.

state: the Indian state where the property is located.
    Use lowercase with underscores: maharashtra, karnataka, delhi,
    tamil_nadu, gujarat, rajasthan, west_bengal, telangana,
    andhra_pradesh, punjab, haryana, uttar_pradesh, kerala, goa.

city: the city name as a plain string. Example: "Mumbai", "Bangalore".

property_type: exactly "under_construction" or "ready_to_move".
    Use "under_construction" if the document mentions: under construction,
    new project, possession date, OC pending, pre-launch, new launch.
    Use "ready_to_move" if it mentions: ready to move, immediate possession,
    OC received, completed project.

area_sqft: the carpet area in square feet as a number.
    If only super built-up area is mentioned, use that but note it in extraction_notes.
    If a range is shown, use the smaller number.

builder_name: the developer or builder company name as a string.

rera_number: the RERA registration number if visible. Usually starts with
    P or MahaRERA or similar state prefix. Return as a string.

possession_date: the expected possession or handover date as a string.
    Return exactly as shown in the document — e.g. "December 2026", "Q3 2025".

hidden_charges: a list of strings describing any charges mentioned
    BEYOND the base price. Examples:
    "Parking: ₹3,00,000 extra"
    "Club membership: ₹50,000 compulsory"
    "Maintenance deposit: 24 months advance"
    "Floor rise charges: ₹50 per sq ft per floor"
    If no hidden charges are mentioned, return an empty list.

annual_interest_rate: if a bank tie-up home loan interest rate is mentioned,
    return it as a decimal. Example: 0.085 for 8.5%. Return null if not mentioned.

confidence: your confidence in the extraction from 0 to 100.
    100 = all key fields clearly visible and unambiguous.
    70-99 = most fields clear, some ambiguity.
    40-69 = partial extraction, some fields unclear or missing.
    Below 40 = document is unclear, not a property brochure, or too low resolution.

extraction_notes: a single string describing:
    - What type of document this appears to be
    - Which fields were clearly visible
    - Which fields were ambiguous or estimated
    - Any important information visible that does not fit the above fields
    - Any warnings about data quality

Return ONLY a valid JSON object. No markdown, no explanation, no text outside the JSON.
Start your response with { and end with }.

{
    "property_price": 8000000,
    "state": "maharashtra",
    "city": "Mumbai",
    "property_type": "under_construction",
    "area_sqft": 850,
    "builder_name": "Lodha Group",
    "rera_number": "P51800012345",
    "possession_date": "December 2026",
    "hidden_charges": [
        "Parking: ₹3,00,000 extra",
        "Club membership: ₹50,000 compulsory"
    ],
    "annual_interest_rate": null,
    "confidence": 85,
    "extraction_notes": "Clear property brochure. Base price, area, and builder name clearly visible. RERA number found at bottom of page. Possession date mentioned as December 2026. Two hidden charges explicitly listed. State inferred from city Mumbai."
}
"""


class BrochureAnalyzerAgent:
    """
    Multimodal agent that extracts property details from brochure images.
    Always uses Gemini Vision — no Ollama equivalent exists for this task.
    """

    def __init__(self):
        self._model = None
        self._init_gemini()

    def _init_gemini(self):
        """Initialise the Gemini 2.0 Flash model for multimodal analysis."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self._model = genai.GenerativeModel("gemini-2.0-flash")
            print("[BrochureAnalyzer] Gemini 2.0 Flash initialised for multimodal analysis")
        except Exception as e:
            print(f"[BrochureAnalyzer] Gemini init failed: {e}")
            raise

    async def analyze(self, file_bytes: bytes, mime_type: str) -> dict:
        """
        Analyze a property brochure image or PDF and extract structured data.

        Args:
            file_bytes: Raw bytes of the uploaded file.
            mime_type:  MIME type of the file — must be in SUPPORTED_MIME_TYPES.

        Returns:
            Dict with extracted property fields. All fields are present —
            unextracted fields are null rather than missing. This guarantees
            the frontend can safely access any field without key errors.
        """
        if mime_type not in SUPPORTED_MIME_TYPES:
            return self._unsupported_format_response(mime_type)

        try:
            import google.generativeai as genai

            # Build the multimodal content — image bytes plus the extraction prompt
            image_part = {"mime_type": mime_type, "data": file_bytes}

            response = await asyncio.to_thread(
                self._model.generate_content,
                [EXTRACTION_PROMPT, image_part]
            )

            raw_text = response.text.strip()
            return self._parse_response(raw_text)

        except Exception as e:
            print(f"[BrochureAnalyzer] Extraction failed: {e}")
            return self._error_response(str(e))

    def _parse_response(self, raw: str) -> dict:
        """
        Parse the Gemini response into a clean dict.
        Handles markdown fences and leading text the same way BaseAgent does.
        Merges with a complete default response so all fields are always present.
        """
        cleaned = raw.strip()

        # Strip markdown fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Skip any text before the opening brace
        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            if start != -1:
                cleaned = cleaned[start:]

        # Trim after the last closing brace
        end = cleaned.rfind("}")
        if end != -1:
            cleaned = cleaned[:end + 1]

        try:
            extracted = json.loads(cleaned)
            # Merge with defaults so all keys are always present
            return {**self._default_response(), **extracted}
        except json.JSONDecodeError as e:
            print(f"[BrochureAnalyzer] JSON parse failed: {e}")
            return self._error_response(f"Could not parse extraction response: {e}")

    def _default_response(self) -> dict:
        """
        Complete response with all fields set to null.
        Used as the base that extracted data is merged into so the frontend
        never encounters a KeyError on any field.
        """
        return {
            "property_price": None,
            "state": None,
            "city": None,
            "property_type": None,
            "area_sqft": None,
            "builder_name": None,
            "rera_number": None,
            "possession_date": None,
            "hidden_charges": [],
            "annual_interest_rate": None,
            "confidence": 0,
            "extraction_notes": "No data extracted."
        }

    def _unsupported_format_response(self, mime_type: str) -> dict:
        """Response when the uploaded file type is not supported."""
        return {
            **self._default_response(),
            "confidence": 0,
            "extraction_notes": (
                f"Unsupported file type: {mime_type}. "
                f"Please upload a JPEG, PNG, WebP, or PDF file."
            )
        }

    def _error_response(self, error_message: str) -> dict:
        """Response when the Gemini call fails for any reason."""
        return {
            **self._default_response(),
            "confidence": 0,
            "extraction_notes": f"Extraction failed: {error_message}"
        }