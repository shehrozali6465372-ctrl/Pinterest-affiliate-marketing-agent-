# DiagnosticRunInput — source-level review

- ID: `FN-APP-DIAGNOSTICS-PY-004`; source `app/diagnostics.py:137-143`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic request schema requires account_id length 1–200. product_name defaults to a kitchen spice-rack example and is bounded 1–300. product_details defaults to generic organizer copy and is bounded 1–1000. These fields are used only for diagnostic image/content generation; schema validation does not prove product facts.

## Callers and risk
Consumed by `run_live_diagnostics`, which can call Cloudflare Workers AI and DeepSeek after DB/Pinterest prerequisites pass. A request can trigger billable provider usage. No diagnostic request was submitted.
