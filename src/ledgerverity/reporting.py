"""Conservative, deterministic reporting for untrusted local comparisons."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

CONTRACT = "ledgerverity.reconciliation-report.v1"
MAX_REPORT_BYTES = 2_000_000
GUIDANCE = {
    "SOURCE_ONLY_OBSERVATION": "Check the export query, filters and exact ledger-range coverage before calling this an omission.",
    "CANDIDATE_ONLY_OBSERVATION": "Check source completeness, transaction placement and export transform revision.",
    "COLUMN_INTEGRITY_DIFFERENCE": "Compare the embedded DiagnosticEvent XDR with the candidate's inline columns.",
    "TRANSACTION_OUTCOME_DIFFERENCE": "Inspect the original XDR result code and export successful field.",
    "UNMATCHABLE_CANDIDATE": "Export the unmodified diagnostic wrapper XDR needed for exact matching.",
}


class ReportingError(ValueError):
    pass


def sha256_bounded(path: Path, limit: int) -> str:
    try:
        if not path.is_file() or path.stat().st_size > limit:
            raise ReportingError("Missing or oversized evidence input")
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as file:
            while True:
                chunk = file.read(65536)
                if not chunk:
                    return digest.hexdigest()
                size += len(chunk)
                if size > limit:
                    raise ReportingError("Evidence file changed or grew beyond limit")
                digest.update(chunk)
    except OSError as exc:
        raise ReportingError("Cannot fingerprint evidence input") from exc


def annotate_report(report: dict[str, Any], source: Path, candidate: Path, scope: Path) -> dict[str, Any]:
    """Additive report contract v1; preserve existing keys and conservative status."""
    from .formats import MAX_FILE_BYTES, MAX_MANIFEST_BYTES
    from .source import MAX_CAPTURE_BYTES
    if report.get("schema_version") != 1 or report.get("status") not in ("INCONCLUSIVE", "REVIEW_REQUIRED"):
        raise ReportingError("Unsupported report schema/status")
    for key in ("reconciliation_proven", "source_provenance_verified",
                "network_identity_independently_verified", "candidate_export_coverage_verified"):
        if report.get(key) is not False:
            raise ReportingError("Unsafe authentication or completeness claim")
    src_digest = sha256_bounded(source, MAX_CAPTURE_BYTES)
    if src_digest != report.get("source_capture_sha256"):
        raise ReportingError("Source input changed during comparison")
    enriched = dict(report)
    enriched["report_contract"] = CONTRACT
    enriched["evidence_fingerprints"] = {
        "source_capture_sha256": src_digest,
        "candidate_file_sha256": sha256_bounded(candidate, MAX_FILE_BYTES),
        "scope_manifest_sha256": sha256_bounded(scope, MAX_MANIFEST_BYTES),
    }
    enriched["evidence_gates"] = {
        "captured_ledger_range_complete": report["source_range_observed_complete"] is True,
        "independent_source_provenance": False,
        "independent_network_identity": False,
        "complete_candidate_export": False,
        "confirmed_reconciliation": False,
    }
    enriched["findings"] = [
        {**finding, "classification": "OBSERVATION_NOT_CONFIRMED",
         "suggested_check": GUIDANCE[finding["code"]]}
        for finding in report["findings"]
    ]
    counts = (
        ("SOURCE_ONLY_OBSERVATION", report["summary"]["source_only"]),
        ("CANDIDATE_ONLY_OBSERVATION", report["summary"]["candidate_only"]),
        ("COLUMN_INTEGRITY_DIFFERENCE", report["summary"]["column_integrity_mismatches"]),
        ("TRANSACTION_OUTCOME_DIFFERENCE", report["summary"]["transaction_outcome_mismatches"]),
        ("UNMATCHABLE_CANDIDATE", report["summary"]["unmatchable_candidate_rows"]),
    )
    enriched["review_guidance"] = [
        {"code": code, "count": count, "suggested_check": GUIDANCE[code]}
        for code, count in counts if count
    ]
    return enriched


def render_markdown(report: dict[str, Any]) -> str:
    """Fixed headings/counts/hashes only: never render user-provided Markdown."""
    if (report.get("report_contract") != CONTRACT
            or report.get("status") not in ("INCONCLUSIVE", "REVIEW_REQUIRED")
            or report.get("reconciliation_proven") is not False):
        raise ReportingError("Cannot render unsupported or unsafe report")
    stats = report["summary"]
    bounds = report["scope_claim"]
    h = report["evidence_fingerprints"]
    lines = [
        "## LedgerVerity — supplied-file observations", "",
        "**Status:** " + report["status"] + " (never a confirmed ETL defect)",
        "**Claimed range:** " + str(int(bounds["first_ledger"])) + "–" + str(int(bounds["last_ledger"])), "",
        "| Observation | Count |", "|---|---:|",
    ]
    for label, key in (
        ("Exact XDR pairs", "exact_xdr_matches"), ("Source-only", "source_only"),
        ("Candidate-only", "candidate_only"),
        ("Column inconsistencies", "column_integrity_mismatches"),
        ("Transaction outcome differences", "transaction_outcome_mismatches"),
        ("Unmatchable candidate rows", "unmatchable_candidate_rows"),
        ("Missing source ledgers", "missing_source_ledgers"),
    ):
        lines.append("| " + label + " | " + str(int(stats[key])) + " |")
    lines.extend(["", "**Input fingerprints (not authenticity proofs):**", ""])
    for label, field in (
        ("Source", "source_capture_sha256"),
        ("Candidate", "candidate_file_sha256"),
        ("Manifest", "scope_manifest_sha256"),
    ):
        lines.append("- " + label + " SHA-256: `" + h[field] + "`")
    lines.extend(["", "**Suggested investigations:**", ""])
    if report["review_guidance"]:
        for item in report["review_guidance"]:
            lines.append("- **" + item["code"] + "** (" + str(int(item["count"])) + "): " + item["suggested_check"])
    else:
        lines.append("- No supplied-file differences found; source and export completeness remain unverified.")
    lines.extend([
        "",
        "**Finding samples shown:** " + str(len(report["findings"])) + " of " + str(int(report["finding_count"])) +
        (" (truncated)" if report["findings_truncated"] else ""),
        "",
        "**NOT VERIFIED:** independent source provenance, network identity, full export coverage, or historical parity.",
        "",
    ])
    return "\n".join(lines)
