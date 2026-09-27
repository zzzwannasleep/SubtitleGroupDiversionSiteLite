CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'publisher', 'user')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS torrents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_torrents_created ON torrents(created_at);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    key TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TEXT NOT NULL,
    last_used TEXT,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 默认管理员：密码不存库，登录时直接比对 ADMIN_PASSWORD secret
INSERT OR IGNORE INTO users (id, username, password, role, created_at)
VALUES ('admin', 'admin', '!', 'admin', '1970-01-01T00:00:00+08:00');
