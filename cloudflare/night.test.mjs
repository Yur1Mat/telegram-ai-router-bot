import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { NIGHT_MESSAGES, nightSlot, nightChance, nightDecision } from './night.mjs';
import { deliver } from './worker.mjs';

function database() {
  const raw = new DatabaseSync(':memory:');
  raw.exec(readFileSync(new URL('./schema.sql', import.meta.url), 'utf8'));
  return { raw, prepare(sql) {
    const stmt = raw.prepare(sql);
    return { bind(...args) { return {
      async run() { return stmt.run(...args); },
      async first() { return stmt.get(...args) || null; },
      async all() { return { results: stmt.all(...args) }; },
    }; } };
  } };
}

test('night window uses 04:00 Moscow and ends at the morning slot', () => {
  assert.equal(nightSlot(Date.parse('2026-09-26T00:59:59Z')), null);
  assert.equal(nightSlot(Date.parse('2026-09-26T01:00:00Z')).key, 'night:2026-09-26');
  assert.equal(nightSlot(Date.parse('2026-09-26T05:29:59Z')).key, 'night:2026-09-26');
  assert.equal(nightSlot(Date.parse('2026-09-26T05:30:00Z')), null);
  assert.equal(nightChance({}), 10);
  assert.equal(nightChance({ NIGHT_MESSAGE_CHANCE_PERCENT: '0' }), 0);
});

test('chance is decided once per date, messages are random and never reused', async () => {
  const db = database();
  try {
    assert.equal(await nightDecision(db, '2026-09-01', 0, () => 0), null);
    assert.equal(await nightDecision(db, '2026-09-01', 100, () => 0), null);
    const indices = [];
    for (let day = 2; day <= NIGHT_MESSAGES.length + 2; day++) {
      indices.push(await nightDecision(db, `2026-09-${String(day).padStart(2, '0')}`, 100, () => 0.99));
    }
    assert.equal(new Set(indices.slice(0, -1)).size, NIGHT_MESSAGES.length);
    assert.equal(indices.at(-1), null);
  } finally { db.raw.close(); }
});

test('night delivery persists its draw and does not send twice on cron retry', async () => {
  const db = database();
  db.raw.exec("INSERT INTO subscribers VALUES('1',1,0,-1),('2',1,0,-1)");
  const sent = [], originalFetch = globalThis.fetch, originalRandom = Math.random;
  globalThis.fetch = async (_, opts) => { sent.push(JSON.parse(opts.body)); return Response.json({ ok: true }); };
  Math.random = () => 0;
  try {
    const env = { DB: db, DELIVERY_ENABLED: 'true', NIGHT_MESSAGE_CHANCE_PERCENT: '100' };
    const now = Date.parse('2026-09-26T01:00:00Z');
    await deliver(env, now);
    await deliver(env, now + 60_000);
    assert.equal(sent.length, 2);
    assert.equal(sent[0].text, sent[1].text);
    assert.ok(NIGHT_MESSAGES.includes(sent[0].text));
    assert.equal(db.raw.prepare('SELECT count(*) AS n FROM night_draws').get().n, 1);
    assert.equal(db.raw.prepare("SELECT count(*) AS n FROM deliveries WHERE status='sent'").get().n, 2);
  } finally { globalThis.fetch = originalFetch; Math.random = originalRandom; db.raw.close(); }
});
