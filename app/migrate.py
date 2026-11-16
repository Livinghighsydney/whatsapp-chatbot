"""Run once at startup — creates tables and applies additive column migrations."""
from __future__ import annotations

import logging
from app import db

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS staff_users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            TEXT UNIQUE NOT NULL,
    name             TEXT NOT NULL DEFAULT '',
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'agent',
    whatsapp_number  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO settings (key, value)
VALUES ('handoff_mode', 'dashboard'), ('session_counter', '0')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS shifts (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_user_id  UUID NOT NULL REFERENCES staff_users(id) ON DELETE CASCADE,
    weekday        INT NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time     TIME NOT NULL,
    end_time       TIME NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_phone      TEXT UNIQUE NOT NULL,
    tenant_name       TEXT,
    property_address  TEXT,
    room              TEXT,
    status            TEXT NOT NULL DEFAULT 'bot_active',
    assigned_staff_id UUID REFERENCES staff_users(id) ON DELETE SET NULL,
    session_id        TEXT,
    handoff_reason    TEXT,
    info_collected    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL,
    content          TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Additive column migrations (safe to re-run)
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_read_at TIMESTAMPTZ;

-- RAG: KB content chunks with Voyage AI embeddings (1024 dims)
CREATE TABLE IF NOT EXISTS chunks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_page_id       TEXT NOT NULL,
    kb_page_title    TEXT NOT NULL DEFAULT '',
    kb_page_type     TEXT NOT NULL DEFAULT 'general',
    visibility       TEXT NOT NULL DEFAULT 'general',
    property_id      INTEGER,
    room_number      TEXT,
    parent_chunk_id  UUID REFERENCES chunks(id) ON DELETE CASCADE,
    chunk_index      INTEGER NOT NULL DEFAULT 0,
    heading          TEXT,
    content          TEXT NOT NULL,
    embedding        vector(1024),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'general';
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS room_number TEXT;

CREATE INDEX IF NOT EXISTS chunks_kb_page_id_idx ON chunks(kb_page_id);
CREATE INDEX IF NOT EXISTS chunks_property_id_idx ON chunks(property_id);
CREATE INDEX IF NOT EXISTS chunks_room_number_idx ON chunks(room_number);
CREATE INDEX IF NOT EXISTS chunks_visibility_idx ON chunks(visibility);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def run() -> None:
    try:
        with db.conn() as c:
            c.cursor().execute(_SCHEMA)
        logger.info("DB migrations complete")
    except Exception:
        logger.exception("DB migration failed — check DATABASE_URL and schema")
        raise
