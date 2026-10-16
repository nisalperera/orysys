"""Allowlisted public status messages for retrieval activity."""


def public_degradation_reasons(reasons):
    if not reasons:
        return []
    messages = []
    for reason in reasons:
        value = str(reason)
        if value.startswith("sparse encoder not loaded"):
            message = "Sparse retrieval is unavailable; dense-only search was used."
        elif value.startswith("sparse encoder failed"):
            message = "Sparse retrieval failed; dense-only search was used."
        elif value.startswith("namespace '") and "failed:" in value:
            message = "Some document collections were unavailable; results may be incomplete."
        else:
            message = "Retrieval was degraded; results may be incomplete."
        if message not in messages:
            messages.append(message)
    return messages
