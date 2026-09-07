CREATE TABLE IF NOT EXISTS subscribers (
  chat_id TEXT PRIMARY KEY,
  active INTEGER NOT NULL DEFAULT 1,
  since INTEGER NOT NULL,
  update_id INTEGER NOT NULL DEFAULT -1
);
CREATE INDEX IF NOT EXISTS subscribers_active ON subscribers(active, since);
CREATE TABLE IF NOT EXISTS deliveries (
  chat_id TEXT NOT NULL,
  slot TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  lease_until INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(chat_id, slot)
);
CREATE TABLE IF NOT EXISTS runtime (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
