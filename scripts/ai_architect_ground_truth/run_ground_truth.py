from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
CASES_DIR = SCRIPT_DIR / "cases"
RESULTS_DIR = SCRIPT_DIR / "results"

sys.path.insert(0, str(BACKEND_DIR))

import ai_architect_service as svc  # noqa: E402


PLAN_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}


class _NullCacheCollection:
    async def find_one(self, *_args, **_kwargs):
        return None

    async def update_one(self, *_args, **_kwargs):
        return None


class _VisionOnlyDB:
    def __init__(self):
        self.ai_architect_cache = _NullCacheCollection()


@dataclass
class CaseResult:
    case_id: str
    status: str
    analysis_ok: Optional[bool]
    geometry_2d_ok: Optional[bool]
    render_ok: Optional[bool]
    violations: List[str]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_plan(case_dir: Path) -> Optional[Path]:
    for item in sorted(case_dir.iterdir()):
        if item.is_file() and item.stem.lower() == "plan" and item.suffix.lower() in PLAN_SUFFIXES:
            return item
    return None


def _has_real_vision_provider() -> bool:
    return bool(svc._anthropic_api_key() or svc._openai_api_key() or svc._openrouter_api_key())


def _room_names(analysis: Dict[str, Any]) -> List[str]:
    names = []
    for room in analysis.get("detected_rooms") or []:
        if isinstance(room, dict) and room.get("name"):
            names.append(str(room["name"]).strip().lower())
    return names


def _feature_count(analysis: Dict[str, Any], key: str) -> int:
    value = (analysis.get("detected_elements") or {}).get(key) or []
    return len(value) if isinstance(value, list) else 0


def _contains_room(room_names: List[str], expected: str) -> bool:
    needle = expected.lower()
    return any(needle in room or room in needle for room in room_names)


def _build_job(case_dir: Path, expected: Dict[str, Any], plan_path: Path) -> Dict[str, Any]:
    payload = plan_path.read_bytes()
    return {
        "plan_type_selected": expected.get("plan_type") or "auto",
        "project_variant_selected": "premium_suite",
        "project_goal": "Ground truth validation",
        "style_selected": "Moderno luxury",
        "priorities": ["funzionalita", "luce naturale"],
        "uploaded_file_path": str(plan_path),
        "uploaded_file_url": None,
        "processed_file_url": None,
        "original_filename": plan_path.name,
        "file_type": plan_path.suffix.lower().lstrip("."),
        "mime_type": svc._guess_mime(plan_path, plan_path.suffix.lower().lstrip(".")),
        "file_hash": hashlib.sha256(payload).hexdigest(),
        "usage_context": "staff",
        "case_dir": str(case_dir),
    }


def _evaluate_analysis(analysis: Dict[str, Any], expected: Dict[str, Any]) -> tuple[bool, List[str]]:
    spec = expected.get("expected") or {}
    violations: List[str] = []
    room_names = _room_names(analysis)
    room_count = len(room_names)
    min_rooms = int(spec.get("room_count_min") or 0)
    max_rooms = int(spec.get("room_count_max") or 999)

    if room_count < min_rooms or room_count > max_rooms:
        violations.append(f"room_count fuori range: {room_count} non in [{min_rooms}, {max_rooms}]")

    for room in spec.get("must_have_rooms") or []:
        if not _contains_room(room_names, str(room)):
            violations.append(f"stanza obbligatoria mancante: {room}")

    if spec.get("external_openings_present"):
        openings = (
            _feature_count(analysis, "windows")
            + _feature_count(analysis, "doors")
            + _feature_count(analysis, "balconies")
            + _feature_count(analysis, "entrances")
        )
        if openings <= 0:
            violations.append("aperture esterne/accessi non rilevati")

    expected_balconies = spec.get("balconies_count")
    if expected_balconies is not None and _feature_count(analysis, "balconies") != int(expected_balconies):
        violations.append(
            f"numero balconi incoerente: attesi {expected_balconies}, rilevati {_feature_count(analysis, 'balconies')}"
        )

    if spec.get("load_bearing_walls_present") and _feature_count(analysis, "structural_constraints_uncertain") <= 0:
        violations.append("vincoli strutturali/muri portanti non marcati da verificare")

    return len(violations) == 0, violations


