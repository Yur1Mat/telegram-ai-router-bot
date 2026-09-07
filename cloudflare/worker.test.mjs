import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import worker, { deliver, handleUpdate } from './worker.mjs';

function database() {
  const db = new DatabaseSync(':memory:');
  db.exec(readFileSync(new URL('./schema.sql', import.meta.url), 'utf8'));
  return { raw: db, prepare(sql) {
    const stmt = db.prepare(sql);
    return { bind(...args) { return {
      async run() { return stmt.run(...args); },
      async first() { return stmt.get(...args) || null; },
      async all() { return { results: stmt.all(...args) }; },
    }; } };
  } };
}
const now = Date.parse('2026-09-07T14:30:00Z');
test('delivery reaches every active subscriber, repeated cron does not duplicate', async () => {
  const DB = database();
  DB.raw.exec("INSERT INTO subscribers VALUES('1',1,0,-1),('2',1,0,-1),('3',0,0,-1)");
  const sent = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (_, opts) => { sent.push(JSON.parse(opts.body)); return Response.json({ok:true}); };
  try {
    const env = { DB, DELIVERY_ENABLED:'true', TELEGRAM_BOT_TOKEN:'test' };
    await deliver(env, now); await deliver(env, now + 60000);
    assert.deepEqual(sent.map(s=>s.chat_id), ['1','2']);
    assert.equal(sent[0].text, sent[1].text);
  } finally { globalThis.fetch = original; DB.raw.close(); }
});
test('403 disables subscriber, transient errors are retried', async () => {
  const DB = database();
  DB.raw.exec("INSERT INTO subscribers VALUES('1',1,0,-1),('2',1,0,-1)");
  const original = globalThis.fetch;
  let fail = true;
  globalThis.fetch = async (_, opts) => {
    const chat = JSON.parse(opts.body).chat_id;
    return Response.json(chat==='1' ? {ok:false,error_code:403} : fail ? {ok:false,error_code:429,parameters:{retry_after:60}} : {ok:true});
  };
  try {
    const env = { DB, DELIVERY_ENABLED:'true' };
    await deliver(env, now);
    assert.equal(DB.raw.prepare("SELECT active FROM subscribers WHERE chat_id='1'").get().active,0);
    fail = false; await deliver(env, now+60001);
    assert.equal(DB.raw.prepare("SELECT status FROM deliveries WHERE chat_id='2'").get().status,'sent');
  } finally { globalThis.fetch=original; DB.raw.close(); }
});
test('start/stop persists; older updates cannot undo stop', async () => {
  const DB=database(); const original=globalThis.fetch;
  globalThis.fetch=async()=>Response.json({ok:true});
  const update=(id,text)=>({update_id:id,message:{chat:{id:1,type:'private'},text}});
  try {
    await handleUpdate(update(10,'/start'),{DB});
    assert.equal(DB.raw.prepare('SELECT active FROM subscribers').get().active,1);
    await handleUpdate(update(11,'/stop'),{DB});
    await handleUpdate(update(10,'/start'),{DB});
    assert.equal(DB.raw.prepare('SELECT active FROM subscribers').get().active,0);
  } finally { globalThis.fetch=original; DB.raw.close(); }
});
test('unauthenticated webhook is rejected without database access', async () => {
  const response=await worker.fetch(new Request('https://example.org/telegram',{method:'POST',body:'{}'}),{WEBHOOK_SECRET:'secret'});
  assert.equal(response.status,403);
});
