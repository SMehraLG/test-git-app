---
contract_version: 1.0
spec_id: spec-7aeea9f3
correlation_id: feat-b7fcdbc2
version: 5
parent_id: spec-7aeea9f3@4
acms_verdict: compliant
created_by: mehrasaiyam
created_at: 2026-07-24T15:06:58Z
service: Connectivity Service (Horizon v2)
intent_kind: new_feature
approver: null
approved: null
---

# Spec: Customer connectivity score endpoint

## Problem
Operators and care agents need a single, at-a-glance measure of an individual customer's recent broadband quality, but the connectivity service exposes no per-customer rollup. It ingests test measurements and surfaces raw records and fleet-level health, so answering "how is this customer's connection doing?" today means inspecting raw speed/latency rows or fleet dashboards. There is no way to get a single bounded score and a plain-language status for one customer over their recent measurement history.

## Users
- Care agents and operator support staff who need a quick, plain-language verdict on a specific customer's connection quality during a support interaction.
- Operator-facing systems and dashboards that display or triage individual customer connection health and need a single score to drive that view.
- Downstream automation (alerting, prioritisation) that acts on a customer's current connectivity standing.

## Outcomes
- A caller can request the connectivity score for a given customer identifier and receives a numeric score in the range 0-100 together with a status label.
- The status label is exactly one of four values - excellent, good, degraded, critical - derived from the score using upper-inclusive bands: score >= 80 is excellent, 60 <= score < 80 is good, 40 <= score < 60 is degraded, and score < 40 is critical.
- The score reflects only measurements whose test time falls within the trailing 30-day window ending at the time of the request; measurements older than 30 days do not influence it.
- The score is a weighted combination of the customer's download speed, upload speed, and latency, weighted 50%, 30%, and 20% respectively.
- Each of the three metrics is normalised to a 0-100 sub-score based on measured performance relative to the customer's provisioned service level for the speed metrics and relative to a latency target for the latency metric, so a customer meeting their provisioned service scores near the top of the range regardless of their plan tier.
- When the window contains some but not all three metric types, the score is computed from the metric types actually present, with the weights redistributed proportionally across the available metrics.
- When no measurements of any type exist for the customer within the 30-day window, the request returns a 404 not-found response identifying the customer, rather than a score.
- For the same customer, window, and underlying measurement data, repeated requests return the same score and status (the computation is deterministic).
- The response conveys the customer identifier, the score, the status, the window it covers, and the per-metric sub-scores together with how many measurements each sub-score is based on, so a caller can interpret and justify the score without a second request.
- The endpoint enforces the same authentication and rate-limiting regime as the service's existing read endpoints, introducing no weaker access path to customer measurement data.
- Under expected load the endpoint meets a p95 response-time budget of under 1 second and a p99 of under 2 seconds, inclusive of the 30-day measurement aggregation.
- A request resolves only measurements belonging to the requester's own operator/market context; data belonging to another operator is never returned or allowed to influence a customer's score, even if a customer identifier were to collide across operators.
- The endpoint returns only derived and aggregate values (the score, status, per-metric sub-scores, measurement counts, the supplied customer identifier, and the window); it exposes no raw underlying measurement records and no additional personal data about the customer beyond the identifier the caller supplied.
- The customer identifier is treated as an opaque token supplied by the caller; the endpoint's response leaks no internal operator identifiers, device or line identifiers, or identifiers belonging to any other operator.

## Out of scope
- Discovering the network topology behind a customer - i.e. resolving which probe, device, or line a customer maps to - via an external identity or inventory service. The endpoint operates only on measurements already tagged with the supplied customer identifier; it does not thereby waive the data-governance obligations that apply to handling that identifier and its data.
- Changing how SamKnows measurements are ingested, enriched, or tagged with a customer identifier.
- Historical trends, time-series, or per-day score breakdowns - the endpoint returns a single current rollup only.
- Scoring metric types other than download speed, upload speed, and latency (for example jitter, packet loss, MOS, or disconnection events).
- Any UI, dashboard, or visualisation surface for the score - this is an API-only capability.
- Caller-tunable weights or band thresholds - the weighting and banding are fixed by this specification, not configurable per request.
- Ranking or comparing customers against one another or against a fleet-wide distribution.

