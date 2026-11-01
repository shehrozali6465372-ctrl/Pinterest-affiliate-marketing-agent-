# ProductInput — source-level review

- ID: `FN-APP-MAIN-PY-004`; source `app/main.py:63-68`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic model requires product_name 1–300, product_details 1–10000, image_url as HttpUrl, and affiliate_url 8–4096. Field validators trim/reject blank name/details; affiliate validator rejects surrounding whitespace, non-HTTP(S), missing host and embedded credentials, while preserving original URL string. HttpUrl may normalize image URL representation when converted to str.

## Callers and tests
Used by product validate/create endpoints. Tests cover malformed URLs, blank name, and exact affiliate URL preservation. Does not fetch product details or validate claims.
