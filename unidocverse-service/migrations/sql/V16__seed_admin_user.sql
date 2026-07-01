-- V16__seed_admin_user.sql
-- Seeds the default admin user on fresh installs.
-- Default credentials: admin / admin
-- !! Customer MUST change password on first login !!

INSERT INTO users (username, email, full_name, password_hash, role, is_active, avatar_color)
VALUES (
    'admin',
    'admin@local',
    'Admin User',
    '$2b$12$Feh.Fo/gn7wllSvZu9z25e28uTyAnRPOjqrbAqRzGGZV0eKmWE8By',
    'admin',
    TRUE,
    '#6366f1'
)
ON CONFLICT (username) DO NOTHING;