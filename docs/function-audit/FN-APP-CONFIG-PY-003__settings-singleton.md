# settings — source-level review

- ID: `FN-APP-CONFIG-PY-003`; source `app/config.py:41`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Instantiates `Settings()` at module import and exposes the object as shared configuration. Pydantic Settings resolves environment/.env values at construction time; imports across app modules reuse the same object reference. It is not a dynamic environment watcher.

## Callers and tests
Imported by main, database, credential vault, workflow, diagnostics, learning, content generation, media generation and Pinterest clients. Tests monkeypatch attributes on this singleton to isolate behavior. Changing process environment after import will not update values unless Settings is reconstructed/reloaded.
