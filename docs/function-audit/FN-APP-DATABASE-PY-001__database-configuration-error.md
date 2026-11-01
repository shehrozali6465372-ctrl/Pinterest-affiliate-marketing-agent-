# FN-APP-DATABASE-PY-001 — DatabaseConfigurationError

Source: `app/database.py`, baseline blob SHA `7000abf6365c60b4543e353a72bbbcce2c49d2dd`, lines 15–16.

The class subclasses RuntimeError and distinguishes absent/invalid database configuration from query or provider failures. It is raised by `get_pool()` when DATABASE_URL is not configured and is mapped to sanitized service-unavailable responses in routes that catch it explicitly. It carries no custom fields or secret material. It does not classify general psycopg connection failures; those remain driver exceptions.