# _ensure_board

- **Unique ID:** `FN-APP-WORKFLOW-PY-007`
- **Source:** `app/workflow.py:87-100`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Analysis

This record isolates one definition. Review the source line by line, its direct callers, callees, tests and side effects before marking its behavior verified.

## Source excerpt

```python
def _ensure_board(token: str, name: str, description: str) -> str:
    _, response = _pinterest_request("GET", "/boards?page_size=100", token)
    items = response.get("items", []) if isinstance(response, dict) else []
    for board in items:
        if isinstance(board, dict) and board.get("name", "").casefold() == name.casefold() and board.get("id"):
            return str(board["id"])
    _, created = _pinterest_request("POST", "/boards", token, body={"name": name, "description": description})
    board_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(board_id, str) or not board_id:
        raise HTTPException(status_code=502, detail="Pinterest did not return a board ID; board creation was not confirmed.")
    return board_id


@router.post("/publish-product", dependencies=[Depends(_require_api_key)])
```

## Evidence tags

- `VERIFIED — SOURCE RETRIEVED`: Yes, from current main branch.
- `UNVERIFIED — LOGIC`: Full call-graph and tests not yet checked.
- `UNVERIFIED — LIVE BEHAVIOR`: No live side effects invoked.
