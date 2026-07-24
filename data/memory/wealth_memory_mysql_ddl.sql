-- ============================================================
-- Wealth Management Assistant — MEMORY database (MySQL DDL)
-- ============================================================
-- Stores BOTH memory tiers used by the LangGraph agents:
--
--   Short-term memory (per session)
--     - chat_sessions   : one row per session + rolling summary
--     - chat_messages   : every user/assistant turn (time-ordered Q&A)
--
--   Long-term memory (per client, across sessions)
--     - episodic_memory    : one row per completed Q&A turn
--     - semantic_memory     : durable, deduplicated client facts
--     - procedural_memory   : behavioural patterns + frequency counter
--     - client_preferences  : structured key→value client preferences
--
-- Engine: InnoDB (FK + transactions). Charset: utf8mb4 (full Unicode).
-- All timestamps are stored in UTC by the application layer.
-- ============================================================

CREATE DATABASE IF NOT EXISTS wealth_memory
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE wealth_memory;

-- Drop children before parents (safe re-run).
DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS chat_sessions;
DROP TABLE IF EXISTS episodic_memory;
DROP TABLE IF EXISTS semantic_memory;
DROP TABLE IF EXISTS procedural_memory;
DROP TABLE IF EXISTS client_preferences;

-- ============================================================
-- SHORT-TERM MEMORY
-- ============================================================

CREATE TABLE chat_sessions (
    session_id    VARCHAR(100) NOT NULL,
    client_id     VARCHAR(64) NOT NULL DEFAULT 'unknown',  -- owning client
    summary       TEXT NULL,                       -- rolling short-term summary
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_updated  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id),
    KEY ix_chat_sessions_client_id (client_id),
    KEY ix_chat_sessions_last_updated (last_updated),
    -- List a client's sessions newest-first.
    KEY ix_chat_sessions_client_updated (client_id, last_updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_messages (
    id          BIGINT NOT NULL AUTO_INCREMENT,
    session_id  VARCHAR(100) NOT NULL,
    role        VARCHAR(20) NOT NULL,              -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_chat_messages_session_id (session_id),
    KEY ix_chat_messages_created_at (created_at),
    -- Time-ordered retrieval of a session's Q&A turns.
    KEY ix_chat_messages_session_created (session_id, created_at),
    CONSTRAINT fk_chat_messages_session
        FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- LONG-TERM MEMORY — EPISODIC (one row per Q&A turn)
-- ============================================================

CREATE TABLE episodic_memory (
    id          CHAR(36) NOT NULL,                 -- uuid4
    client_id   VARCHAR(64) NOT NULL,
    session_id  VARCHAR(100) NOT NULL,
    query       TEXT NOT NULL,
    answer      TEXT NOT NULL,
    intent      VARCHAR(64) NOT NULL,
    confidence  DECIMAL(5,3) NOT NULL DEFAULT 1.000,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_episodic_client_id (client_id),
    KEY ix_episodic_created_at (created_at),
    -- Pull the most-recent episodes for a client quickly.
    KEY ix_episodic_client_created (client_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- LONG-TERM MEMORY — SEMANTIC (durable, deduplicated facts)
-- ============================================================

CREATE TABLE semantic_memory (
    id            CHAR(36) NOT NULL,               -- uuid4
    client_id     VARCHAR(64) NOT NULL,
    fact          TEXT NOT NULL,
    fact_hash     CHAR(64) NOT NULL,               -- sha256(lower(trim(fact)))
    confidence    DECIMAL(5,3) NOT NULL DEFAULT 0.850,
    source_query  VARCHAR(500) NOT NULL DEFAULT '',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_semantic_client_id (client_id),
    KEY ix_semantic_client_created (client_id, created_at),
    -- DB-level dedup: one fact (by hash) per client.
    UNIQUE KEY uq_semantic_client_fact (client_id, fact_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- LONG-TERM MEMORY — PROCEDURAL (behavioural patterns + frequency)
-- ============================================================

CREATE TABLE procedural_memory (
    id            CHAR(36) NOT NULL,               -- uuid4
    client_id     VARCHAR(64) NOT NULL,
    pattern       TEXT NOT NULL,
    pattern_hash  CHAR(64) NOT NULL,               -- sha256(lower(trim(pattern)))
    frequency     INT NOT NULL DEFAULT 1,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_procedural_client_id (client_id),
    KEY ix_procedural_client_freq (client_id, frequency),
    -- DB-level dedup: one pattern (by hash) per client; frequency is bumped.
    UNIQUE KEY uq_procedural_client_pattern (client_id, pattern_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- LONG-TERM MEMORY — PREFERENCES (structured key→value)
-- ============================================================

CREATE TABLE client_preferences (
    id          CHAR(36) NOT NULL,                 -- uuid4
    client_id   VARCHAR(64) NOT NULL,
    category    VARCHAR(64) NOT NULL DEFAULT 'general',  -- risk|investment|communication|general
    pref_key    VARCHAR(100) NOT NULL,             -- e.g. 'risk_tolerance'
    pref_value  TEXT NOT NULL,
    confidence  DECIMAL(5,3) NOT NULL DEFAULT 0.800,
    source      VARCHAR(20) NOT NULL DEFAULT 'inferred',  -- explicit|inferred
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_pref_client_id (client_id),
    KEY ix_pref_client_category (client_id, category),
    -- One value per (client, key); an upsert overwrites the existing value.
    UNIQUE KEY uq_pref_client_key (client_id, pref_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
