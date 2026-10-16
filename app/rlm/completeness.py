"""Research measurement coverage and bounded, safe completeness disclosures."""
import re

METRICS = {
    "duration_minutes": "Downtime",
    "failed_transactions": "Failed-transaction",
}


def valid_measurement(value):
    return type(value) is int and value >= 0


def measurement_coverage(incidents, doc_meta):
    # Legacy direct callers omitted document_type; treat those rows as incidents.
    applicable = sorted({
        row["doc_id"] for row in incidents
        if (doc_meta.get(row["doc_id"]) or {}).get("document_type", "incident") == "incident"
    })
    result = {}
    for key in METRICS:
        known = [doc_id for doc_id in applicable
                 if valid_measurement((doc_meta.get(doc_id) or {}).get(key))]
        missing = sorted(set(applicable) - set(known))
        result[key] = {
            "applicable": bool(applicable),
            "total_documents": len(applicable),
            "known_documents": len(known),
            "missing_doc_ids": missing,
            "complete": bool(applicable) and not missing,
            "known_subtotal": sum(doc_meta[doc_id][key] for doc_id in known),
        }
    return result


def coverage_reasons(analysis):
    notes = []
    for key, label in METRICS.items():
        coverage = (analysis.get("metric_coverage") or {}).get(key) or {}
        if coverage.get("applicable") and not coverage.get("complete"):
            notes.append(
                f"{label} measurements are incomplete: "
                f"{coverage.get('known_documents', 0)} of {coverage.get('total_documents', 0)} "
                "incident documents have valid values. The sum is a known subtotal; "
                "collection-wide totals and rankings are not established."
            )
    return notes


def bounded_records(records, limit=1500):
    """Keep complete string records only; never slice through a record or citation."""
    kept = []
    used = 0
    for record in records:
        extra = len(record) + (1 if kept else 0)
        if used + extra <= limit:
            kept.append(record)
            used += extra
    return {
        "text": "\n".join(kept),
        "retained": len(kept),
        "omitted": len(records) - len(kept),
    }


def safe_completeness_notes(analysis, reasons=(), failed=()):
    notes = coverage_reasons(analysis)
    if analysis.get("root_cause_groups_overlap"):
        notes.append("Some documents have multiple root-cause labels; cause-group totals overlap and must not be added together.")
    if failed:
        notes.append("Some analysis batches failed; collection coverage is incomplete.")
    for reason in reasons or ():
        text = str(reason).lower()
        if "measurements are incomplete:" in text or "root-cause labels" in text:
            continue
        if "partial aggregation failed" in text:
            counts = re.search(r"retained (\d+) of (\d+) complete records", text)
            if counts:
                kept, total = counts.groups()
                note = f"Partial aggregation failed; fallback retained {kept} of {total} complete finding records."
                if int(kept) < int(total):
                    note += " Some finding text was omitted."
            else:
                note = "Partial aggregation failed; fallback coverage may be incomplete."
        elif "selection truncated" in text:
            note = "Document selection was capped; the answer does not cover every matching document."
        elif "evidence truncated" in text:
            note = "Some retrieved evidence was omitted to respect the context budget."
        elif "no evidence retrieved" in text:
            note = "Supporting evidence was missing for some selected documents."
        elif "retrieval was degraded" in text:
            note = "Retrieval was degraded; some evidence may be missing."
        elif "plan unavailable" in text:
            note = "A fallback research plan was used because model planning was unavailable."
        elif "final aggregation llm failed" in text:
            note = "Final model aggregation failed; an automatic summary was used."
        elif "failed:" in text or "classified irrelevant" in text:
            note = "Some research steps could not establish complete coverage."
        else:
            note = "Some research steps were incomplete; review the activity and sources."
        if note not in notes:
            notes.append(note)
    return list(dict.fromkeys(notes))[:10]


def append_completeness_notes(answer, analysis, reasons=(), failed=()):
    notes = safe_completeness_notes(analysis, reasons, failed)
    if not notes:
        return answer
    footer = "Analysis limitations: " + " ".join(notes)
    if footer in answer:
        return answer
    return answer.rstrip() + "\n\n" + footer


def no_findings_outcome(selected_ids, analysed_ids, batch_errors=(), has_warnings=False):
    """Separate empty scope, failed analysis, explicit irrelevance and inconclusive evidence."""
    selected = set(selected_ids)
    analysed = set(analysed_ids)
    if not selected:
        return "No accessible documents match this request.", False
    errors = list(batch_errors)
    if errors and all(errors):
        return (
            "The documents could not be analysed because a required service failed. Please try again.",
            True,
        )
    if selected <= analysed and not any(errors) and not has_warnings:
        return "No relevant documents were identified within the analysed scope.", False
    return (
        "I could not establish supported relevance for the selected documents. "
        "This analysis is incomplete; please retry or refine the request.",
        True,
    )


def downtime_label(analysis):
    coverage = (analysis.get("metric_coverage") or {}).get("duration_minutes") or {}
    if coverage.get("applicable") and not coverage.get("complete"):
        return "min known downtime subtotal"
    return "min downtime"
