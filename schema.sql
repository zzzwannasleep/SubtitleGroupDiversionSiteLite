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
    publisher_name TEXT NOT NULL,
    -- 合集/分集：1=合集（内含多个文件或标题含合集关键词），0=分集，NULL=升级前的旧记录
    is_collection INTEGER,
    -- 系列键：去掉季号/集数标记后的“命名”，相同即视为同一系列
    series_key TEXT,
    -- 季号（S02 / 第2季），没有写季号为 NULL；合集与分集的季号兼容才互相取代
    season INTEGER
);
CREATE INDEX IF NOT EXISTS idx_torrents_created ON torrents(created_at);
CREATE INDEX IF NOT EXISTS idx_torrents_series ON torrents(series_key);

-- 已有部署升级：把下面三条粘到 D1 控制台执行一次即可（Worker 冷启动也会自动补列）
-- ALTER TABLE torrents ADD COLUMN is_collection INTEGER;
-- ALTER TABLE torrents ADD COLUMN series_key TEXT;
-- ALTER TABLE torrents ADD COLUMN season INTEGER;

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
