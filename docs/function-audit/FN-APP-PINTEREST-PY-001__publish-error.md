# PinterestPublishError — source-level review

- ID: `FN-APP-PINTEREST-PY-001`; source `app/pinterest.py:10-15`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
RuntimeError subclass used to carry publication failure message plus outcome_uncertain boolean, optional HTTP status and error code. Constructor stores these fields; it performs no retry, HTTP request or persistence itself.

## Callers and semantics
Raised by image_media_source and publish_image_pin. Transport/5xx/malformed-success/missing-Pin-ID cases are uncertain; local validation and definite 4xx rejection are non-uncertain. Route callers must persist unknown state for uncertainty and must not blindly retry. Unit tests inspect these attributes with fake HTTP responses. No Pinterest write occurred.
