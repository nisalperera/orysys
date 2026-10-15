---
doc_id: ARCH-004
title: "Architecture: identity and access management"
department: security
document_type: architecture
access_level: confidential
created_date: "2025-09-15"
---

# Architecture: identity and access management
## Overview
Staff authenticate via the corporate IdP with SAML. Service to service calls use short-lived JWTs signed by an HSM-backed key.
## Availability
Target availability 99.95% for payment authorisation.
## Dependencies
See related incident reports for past failure modes.
