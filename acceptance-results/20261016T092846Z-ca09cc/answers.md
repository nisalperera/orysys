# API acceptance answers

Semantic checks require manual review; browser rendering is not tested.

## analyst-research [PASS]

Role: analyst | Session: f50a846beb2f40848bbfaf178c0cccef

Question: Summarize all outage reports related to payment failures during the last year and identify recurring root causes.

Answer:

**Summary of Payment Outage Reports (Last Year)**

A total of **9 incidents** related to payment failures were recorded between November 2025 and September 2026. These outages resulted in a combined downtime of **469 minutes** and **48,150 failed transactions**. The incidents affected four primary services: `payments-api` (3 incidents), `settlement-svc` (3 incidents), `card-switch-gw` (2 incidents), and `wallet-service` (1 incident).

**Recurring Root Causes**

Three root causes have been identified as recurring issues, each occurring three or more times during the reporting period:

1.  **Database connection pool exhaustion**
    *   **Occurrences:** 3 incidents [INC-2025-031, INC-2026-007, INC-2026-019]
    *   **Affected Service:** `payments-api`
    *   **Details:** Saturation of the database connection pool was caused by long-running reconciliation queries, leading to queued authorisations and timeouts.
    *   **Impact:** 136 minutes of downtime; 13,560 failed transactions.

2.  **Third-party gateway timeouts without circuit breaker**
    *   **Occurrences:** 3 incidents [INC-2026-003, INC-2026-022, INC-2026-029]
    *   **Affected Service:** `settlement-svc`
    *   **Details:** Latency from the NovaPay settlement API exceeded thresholds. The absence of a circuit breaker led to synchronous retries that amplified load, causing cascading failures.
    *   **Impact:** 153 minutes of downtime; 20,200 failed transactions.

3.  **Expired TLS certificate**
    *   **Occurrences:** 2 incidents [INC-2025-044, INC-2026-014]
    *   **Affected Service:** `card-switch-gw`
    *   **Details:** Mutual TLS certificates on the link between the card switch gateway and the card network expired, blocking payment processing.
    *   **Impact:** 153 minutes of downtime; 9,040 failed transactions.

**Other Identified Cause**

*   **Faulty configuration deployment (transaction limit flag):** This occurred once [INC-2026-011] affecting `wallet-service`. A feature-flag change incorrectly set the per-transaction limit to zero for retail wallets, resulting in 27 minutes of downtime and 5,350 failed transactions.

Checks: [{"check": "nonempty final answer", "passed": true}, {"check": "no internal error event", "passed": true}, {"check": "not blocked", "passed": true}, {"check": "no placeholder citations", "passed": true}, {"check": "research routing", "passed": true}, {"check": "nine incident sources", "passed": true}, {"check": "469 incident-minutes", "passed": true}, {"check": "48150 failed transactions", "passed": true}, {"check": "nine relevant findings", "passed": true}, {"check": "three recurring groups", "passed": true}, {"check": "healthy execution", "passed": true}]

Manual review: Review evidence support, date scope, cause grouping and totals; lexical checks are not entailment validation.

Error: none

---

## analyst-longest [PASS]

Role: analyst | Session: f50a846beb2f40848bbfaf178c0cccef

Question: Which of those incidents had the longest downtime, and how long did it last?

Answer:

Across the 9 analysed incidents, [INC-2025-044] had the longest downtime: 95 minutes.

Checks: [{"check": "nonempty final answer", "passed": true}, {"check": "no internal error event", "passed": true}, {"check": "not blocked", "passed": true}, {"check": "no placeholder citations", "passed": true}, {"check": "bracketed evidence citation", "passed": true}, {"check": "memory has preceding messages", "passed": true}, {"check": "memory turn count", "passed": true}, {"check": "correct incident", "passed": true}, {"check": "95 minutes", "passed": true}]

Manual review: Review wording and evidence support.

Error: none

---

## analyst-transactions [PASS]

Role: analyst | Session: f50a846beb2f40848bbfaf178c0cccef

Question: Was that also the incident with the most failed transactions? If not, identify the other incident and its transaction count.

Answer:

Across the 9 analysed incidents, [INC-2026-029] had the highest failed-transaction count: 8,670 failed transactions. For comparison, [INC-2025-044] had 2,860 failed transactions.

Checks: [{"check": "nonempty final answer", "passed": true}, {"check": "no internal error event", "passed": true}, {"check": "not blocked", "passed": true}, {"check": "no placeholder citations", "passed": true}, {"check": "bracketed evidence citation", "passed": true}, {"check": "memory has preceding messages", "passed": true}, {"check": "memory turn count", "passed": true}, {"check": "correct highest-impact incident", "passed": true}, {"check": "8670 transactions", "passed": true}]

Manual review: Review wording and evidence support.

Error: none

---

