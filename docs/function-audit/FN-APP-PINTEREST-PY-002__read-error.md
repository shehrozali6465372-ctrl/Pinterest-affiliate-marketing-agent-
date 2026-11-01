# PinterestReadError

- **Unique ID:** FN-APP-PINTEREST-PY-002
- **Definition type:** class
- **Source:** `app/pinterest.py:60-61`
- **Source blob SHA:** `6ccc51b2cf8a289f6989e872179a0014cfe6f372`
- **Status:** VERIFIED — SOURCE RETRIEVED; STATIC LOGIC REVIEWED

## Exact source

```python
class PinterestReadError(RuntimeError):
    """A sanitized error from a read-only Pinterest verification request."""
```

## Behavior
Defines a distinct exception type for sanitized failures in the read-only Pinterest board-list and Pin-detail helpers. It carries no custom fields and does not itself issue a request, mutate a Pin, or access credentials.

## Callers
Raised by `list_board_pins_read_only` and `get_pin_read_only` for HTTP errors, malformed JSON/response shapes, pagination errors and transport failures. Callers in the publication-verification route translate these failures into controlled API responses.

## Verification boundary
Source and definition boundary are confirmed. Tests in `tests/test_pinterest_readonly.py` cover read-only GET behavior, bookmark pagination, repeated bookmarks, page-cap behavior and provider-error sanitization. Those tests use fake HTTP clients; they do not prove live Pinterest API behavior.