def _evaluate_geometry(job: Dict[str, Any], analysis: Dict[str, Any], expected: Dict[str, Any]) -> tuple[bool, List[str]]:
    spec = expected.get("expected") or {}
    mode = "redistributed" if (expected.get("plan_type") or "existing_state") == "existing_state" else "defined"
    details = svc._plan_details_json({**job, "vision_analysis": analysis}, mode)
    violations: List[str] = []

    if spec.get("must_not_invent_rooms"):
        room_count = len(details.get("rooms") or [])
        max_rooms = int(spec.get("room_count_max") or 999)
        if room_count > max_rooms:
            violations.append(f"2D rooms oltre massimo atteso: {room_count} > {max_rooms}")

    expected_balconies = spec.get("balconies_count")
    if expected_balconies is not None:
        counts = ((details.get("as_built_invariants") or {}).get("critical_counts") or {})
        actual = int(counts.get("balconies_loggias_terraces") or 0)
        if actual != int(expected_balconies):
            violations.append(f"2D invariant balconi incoerente: attesi {expected_balconies}, rilevati {actual}")

    return len(violations) == 0, violations


async def _run_case(case_dir: Path) -> CaseResult:
    expected_path = case_dir / "expected.json"
    case_id = case_dir.name
    if not expected_path.exists():
        return CaseResult(case_id, "skipped_missing_expected", None, None, None, ["expected.json mancante"])

    expected = _load_json(expected_path)
    case_id = expected.get("case_id") or case_id
    plan_path = _find_plan(case_dir)
    if not plan_path:
        return CaseResult(case_id, "skipped_missing_plan", None, None, None, ["plan.* mancante"])

    if not _has_real_vision_provider():
        return CaseResult(case_id, "not_evaluable_no_vision_provider", None, None, None, ["provider vision reale non configurato"])

    job = _build_job(case_dir, expected, plan_path)
    try:
        analysis, _cache_hit = await svc._vision_analysis(_VisionOnlyDB(), job)
    except Exception as exc:
        return CaseResult(case_id, "not_evaluable_vision_failed", None, None, None, [str(exc)[:500]])

    if analysis.get("is_fallback") or analysis.get("vision_fallback"):
        return CaseResult(case_id, "not_evaluable_fallback", None, None, None, ["analysis fallback non ammessa nel ground truth"])

    analysis_ok, analysis_violations = _evaluate_analysis(analysis, expected)
    geometry_ok, geometry_violations = _evaluate_geometry(job, analysis, expected)
    violations = analysis_violations + geometry_violations
    status = "passed" if analysis_ok and geometry_ok else "failed"
    return CaseResult(case_id, status, analysis_ok, geometry_ok, None, violations)


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _render_report(results: List[CaseResult]) -> tuple[str, bool]:
    evaluable = [result for result in results if result.analysis_ok is not None]
    total = len(evaluable)
    analysis_ok = sum(1 for result in evaluable if result.analysis_ok)
    geometry_ok = sum(1 for result in evaluable if result.geometry_2d_ok)
    hard_fails = sum(1 for result in evaluable if result.violations)

    analysis_rate = _percent(analysis_ok, total)
    geometry_rate = _percent(geometry_ok, total)
    hard_fail_rate = _percent(hard_fails, total)
    go = total > 0 and analysis_rate >= 70.0 and geometry_rate >= 50.0 and hard_fail_rate < 10.0

    lines = [
        "# AI Architect Ground Truth Report",
        "",
        f"Run: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Case | Stato | Analisi OK | 2D OK | Render OK | Violazioni |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        violations = "; ".join(result.violations) if result.violations else "-"
        lines.append(
            f"| {result.case_id} | {result.status} | {result.analysis_ok} | "
            f"{result.geometry_2d_ok} | {result.render_ok} | {violations} |"
        )

    lines.extend(
        [
            "",
            "## Aggregati",
            "",
            f"- Case valutabili: {total}",
            f"- Analisi accettabili: {analysis_rate}%",
            f"- 2D non contraddittorie: {geometry_rate}%",
            f"- Errori gravi: {hard_fail_rate}%",
            "",
            "## Go/No-Go",
            "",
            "- GO pubblico se: analisi accettabili >= 70%, 2D non contraddittorie >= 50%, errori gravi < 10%.",
            f"- Verdetto: {'GO pubblico' if go else 'NO-GO: resta beta interna'}",
            "",
        ]
    )
    return "\n".join(lines), go


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run AI Architect ground truth validation.")
    parser.add_argument("--cases-dir", type=Path, default=CASES_DIR)
    args = parser.parse_args()

    case_dirs = [path for path in sorted(args.cases_dir.glob("case_*")) if path.is_dir()]
    if not case_dirs:
        results = [CaseResult("none", "skipped_no_cases", None, None, None, ["nessun case_* trovato"])]
    else:
        results = [await _run_case(case_dir) for case_dir in case_dirs]

    report, go = _render_report(results)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report scritto in: {report_path}")
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
