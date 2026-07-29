from __future__ import annotations

import re
from collections import Counter
from typing import Any

from tools._shared import fold_text, terms


PROHIBITION_MARKERS = (
    "do not", "must not", "never", "prohibited",
    "khong duoc", "khong bao gio", "cam",
)
REQUIREMENT_MARKERS = (
    "must", "required", "requires", "need to", "ask for", "include",
    "keep", "redact", "use an approved", "phai", "can",
)
PERMISSION_MARKERS = (
    "may", "allowed", "can be", "co the", "duoc phep",
)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for",
    "from", "if", "in", "into", "is", "it", "of", "on", "or", "the",
    "their", "this", "to", "with", "without", "user", "users", "must",
    "should", "can", "may", "do", "not", "only", "when",
}


def _sentences(value: str) -> list[str]:
    chunks = re.split(r"(?:^|\s)-\s+|(?<=[.!?])\s+", value.strip())
    return [chunk.strip(" \t\r\n-") for chunk in chunks if chunk.strip(" \t\r\n-")]


def _modality(sentence: str) -> str:
    folded = fold_text(sentence)
    if any(marker in folded for marker in PROHIBITION_MARKERS):
        return "prohibition"
    if any(marker in folded for marker in PERMISSION_MARKERS):
        return "permission"
    if any(marker in folded for marker in REQUIREMENT_MARKERS):
        return "requirement"
    return "guidance"


def _content_terms(value: str) -> set[str]:
    return {
        term for term in terms(value)
        if len(term) > 2 and term not in STOPWORDS
    }


def _normalize_section(raw: Any, index: int) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(raw, dict):
        return None, [f"item_{index}_must_be_an_object"]

    facts = str(
        raw.get("facts") or raw.get("content") or raw.get("text") or ""
    ).strip()
    issues: list[str] = []
    if not facts:
        issues.append(f"item_{index}_missing_facts")

    return {
        "evidence_id": f"P{index}",
        "doc_id": str(raw.get("doc_id") or "").strip(),
        "policy_area": str(raw.get("policy_area") or "unknown").strip(),
        "title": str(
            raw.get("title") or raw.get("document_title") or "Untitled policy"
        ).strip(),
        "section": str(
            raw.get("section") or raw.get("section_title") or "Unspecified section"
        ).strip(),
        "facts": facts,
        "source": str(raw.get("source") or "Unknown source").strip(),
        "source_path": str(raw.get("source_path") or raw.get("source") or "").strip(),
        "effective_date": (
            str(raw.get("effective_date")).strip()
            if raw.get("effective_date") is not None
            else None
        ),
    }, issues


def compare_policy_sections(
    policy_sections: list[dict[str, Any]],
    comparison_focus: str = "",
) -> dict[str, Any]:
    """Compare supplied policy evidence without searching or inventing rules."""
    if not isinstance(policy_sections, list):
        return {
            "error": "invalid_policy_sections",
            "message": "policy_sections must be a list.",
        }
    if len(policy_sections) < 2:
        return {
            "error": "insufficient_policy_sections",
            "message": "At least two policy sections are required.",
            "received": len(policy_sections),
        }

    normalized: list[dict[str, Any]] = []
    validation_issues: list[str] = []
    for index, raw in enumerate(policy_sections, start=1):
        section, issues = _normalize_section(raw, index)
        validation_issues.extend(issues)
        if section is not None:
            normalized.append(section)

    if len(normalized) < 2 or any(not section["facts"] for section in normalized):
        return {
            "error": "missing_policy_evidence",
            "message": "Every section must contain facts, content, or text.",
            "validation_issues": validation_issues,
        }

    focus_terms = _content_terms(comparison_focus)
    topic_counts: Counter[str] = Counter()
    all_rules: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for section in normalized:
        section_terms = _content_terms(
            " ".join([
                section["policy_area"],
                section["title"],
                section["section"],
                section["facts"],
            ])
        )
        topic_counts.update(section_terms)

        section_rules: list[dict[str, Any]] = []
        for sentence in _sentences(section["facts"]):
            rule = {
                "evidence_id": section["evidence_id"],
                "modality": _modality(sentence),
                "text": sentence,
            }
            all_rules.append(rule)
            section_rules.append(rule)

        summaries.append({
            "evidence_id": section["evidence_id"],
            "policy_area": section["policy_area"],
            "title": section["title"],
            "section": section["section"],
            "focus_match": sorted(focus_terms & section_terms) if focus_terms else [],
            "rules": section_rules,
        })

    possible_tensions: list[dict[str, Any]] = []
    for left_index, left in enumerate(all_rules):
        for right in all_rules[left_index + 1:]:
            if left["evidence_id"] == right["evidence_id"]:
                continue
            modalities = {left["modality"], right["modality"]}
            if "prohibition" not in modalities or not (
                "permission" in modalities or "requirement" in modalities
            ):
                continue
            overlap = sorted(
                _content_terms(left["text"]) & _content_terms(right["text"])
            )
            if len(overlap) < 2:
                continue
            possible_tensions.append({
                "status": "manual_review_required",
                "shared_terms": overlap,
                "left": left,
                "right": right,
                "note": (
                    "Lexical overlap with different rule modalities; "
                    "this is not a legal conclusion."
                ),
            })

    sources = [{
        "evidence_id": section["evidence_id"],
        "doc_id": section["doc_id"],
        "policy_area": section["policy_area"],
        "title": section["title"],
        "section": section["section"],
        "source": section["source"],
        "source_path": section["source_path"],
        "effective_date": section["effective_date"],
    } for section in normalized]

    focused_ids = [
        summary["evidence_id"] for summary in summaries
        if summary["focus_match"]
    ]
    return {
        "error": None,
        "tool": "policy_compare",
        "comparison_focus": comparison_focus,
        "section_count": len(normalized),
        "shared_topics": sorted(
            term for term, count in topic_counts.items() if count >= 2
        ),
        "section_summaries": summaries,
        "combined_requirements": [
            rule for rule in all_rules
            if rule["modality"] in {"requirement", "prohibition"}
        ],
        "permissions": [
            rule for rule in all_rules if rule["modality"] == "permission"
        ],
        "possible_tensions": possible_tensions,
        "focus_coverage": {
            "evidence_ids": focused_ids,
            "covered": not focus_terms or bool(focused_ids),
            "note": (
                "Focus coverage is lexical evidence only."
                if focus_terms else "No comparison focus was supplied."
            ),
        },
        "sources": sources,
        "validation_issues": validation_issues,
        "trust_boundary": (
            "Comparison uses only supplied policy facts. Possible tensions "
            "require human review and are not legal conclusions."
        ),
    }
