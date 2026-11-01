# PublicationReconciliationInput — source-level review

- ID: `FN-APP-MAIN-PY-023`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic schema accepts operator outcome, optional Pinterest Pin ID and evidence string subject to field constraints. Semantic outcome/Pin ID consistency and unknown-state transition are enforced by database.reconcile_unknown_publication rather than this model alone. Evidence is operator-supplied, not independently authenticated by the schema.

## Callers
Used by reconcile_publication, which has fail-closed configured API-key dependency. Operator must first perform read-only Pinterest verification and preserve complete pagination evidence.
