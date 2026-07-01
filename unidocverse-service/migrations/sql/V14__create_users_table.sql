-- migrations/create_users_table.sql
-- Run once: psql -U unidocverse -p 54321 -d unidocverse_db -f this_file.sql

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    full_name     VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(50)  DEFAULT 'agent',   -- admin, agent
    is_active     BOOLEAN      DEFAULT TRUE,
    avatar_color  VARCHAR(7)   DEFAULT '#6366f1', -- hex color for initials avatar
    created_at    TIMESTAMP    DEFAULT NOW(),
    updated_at    TIMESTAMP    DEFAULT NOW(),
    last_login    TIMESTAMP,

    -- Future social login columns (nullable for now)
    google_id     VARCHAR(255),
    microsoft_id  VARCHAR(255),
    apple_id      VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- Default admin user: admin@unidocverse.com / admin
-- Password hash for 'admin' using bcrypt
INSERT INTO users (email, full_name, password_hash, role, avatar_color)
VALUES (
    'admin@unidocverse.com',
    'Admin User',
    '$2b$12$Feh.Fo/gn7wllSvZu9z25e28uTyAnRPOjqrbAqRzGGZV0eKmWE8By',
    'admin',
    '#6366f1'
) ON CONFLICT (email) DO NOTHING;