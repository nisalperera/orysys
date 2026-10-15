---
doc_id: ARCH-002
title: "Architecture: card switch gateway"
department: cards
document_type: architecture
access_level: internal
created_date: "2025-09-15"
---

# Architecture: card switch gateway
## Overview
card-switch-gw maintains mutual TLS sessions to the card network. Certificates are issued by the internal PKI. Connection failover is active-passive across two data centres.
## Availability
Target availability 99.95% for payment authorisation.
## Dependencies
See related incident reports for past failure modes.
