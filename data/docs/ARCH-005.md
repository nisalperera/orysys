---
doc_id: ARCH-005
title: "Architecture: data platform and audit logging"
department: data
document_type: architecture
access_level: confidential
created_date: "2025-09-15"
---

# Architecture: data platform and audit logging
## Overview
Transaction events stream through Kafka into the data lake. Audit logs are immutable and retained for 7 years.
## Availability
Target availability 99.95% for payment authorisation.
## Dependencies
See related incident reports for past failure modes.
