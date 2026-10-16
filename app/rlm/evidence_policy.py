"""Require same-document, actually rendered evidence for relevant findings."""


def supported_findings(findings, valid_chunks, hits):
    owners = {hit.chunk_id: hit.doc_id for hit in hits}
    supported, warnings = [], []
    for finding in findings:
        evidence = [
            chunk for chunk in finding.evidence
            if chunk in valid_chunks and owners.get(chunk) == finding.doc_id
        ]
        if finding.relevant and not evidence:
            warnings.append("Dropped a relevant finding with no supporting rendered evidence")
            continue
        supported.append(finding.model_copy(update={"evidence": evidence}))
    return supported, warnings
