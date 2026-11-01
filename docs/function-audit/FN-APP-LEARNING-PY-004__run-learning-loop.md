# run_learning_loop — source-level review

- ID: `FN-APP-LEARNING-PY-004`; source `app/learning.py:49-203`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest/Neon verification: NOT RUN.

## Control flow
1. Requires configured LLM? No: this route is analytics-only and does not call the LLM.
2. Loads stored access credential for request.account_id; maps missing/decryption/config/DB failures to sanitized HTTP errors.
3. Computes start date as server-local `date.today() - period_days` and end date as current server-local date.
4. Queries succeeded publication rows with non-null Pin IDs for exact account_id.
5. If none, returns waiting_for_published_pins with zero counts and `model_trained=false`.
6. For each Pin, GETs Pinterest analytics using fixed metric types and bounded date range.
7. Parses supported summary_metrics/per-metric response forms with _number; validates requested metrics; records per-Pin errors without aborting the remaining batch.
8. Upserts one snapshot per Pin/date window and accumulates impressions, saves, outbound clicks and derived rates.
9. Returns totals, per-Pin results, snapshot count and `model_trained=false`; partial failures set overall ok=false.

## Callers, tests and limitations
Called by Learning Loop router and scheduled GitHub Actions workflow. `tests/test_learning.py` stubs DB/Pinterest and tests account filtering, metric parsing, omitted-zero summary fields, invalid metrics and snapshot persistence calls. These tests do not prove Neon durability or live Pinterest schema.

Date calculation uses server-local timezone rather than explicit UTC/configured Pinterest timezone. Repeated fetches overwrite the same Pin/date-period snapshot rather than retaining daily history. Stored access token is used directly; no refresh route is invoked. Analytics ingestion and descriptive aggregation are real data processing, not ML training. No model is fitted and no policy/weights are updated.
