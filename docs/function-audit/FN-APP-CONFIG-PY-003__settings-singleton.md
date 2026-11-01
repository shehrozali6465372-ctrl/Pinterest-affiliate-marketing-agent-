# settings module singleton

- **Unique ID:** FN-APP-CONFIG-PY-003
- **Source:** app/config.py:1-27
- **Source revision:** main, refreshed during audit on 2026-11-01
- **Status:** VERIFIED — SOURCE RETRIEVED; logic static only

## Purpose
Constructs one module-level Pydantic settings object from environment configuration.

## Line-by-line behavior
- Lines 1-4: module documentation and imports; Pydantic settings/validator support plus Unicode category inspection.
- Lines 7-24: the Settings model and its configuration surface. `env_file=".env"` permits local dotenv loading; `extra="ignore"` ignores undeclared environment values. Settings include API/database/Pinterest/Cloudflare/LLM credentials and provider defaults. The configured LLM defaults to DeepSeek at `https://api.deepseek.com` with model identifier `deepseek-flash`.
- Line 27: instantiates Settings at import time; environment is read when this module is imported/constructed.

## Security and operational implications
Secret values are held in process memory as settings attributes. This module does not persist OAuth account credentials; those are handled by credential_vault. Configuration presence does not prove provider connectivity or token validity. Import-time construction means tests that mutate environment after import must patch the singleton or reload the module.

## Call graph and evidence
Imported by application/provider modules. This audit retrieved the exact source; no runtime provider or secret operation was performed. No independent runtime behavior claim is made.
