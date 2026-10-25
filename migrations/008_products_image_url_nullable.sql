-- Generated image bytes are sent directly to Pinterest and are not persisted in Neon.
-- Keep the column for legacy/external URLs, but allow metadata-only product rows.
ALTER TABLE products ALTER COLUMN image_url DROP NOT NULL;
