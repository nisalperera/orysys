---
doc_id: ARCH-001
title: "Architecture: payments platform overview"
department: payments
document_type: architecture
access_level: internal
created_date: "2025-09-15"
---

# Architecture: payments platform overview
## Overview
payments-api receives requests from the channels, calls fraud-scoring, then routes to card-switch-gw for cards or settlement-svc for wallets and bank transfers. PostgreSQL is the system of record with a standby replica.
## Availability
Target availability 99.95% for payment authorisation.
## Dependencies
See related incident reports for past failure modes.
