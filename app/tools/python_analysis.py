"""Python analysis tool: deterministic, structured analysis over retrieved findings.

Numbers and rankings in the final answer come from here, not from the LLM. The result includes a per-incident
table and explicit extremes (longest downtime, most failed transactions), so the answer never has to guess which
incident was "most severe". In T4 this is registered as the `python_analysis` tool (Analyst and Admin roles).
"""
import re
from collections import Counter, defaultdict

_FACTS = {
    "severity": (re.compile(r"\*\*Severity:\*\*\s*(P\d)", re.I), str),
    "duration_minutes": (re.compile(r"\*\*Duration:\*\*\s*(\d+)\s*minutes", re.I), int),
    "failed_transactions": (re.compile(r"\*\*Failed transactions[^*]*\*\*\s*(\d+)", re.I), int),
    "service": (re.compile(r"\*\*Affected service:\*\*\s*([\w\-\.]+)", re.I), str),
}
_STOP = {"in", "on", "of", "the", "a", "an", "and", "for", "to", "at", "by", "due"}


def extract_facts(body: str) -> dict:
    out = {}
    for key, (rx, cast) in _FACTS.items():
        m = rx.search(body)
        if m:
            out[key] = cast(m.group(1))
    return out


def _tokens(label: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", label.lower()) if t not in _STOP}


def cluster_labels(labels: list[str]) -> dict[str, str]:
    """Greedy grouping of free-text root cause labels by token overlap (overlap coefficient >= 0.6)."""
    canon: list[tuple[str, set[str]]] = []
    mapping: dict[str, str] = {}
    for label in labels:
        toks = _tokens(label)
        if not toks:
            mapping[label] = "unspecified"
            continue
        for name, ctoks in canon:
            if len(toks & ctoks) / min(len(toks), len(ctoks)) >= 0.6:
                mapping[label] = name
                break
        else:
            canon.append((label, toks))
            mapping[label] = label
    return mapping


def _extreme(incidents: list[dict], key: str):
    pool = [i for i in incidents if isinstance(i.get(key), int)]
    if not pool:
        return None
    top = max(pool, key=lambda i: (i[key], i["doc_id"]))
    return {"doc_id": top["doc_id"], key: top[key], "date": top["date"], "severity": top["severity"]}


def analyze_findings(findings: list[dict], doc_meta: dict[str, dict]) -> dict:
    """findings: dicts with doc_id/root_cause/service. doc_meta: doc_id -> created_date + extracted facts."""
    mapping = cluster_labels([f.get("root_cause", "") for f in findings])
    groups: dict[str, list[str]] = defaultdict(list)
    for f in findings:
        groups[mapping[f.get("root_cause", "")]].append(f["doc_id"])

    incidents, months, services, severities = [], Counter(), Counter(), Counter()
    tot_down = tot_txn = 0
    for f in findings:
        m = doc_meta.get(f["doc_id"], {})
        svc = m.get("service") or f.get("service") or "unknown"
        months[m.get("created_date", "")[:7] or "unknown"] += 1
        services[svc] += 1
        severities[m.get("severity") or "unknown"] += 1
        tot_down += m.get("duration_minutes", 0)
        tot_txn += m.get("failed_transactions", 0)
        incidents.append({
            "doc_id": f["doc_id"], "date": m.get("created_date"), "severity": m.get("severity"), "service": svc,
            "duration_minutes": m.get("duration_minutes"), "failed_transactions": m.get("failed_transactions"),
            "root_cause": mapping[f.get("root_cause", "")]})
    incidents.sort(key=lambda i: (i["date"] or "", i["doc_id"]))

    by_cause = []
    for cause, ids in groups.items():
        metas = [doc_meta.get(i, {}) for i in ids]
        dates = sorted(m["created_date"] for m in metas if m.get("created_date"))
        by_cause.append({
            "root_cause": cause, "count": len(ids), "doc_ids": sorted(ids),
            "downtime_minutes": sum(m.get("duration_minutes", 0) for m in metas),
            "failed_transactions": sum(m.get("failed_transactions", 0) for m in metas),
            "services": sorted({m.get("service") for m in metas if m.get("service")}),
            "first_seen": dates[0] if dates else None, "last_seen": dates[-1] if dates else None,
        })
    by_cause.sort(key=lambda c: (-c["count"], c["root_cause"]))
    return {
        "total_documents": len(findings),
        "by_root_cause": by_cause,
        "recurring": [c["root_cause"] for c in by_cause if c["count"] >= 2],
        "incidents": incidents,
        "by_severity": dict(sorted(severities.items())),
        "longest_downtime": _extreme(incidents, "duration_minutes"),
        "most_failed_transactions": _extreme(incidents, "failed_transactions"),
        "by_month": dict(sorted(months.items())),
        "by_service": dict(services.most_common()),
        "totals": {"downtime_minutes": tot_down, "failed_transactions": tot_txn},
    }
