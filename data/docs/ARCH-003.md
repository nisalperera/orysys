---
doc_id: ARCH-003
title: "Architecture: settlement service and NovaPay integration"
department: payments
document_type: architecture
access_level: internal
created_date: "2025-09-15"
---

# Architecture: settlement service and NovaPay integration
## Overview
settlement-svc batches wallet transfers and calls the NovaPay REST API. Retries use exponential backoff. A circuit breaker and fallback queue were added after INC-2026-003.
## Availability
Target availability 99.95% for payment authorisation.
## Dependencies
See related incident reports for past failure modes.