## Business context
- (nugget:9265286c-625f-4c02-bb76-7aa555240c8a [external:casas-architecture]) No 0-100 numeric scoring scale is defined anywhere in CASAS. The closest existing pattern is the Consumer Experience Mapping on the CNX Speed Test Evaluation Platform, which classifies raw metrics (download Mbps, RTT ms, jitter, packet loss) into three threshold-based indicator states — good (green tick), marginal (amber), or insufficient (red cross) — across five application categories (Streaming, Gaming, Video Calls, Social Media, Audio & Voice), with no numeric band or weighted aggregate defined. Relevance: Answers spec question: How are raw broadband measurements (download/upload Mbps, latency ms) normalized onto a 0-100 quality scale anywhere in CASAS? Any reference thresholds, target throughput values, or scoring bands?
- (nugget:bd18e25f-010a-4452-a249-399e16cf1a91 [external:casas-architecture]; nugget:e807a967-3cf6-4ff1-a865-f954621298ae [external:horizon-v2-microservices]; nugget:69c969e3-b795-474e-b575-085ba9477dc4 [external:casas-architecture]) The authoritative customer identifier in the platform is minted by the CRM/Account Service. In the connectivity service's measurement store, probe and CPE records (customer ID, hardware type, service tier) are sourced from a separate identity resolution service in the target architecture; the link between a customer identifier and a probe is resolved via that external service rather than being embedded directly in the measurement dataset. Relevance: Answers spec question: What identifies a "customer" in the connectivity data model? Is there a customer_id field, and how does it relate to probes (probe_registry) and the fact tables?
- (nugget:e807a967-3cf6-4ff1-a865-f954621298ae [external:horizon-v2-microservices]; nugget:f1ca10e2-e8a8-4c9b-af6a-733ffd7e72c3 [external:casas-architecture]; nugget:1368a70e-a725-40e9-b2c4-106eab36edc0 [external:horizon-v2-microservices]) Download and upload throughput measurements and latency/RTT measurements are stored in separate fact tables in the connectivity measurement store. All measurement tables support time-bounded queries, making it possible to restrict aggregation to a trailing window such as the last 30 days. Specific field names within those tables are not enumerated in the knowledge base. Relevance: Establishes whether the measurement store already supports time-bounded queries over a trailing window, and which metric categories (throughput, latency) have separate storage structures — context needed to determine whether the 30-day window and per-metric sub-score design are consistent with how measurements are physically available.
- (nugget:d28d3c2a-663f-4c0c-9493-b12ab271c434 [external:horizon-v2-microservices]; nugget:695338a5-b68e-462c-8fa7-a525fffaa619 [external:horizon-v2-microservices]) The connectivity service enforces API key authentication on its /api/v1 endpoints, with authentication enabled in production and disabled in local/development environments. Per-IP rate limiting is also applied. In production, the service sits behind an API gateway that enforces per-operator API key authentication at the gateway tier. Relevance: Answers spec question: Does the connectivity service require API-key authentication (or other auth) on its /api/v1 REST endpoints? What is the auth/permission model?
- (nugget:8e96c34d-5396-4cd7-be94-3d8607e48502 [external:horizon-v2-microservices]; nugget:da51b767-839e-4fec-a623-9cd0faa42ee4 [external:horizon-v2-microservices]; nugget:1b78e00c-8a08-49e2-8db8-05f5cf67e101 [external:horizon-v2-microservices]) The connectivity service has an existing fleet-level health endpoint whose response shape and semantics the new per-customer score endpoint should align with. The service follows a standard error envelope format. The detailed response shape of the existing fleet health endpoint is not recorded in the knowledge base. Relevance: Answers spec question: Are there existing score, health, or quality-rating endpoints in the connectivity service (e.g. /api/v1/fleet/health) whose response shape or semantics this new endpoint should align with?
- (nugget:4ff11db3-05c6-49ad-9d0a-641c42e82227 [external:casas-architecture]; nugget:d100b0b8-b3f4-42b6-b7b0-ce273a38ed17 [external:casas-architecture]) No connectivity-service-specific read latency budget is recorded for measurement-aggregation endpoints. Adjacent targets from the architecture: Touchpoint APIs are targeted at p95 < 500 ms / p99 < 1000 ms / 99.9% uptime; a separate speed-test NFR requires measurement results to be available near real-time after test completion, but sets no read-query response time. Relevance: Answers spec question: Is there a defined latency or performance budget for connectivity REST API read endpoints that query BigQuery?

## Compliance constraints
- `compliance:gdpr` — applies because: The endpoint accepts a customer_id path parameter to return a scored view of that customer's broadband measurements — introducing a customer-identified data access surface subject to GDPR data-handling obligations that apply per OpCo market across all connectivity APIs (CON-004-03, CON-009-005).
- `compliance:gdpr-data-minimisation` — applies because: The Connectivity service's established data profile carries no PII in probe data (device IDs only); this endpoint extends that profile to expose a derived score keyed by customer_id, requiring that only the necessary customer-identifying data is processed over the 30-day window and that no raw or excess personal data is returned.
- `domain:casas-tcid-abstraction` — applies because: A core connectivity principle is that operator customer IDs must never be exposed to third parties via TCId abstraction; the endpoint's use of a customer identifier in the path and response must respect this boundary so internal identifiers are not leaked across OpCo trust domains.
- `domain:casas-per-opco-data-isolation` — applies because: ADR-C020 mandates per-OpCo data isolation for all customer data; the connectivity-score endpoint returns per-customer data that must be scoped and isolated to the originating OpCo market so a query in one market cannot resolve data belonging to another.
- `compliance:ofcom` — applies because: The score is derived from SamKnows broadband measurements, a regulated measurement approach subject to UK Ofcom approval (CON-ST-002, NFR-ST-007); any API surface that surfaces derived outputs from this measurement data inherits the obligation that the underlying measurement methodology is Ofcom-compliant.
