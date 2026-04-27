"""
Mumbai real estate benchmark loader with semantic area name matching.

Lookup chain (Task 2.3):
  1. Exact key match
  2. Exact normalized name match
  3. AREA_ALIASES lookup
  4. BenchmarkMatcher semantic similarity (sentence-transformers)
  5. difflib fuzzy fallback

BenchmarkResult namedtuple (Task 2.4) carries coverage metadata alongside
the benchmark data, enabling the frontend to display confidence warnings.
"""
from __future__ import annotations

import json
import logging
from collections import namedtuple
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent / "data" / "mumbai_benchmarks.json"
_cache: Optional[dict] = None

BenchmarkResult = namedtuple(
    "BenchmarkResult",
    ["data", "coverage_level", "confidence_score", "warning_message"],
)

# Common alias variants → canonical benchmark key
AREA_ALIASES: dict[str, str] = {
    "bandra": "bandra_west",
    "andheri": "andheri_west",
    "lower parel": "lower_parel",
    "bkc": "bandra_west",  # no BKC key; nearest is Bandra West
    "kurla": "bandra_west",
    "worlee": "worli",
    "worlee": "worli",
    "goregaon": "goregaon_west",
    "borivali": "borivali_west",
    "ghatkopar": "ghatkopar_west",
    "malad": "malad_west",
    "kandivali": "kandivali_west",
    "mulund": "mulund_west",
    "thane": "thane_west",
    "navi mumbai": "navi_mumbai_vashi",
    "vashi": "navi_mumbai_vashi",
    "kharghar": "navi_mumbai_kharghar",
    "panvel": "navi_mumbai_panvel",
    "nerul": "navi_mumbai_nerul",
    "airoli": "navi_mumbai_airoli",
    "belapur": "navi_mumbai_belapur",
    "jogeshwari west": "jogeshwari",
    "jogeshwari east": "jogeshwari",
    "vile parle": "vile_parle",
    "ville parle": "vile_parle",
    "santacruz west": "santacruz",
    "santacruz east": "santacruz",
    "mira road east": "mira_road",
    "mira bhayandar": "mira_road",
    "dahisar west": "dahisar",
    "dahisar east": "dahisar",
    "kalyan west": "kalyan",
    "kalyan east": "kalyan",
}


@dataclass
class AreaBenchmark:
    key: str
    name: str
    price_min: float
    price_median: float
    price_max: float
    maintenance_typical: float
    rental_yield_pct: float
    distance_to_bkc_km: float
    distance_to_lower_parel_km: float
    metro_connectivity: bool
    infrastructure_notes: str
    flood_risk: str
    data_as_of: str


class BenchmarkMatcher:
    """
    Semantic area name matcher using sentence-transformer embeddings.

    Loads model once at startup and caches area embeddings in memory.
    Falls back to difflib if model loading fails — graceful degradation.
    """

    def __init__(self, benchmark_keys: list[str], benchmark_names: list[str]) -> None:
        """
        Initialize with all area keys and display names from benchmark data.

        Args:
            benchmark_keys: List of area keys (e.g. "andheri_west").
            benchmark_names: Corresponding display names (e.g. "Andheri West").
        """
        self._keys = benchmark_keys
        self._names = benchmark_names
        self._model = None
        self._embeddings = None
        self._available = False
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            texts = benchmark_keys + benchmark_names
            self._embeddings = self._model.encode(texts, normalize_embeddings=True)
            self._np = np
            self._available = True
            logger.debug("BenchmarkMatcher loaded %d area embeddings", len(texts))
        except Exception as exc:
            logger.warning("BenchmarkMatcher unavailable (sentence-transformers error: %s). "
                           "Falling back to difflib.", exc)

    def find_best_match(self, user_input: str, threshold: float = 0.65) -> tuple[str | None, float]:
        """
        Returns (best_matching_key, confidence_score) or (None, 0.0) if below threshold.

        Uses cosine similarity of sentence embeddings. The input is compared against
        all area keys and display names; the best-scoring key is returned.

        Args:
            user_input: User-entered area name string.
            threshold: Minimum cosine similarity to consider a match. Default 0.65.

        Returns:
            Tuple of (matched_key, score) or (None, 0.0).
        """
        if not self._available or self._model is None:
            return None, 0.0
        try:
            q_emb = self._model.encode([user_input], normalize_embeddings=True)
            sims = (self._embeddings @ q_emb.T).flatten()
            best_idx = int(sims.argmax())
            best_score = float(sims[best_idx])
            if best_score < threshold:
                return None, best_score
            n = len(self._keys)
            matched_key = self._keys[best_idx] if best_idx < n else self._keys[best_idx - n]
            return matched_key, best_score
        except Exception as exc:
            logger.warning("BenchmarkMatcher.find_best_match failed: %s", exc)
            return None, 0.0


_matcher: Optional[BenchmarkMatcher] = None


def _load() -> dict:
    global _cache
    if _cache is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def _get_matcher() -> BenchmarkMatcher:
    global _matcher
    if _matcher is None:
        data = _load()
        keys = list(data.keys())
        names = [data[k]["name"] for k in keys]
        _matcher = BenchmarkMatcher(benchmark_keys=keys, benchmark_names=names)
    return _matcher


def _normalize(name: str) -> str:
    return (name.lower().strip().replace("-", " ").replace("_", " ")
            .replace("(", "").replace(")", "").replace(",", ""))


