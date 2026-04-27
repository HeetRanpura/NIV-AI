"""
Visual property inspection using Gemini multimodal.

Users photograph the property (rooms, exterior, structural elements).
Gemini analyzes images and returns a structured condition report with
a visual_inspection_score (0-100) that feeds into Agent 4.

No competing proptech tool in India does visual AI property assessment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.llm.client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class PropertyInspectionResult:
    """Structured result from Gemini visual property inspection."""
    visual_inspection_score: int
    condition_grade: str
    visible_defects: list[str] = field(default_factory=list)
    positive_observations: list[str] = field(default_factory=list)
    structural_concerns: list[str] = field(default_factory=list)
    maintenance_flags: list[str] = field(default_factory=list)
    estimated_renovation_cost_range: str = "Unknown"
    recommendation: str = ""
    images_analyzed: int = 0
    data_source: str = "unavailable"


async def inspect_property_images(
    llm: "LLMClient",
    image_files: list[bytes],
    content_types: list[str],
    property_context: dict,
) -> PropertyInspectionResult:
    """
    Analyzes property photographs using Gemini 1.5 Pro multimodal.

    Evaluates: water damage, structural cracks, plumbing/electrical
    condition, ventilation, building exterior, parking quality.

    Scoring weights:
      Structural integrity: 40%
      Water and moisture: 25%
      Electrical and plumbing: 20%
      Aesthetic and maintenance: 15%

    Args:
        llm: LLM client with run_document_analysis capability.
        image_files: List of raw image bytes (max 5 images).
        content_types: Corresponding MIME types.
        property_context: Dict with location_area, configuration,
            property_price.

    Returns:
        PropertyInspectionResult. Returns unavailable result if
        multimodal analysis not configured or all images fail.
    """
    if not hasattr(llm, "run_document_analysis") or not image_files:
        return _unavailable_result()

    from backend.utils.sanitize import wrap_user_content
    location = wrap_user_content(property_context.get("location_area", "Mumbai"), "location")
    config = wrap_user_content(property_context.get("configuration", "2BHK"), "config")

    prompt = (
        f"You are a structural engineer. Inspect the property photograph. "
        f"Context — location: {location}, configuration: {config}. "
        f"Identify visible defects, water damage, structural concerns, "
        f"and positive features. "
        f"Return ONLY JSON with: "
        f"structural_score (0-100), water_score (0-100), "
        f"electrical_score (0-100), aesthetic_score (0-100), "
        f"visible_defects (list), positive_observations (list), "
        f"structural_concerns (list), maintenance_flags (list), "
        f"estimated_renovation_cost_range (string like 'Rs.2-5 Lakhs'), "
        f"recommendation (one sentence)."
    )

    all_defects: list[str] = []
    all_positive: list[str] = []
    all_structural: list[str] = []
    all_maintenance: list[str] = []
    scores: list[float] = []

    for i, (img_bytes, ctype) in enumerate(zip(image_files, content_types)):
        try:
            response = await llm.run_document_analysis(img_bytes, ctype, prompt)
            if not response:
                continue
            parsed = llm.parse_json(response)
            if "error" in parsed:
                continue
            s = (
                parsed.get("structural_score", 70) * 0.40
                + parsed.get("water_score", 70) * 0.25
                + parsed.get("electrical_score", 70) * 0.20
                + parsed.get("aesthetic_score", 70) * 0.15
            )
            scores.append(s)
            all_defects.extend(parsed.get("visible_defects", []))
            all_positive.extend(parsed.get("positive_observations", []))
            all_structural.extend(parsed.get("structural_concerns", []))
            all_maintenance.extend(parsed.get("maintenance_flags", []))
        except Exception as exc:
            logger.warning("Image %d inspection failed: %s", i, exc)
            continue

    if not scores:
        return _unavailable_result()

    final_score = round(sum(scores) / len(scores))
    grade = (
        "Excellent" if final_score >= 80
        else "Good" if final_score >= 65
        else "Fair" if final_score >= 50
        else "Poor" if final_score >= 35
        else "Critical"
    )

    return PropertyInspectionResult(
        visual_inspection_score=final_score,
        condition_grade=grade,
        visible_defects=list(dict.fromkeys(all_defects))[:6],
        positive_observations=list(dict.fromkeys(all_positive))[:4],
        structural_concerns=list(dict.fromkeys(all_structural))[:4],
        maintenance_flags=list(dict.fromkeys(all_maintenance))[:4],
        estimated_renovation_cost_range=_aggregate_renovation_range(all_defects),
        recommendation=(
            f"Condition grade: {grade}. "
            f"Score {final_score}/100 based on {len(scores)} image(s)."
        ),
        images_analyzed=len(scores),
        data_source="gemini_vision",
    )


def _unavailable_result() -> PropertyInspectionResult:
    """Returns a default unavailable result without raising."""
    return PropertyInspectionResult(
        visual_inspection_score=0,
        condition_grade="Unknown",
        recommendation="Upload property photographs for AI visual inspection.",
        data_source="unavailable",
    )


def _aggregate_renovation_range(defects: list[str]) -> str:
    """Rough cost range based on defect count — no external call needed."""
    count = len(defects)
    if count == 0:
        return "Rs.0-1 Lakh"
    if count <= 2:
        return "Rs.1-3 Lakhs"
    if count <= 4:
        return "Rs.3-7 Lakhs"
    return "Rs.7-15 Lakhs"
