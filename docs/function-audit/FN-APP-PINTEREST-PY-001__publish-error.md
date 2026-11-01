# PinterestPublishError

- **Unique ID:** FN-APP-PINTEREST-PY-001
- **Source:** app/pinterest.py:10-15 (line positions to be rechecked against current full file before final sign-off)
- **Status:** VERIFIED — SOURCE RETRIEVED; line coordinates provisional

## Behavior
A RuntimeError subtype used to transport a sanitized publication failure together with explicit publication-outcome certainty. Constructor fields are `outcome_uncertain`, optional HTTP status and optional error code. It does not retry or make network calls.

## Why certainty matters
Callers must not blindly retry a Pinterest write if the client timed out, Pinterest returned a 5xx, or a response was malformed after the request may have reached Pinterest. Determinate local validation and explicit client rejection can be represented as non-uncertain.

## Evidence boundary
Definition inspected in app/pinterest.py. Test coverage and every caller must be mapped before marking correctness verified. No Pin was published during this review.
