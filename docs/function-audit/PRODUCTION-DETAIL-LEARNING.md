# Production definition review — app/learning.py

Source baseline blob SHA: ea27a7ebf2fbdf58ba1452f4adaf7d56a197e9b9.

- _require_api_key(): rejects missing configured key, missing caller header or constant-time mismatch with HTTP 401.
- LearningRequest: requires account_id (1–200 chars); period_days defaults to 30 and is constrained 1–90.
- _number(value): unwraps value/count dictionaries; rejects None and bool; converts to float; rejects non-finite and negative values. It permits numeric strings and fractional metrics.
- run_learning_loop(payload): obtains stored credential; maps missing/decryption/config/DB failures to sanitized HTTP errors; computes start date from date.today() minus period; selects succeeded publications with Pin ID for exact account; returns waiting state if none. For each Pin, GETs Pinterest analytics with start/end/metric_types, rejects non-success response, parses documented summary/per-metric shapes, validates each metric, upserts snapshot by Pin/date range, and records per-Pin failures without aborting remaining Pins. Aggregates successful impressions/saves/outbound clicks and rates; explicitly reports model_trained=false.

Important limitations:
1. Uses date.today() (server-local date) rather than explicitly UTC; date boundaries should be aligned with Pinterest API expectations and configured timezone.
2. It uses stored access token directly and does not invoke refresh endpoint; expired token can cause analytics failure.
3. A valid summary_metrics object treats omitted metrics as zero; outside that shape, missing requested metric fails closed. This distinction is deliberate but should be covered by contract fixtures.
4. Per-Pin snapshot upsert is independent; partial batch success can persist even if other Pins fail. Response ok=false when any failed.
5. It stores one snapshot per Pin and fixed date period, overwriting metrics/fetched_at on repeat rather than preserving every daily observation.
6. Aggregate metrics are descriptive; no training, ranking update, experiment or policy feedback occurs.
7. No live Pinterest analytics call or DB write was made in this audit.