def _build(key: str, raw: dict) -> AreaBenchmark:
    return AreaBenchmark(
        key=key, name=raw["name"],
        price_min=raw["avg_price_per_sqft"]["min"],
        price_median=raw["avg_price_per_sqft"]["median"],
        price_max=raw["avg_price_per_sqft"]["max"],
        maintenance_typical=raw["maintenance_per_sqft_monthly"]["typical"],
        rental_yield_pct=raw["rental_yield_pct"],
        distance_to_bkc_km=raw["distance_to_bkc_km"],
        distance_to_lower_parel_km=raw["distance_to_lower_parel_km"],
        metro_connectivity=raw["metro_connectivity"],
        infrastructure_notes=raw["infrastructure_notes"],
        flood_risk=raw["flood_risk"],
        data_as_of=raw["data_as_of"],
    )


def lookup_area(user_input: str) -> BenchmarkResult:
    """
    Look up benchmark data for a Mumbai area using a 5-step matching chain.

    Chain:
      1. Exact key match (fastest)
      2. Exact normalized display name match
      3. AREA_ALIASES lookup (common variant spellings)
      4. BenchmarkMatcher semantic similarity (sentence-transformers)
      5. difflib fuzzy fallback

    Args:
        user_input: User-entered area name string.

    Returns:
        BenchmarkResult namedtuple with (data, coverage_level, confidence_score, warning_message).
        data is AreaBenchmark or None. coverage_level is "full", "partial", or "default".
    """
    data = _load()
    if not user_input:
        return BenchmarkResult(data=None, coverage_level="default",
                               confidence_score=0.0, warning_message=_default_warning(""))

    normalized = _normalize(user_input)
    key_attempt = normalized.replace(" ", "_")

    # Step 1: exact key match
    if key_attempt in data:
        return BenchmarkResult(data=_build(key_attempt, data[key_attempt]),
                               coverage_level="full", confidence_score=1.0,
                               warning_message=None)

    # Step 2: exact normalized name match
    name_map: dict[str, str] = {}
    for key, info in data.items():
        name_map[_normalize(info["name"])] = key
    if normalized in name_map:
        matched_key = name_map[normalized]
        return BenchmarkResult(data=_build(matched_key, data[matched_key]),
                               coverage_level="full", confidence_score=1.0,
                               warning_message=None)

    # Step 3: alias lookup
    alias_key = AREA_ALIASES.get(normalized)
    if alias_key and alias_key in data:
        return BenchmarkResult(data=_build(alias_key, data[alias_key]),
                               coverage_level="full", confidence_score=0.95,
                               warning_message=None)

    # Step 4: semantic similarity
    try:
        matcher = _get_matcher()
        semantic_key, score = matcher.find_best_match(user_input)
        if semantic_key and semantic_key in data:
            coverage = "full" if score >= 0.85 else "partial"
            warn = None if coverage == "full" else _partial_warning(
                user_input, data[semantic_key]["name"], score)
            return BenchmarkResult(data=_build(semantic_key, data[semantic_key]),
                                   coverage_level=coverage,
                                   confidence_score=round(score, 3),
                                   warning_message=warn)
    except Exception as exc:
        logger.debug("Semantic matching error: %s", exc)

    # Step 5: difflib fuzzy fallback
    matches = get_close_matches(normalized, name_map.keys(), n=1, cutoff=0.6)
    if matches:
        matched_key = name_map[matches[0]]
        matched_name = data[matched_key]["name"]
        return BenchmarkResult(
            data=_build(matched_key, data[matched_key]),
            coverage_level="partial",
            confidence_score=0.6,
            warning_message=_partial_warning(user_input, matched_name, 0.6),
        )
    key_matches = get_close_matches(key_attempt, data.keys(), n=1, cutoff=0.6)
    if key_matches:
        matched_name = data[key_matches[0]]["name"]
        return BenchmarkResult(
            data=_build(key_matches[0], data[key_matches[0]]),
            coverage_level="partial",
            confidence_score=0.6,
            warning_message=_partial_warning(user_input, matched_name, 0.6),
        )

    return BenchmarkResult(data=None, coverage_level="default",
                           confidence_score=0.0,
                           warning_message=_default_warning(user_input))


def _default_warning(area: str) -> str:
    return (
        f"No benchmark data available for '{area}'. Analysis uses national "
        f"averages (rental yield: 2.5%, maintenance: ₹5.5/sqft). "
        f"Price verdict confidence: LOW. Consider researching local market "
        f"rates independently before making a decision."
    )


def _partial_warning(user_area: str, matched_area: str, score: float) -> str:
    return (
        f"Using approximate benchmark data for '{matched_area}' as closest "
        f"match to '{user_area}'. Confidence: {score:.0%}. Verify local rates."
    )


def list_areas() -> list:
    """Return all available area display names."""
    return [info["name"] for info in _load().values()]


def get_maintenance_estimate(user_area: str) -> float:
    """Return monthly maintenance estimate per sqft for the given area. Defaults to 5.5."""
    result = lookup_area(user_area)
    return result.data.maintenance_typical if result.data else 5.5


def get_rental_yield(user_area: str) -> float:
    """Return annual rental yield percentage for the given area. Defaults to 2.5."""
    result = lookup_area(user_area)
    return result.data.rental_yield_pct if result.data else 2.5


def get_area_benchmark_result(user_area: str) -> BenchmarkResult:
    """Return the full BenchmarkResult with coverage metadata for a given area."""
    return lookup_area(user_area)
