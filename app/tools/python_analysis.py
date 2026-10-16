"""Deterministic research analysis over unique documents and their findings.

The authorized python_analysis registry entry runs the bounded research workflow.
Counts/totals use unique document IDs. Root-cause groups may overlap when a
single document has multiple distinct supported cause labels.
"""
import re
from collections import Counter, defaultdict

_FACTS = {
    "severity": re.compile(r"\*\*Severity:\*\*[ \t]*(P\d)", re.I),
    "service": re.compile(r"\*\*Affected service:\*\*[ \t]*([\w\-\.]+)", re.I),
}
_DURATION = re.compile(r"\*\*Duration:\*\*[ \t]*([^\r\n]*)", re.I)
_TRANSACTIONS = re.compile(r"\*\*Failed transactions[^*]*\*\*[ \t]*([^\r\n]*)", re.I)
_INTEGER = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)")
_STOP = {"in", "on", "of", "the", "a", "an", "and", "for", "to", "at", "by", "due"}


def _integer(text):
    value = text.strip()
    if not _INTEGER.fullmatch(value):
        return None
    return int(value.replace(",", ""))


def extract_facts(body: str) -> dict:
    out = {}
    for key, pattern in _FACTS.items():
        match = pattern.search(body)
        if match:
            out[key] = match.group(1)
    match = _DURATION.search(body)
    if match:
        duration = re.fullmatch(r"(.+?)[ \t]+minutes", match.group(1).strip(), re.I)
        value = _integer(duration.group(1)) if duration else None
        if value is not None:
            out["duration_minutes"] = value
    match = _TRANSACTIONS.search(body)
    if match:
        value = _integer(match.group(1))
        if value is not None:
            out["failed_transactions"] = value
    return out


def _tokens(label: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", label.lower()) if t not in _STOP}


def cluster_labels(labels: list[str]) -> dict[str, str]:
    """Greedy grouping by token-overlap coefficient >= 0.6; not causal verification."""
    canon = []
    mapping = {}
    for label in labels:
        tokens = _tokens(label)
        if not tokens:
            mapping[label] = "unspecified"
            continue
        for name, canonical_tokens in canon:
            if len(tokens & canonical_tokens) / min(len(tokens), len(canonical_tokens)) >= 0.6:
                mapping[label] = name
                break
        else:
            canon.append((label, tokens))
            mapping[label] = label
    return mapping


def _extreme(incidents: list[dict], key: str):
    pool = [i for i in incidents if type(i.get(key)) is int]
    if not pool:
        return None
    top = max(pool, key=lambda item: (item[key], item["doc_id"]))
    return {
        "doc_id": top["doc_id"], key: top[key],
        "date": top["date"], "severity": top["severity"],
    }


def _numeric(metadata, key):
    value = metadata.get(key)
    return value if type(value) is int and value >= 0 else 0


def analyze_findings(findings: list[dict], doc_meta: dict[str, dict]) -> dict:
    by_doc = {}
    for finding in findings:
        doc_id = finding["doc_id"]
        record = by_doc.setdefault(doc_id, {"findings": [], "labels": [], "services": [], "evidence": []})
        record["findings"].append(finding)
        label = finding.get("root_cause") or ""
        if label not in record["labels"]:
            record["labels"].append(label)
        service = finding.get("service") or ""
        if service and service not in record["services"]:
            record["services"].append(service)
        for chunk_id in finding.get("evidence") or []:
            if isinstance(chunk_id, str) and chunk_id not in record["evidence"]:
                record["evidence"].append(chunk_id)

    mapping = cluster_labels([
        label for record in by_doc.values() for label in record["labels"]
    ])
    groups = defaultdict(set)
    incidents, months, services, severities = [], Counter(), Counter(), Counter()
    conflicts = {}
    total_downtime = total_transactions = 0

    for doc_id, record in by_doc.items():
        metadata = doc_meta.get(doc_id) or {}
        service = metadata.get("service") or (record["services"][0] if record["services"] else "unknown")
        labels = list(dict.fromkeys(mapping[label] for label in record["labels"]))
        # Missing labels do not create a second unknown group beside a known cause.
        if len(labels) > 1 and "unspecified" in labels:
            labels.remove("unspecified")
        if len(labels) > 1:
            conflicts[doc_id] = labels
        for label in labels:
            groups[label].add(doc_id)
        months[(metadata.get("created_date") or "")[:7] or "unknown"] += 1
        services[service] += 1
        severities[metadata.get("severity") or "unknown"] += 1
        total_downtime += _numeric(metadata, "duration_minutes")
        total_transactions += _numeric(metadata, "failed_transactions")
        incidents.append({
            "doc_id": doc_id, "date": metadata.get("created_date"),
            "severity": metadata.get("severity"), "service": service,
            "duration_minutes": metadata.get("duration_minutes"),
            "failed_transactions": metadata.get("failed_transactions"),
            "root_cause": "; ".join(labels),
            "root_cause_labels": labels,
            "evidence": list(record["evidence"]),
            "finding_count": len(record["findings"]),
        })
    incidents.sort(key=lambda item: (item["date"] or "", item["doc_id"]))

    by_cause = []
    for cause, ids in groups.items():
        metadata = [doc_meta.get(doc_id) or {} for doc_id in sorted(ids)]
        dates = sorted(item["created_date"] for item in metadata if item.get("created_date"))
        by_cause.append({
            "root_cause": cause, "count": len(ids), "doc_ids": sorted(ids),
            "downtime_minutes": sum(_numeric(item, "duration_minutes") for item in metadata),
            "failed_transactions": sum(_numeric(item, "failed_transactions") for item in metadata),
            "services": sorted({item["service"] for item in metadata if item.get("service")}),
            "first_seen": dates[0] if dates else None,
            "last_seen": dates[-1] if dates else None,
        })
    by_cause.sort(key=lambda item: (-item["count"], item["root_cause"]))
    return {
        "total_documents": len(by_doc),
        "total_findings": len(findings),
        "by_root_cause": by_cause,
        "recurring": [item["root_cause"] for item in by_cause if item["count"] >= 2],
        "incidents": incidents,
        "root_cause_conflicts": conflicts,
        "root_cause_groups_overlap": bool(conflicts),
        "by_severity": dict(sorted(severities.items())),
        "longest_downtime": _extreme(incidents, "duration_minutes"),
        "most_failed_transactions": _extreme(incidents, "failed_transactions"),
        "by_month": dict(sorted(months.items())),
        "by_service": dict(services.most_common()),
        "totals": {"downtime_minutes": total_downtime, "failed_transactions": total_transactions},
    }
