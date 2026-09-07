import messages from './messages.json' with { type: 'json' };
import { latestSlot, messageIndex } from './schedule.mjs';

async function telegram(env, method, body) {
  try {
    const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
    });
    const result = await response.json();
    return { ok: result.ok === true, code: result.error_code || response.status,
      retry: result.parameters?.retry_after || 60 };
  } catch {
    // Never log exceptions containing a Telegram URL/token or user data.
    return { ok: false, code: 0, retry: 180 };
  }
}

export async function handleUpdate(update, env) {
  const message = update.message;
  if (!Number.isSafeInteger(update.update_id) || message?.chat?.type !== 'private'
      || !Number.isSafeInteger(message.chat.id) || typeof message.text !== 'string') return;
  const chat = String(message.chat.id);
  const command = message.text.trim().split(/\s+/)[0].split('@')[0].toLowerCase();
  if (!['/start', '/stop', '/status', '/help'].includes(command)) return;
  const now = Date.now();
  if (command === '/start' || command === '/stop') {
    const active = command === '/start' ? 1 : 0;
    await env.DB.prepare(`INSERT INTO subscribers(chat_id,active,since,update_id) VALUES(?,?,?,?)
      ON CONFLICT(chat_id) DO UPDATE SET active=excluded.active,
      since=CASE WHEN subscribers.active=0 AND excluded.active=1 THEN excluded.since ELSE subscribers.since END,
      update_id=excluded.update_id WHERE excluded.update_id>subscribers.update_id`)
      .bind(chat, active, now, update.update_id).run();
  }
  const subscriber = await env.DB.prepare('SELECT active,update_id FROM subscribers WHERE chat_id=?').bind(chat).first();
  // An old Telegram retry must not override or announce a newer command.
  if (subscriber && update.update_id < subscriber.update_id) return;
  const text = command === '/stop' ? 'Рассылка отключена. Вернуться: /start 💛'
    : command === '/help' ? 'Два добрых пожелания каждый день: 08:30 и 17:30 по Москве. /start — подписаться, /stop — отключить, /status — проверить.'
    : subscriber?.active ? 'Подписка включена 💛 Пожелания приходят в 08:30 и 17:30 по Москве. Остановить: /stop.'
    : 'Подписка отключена. Включить: /start 💛';
  const result = await telegram(env, 'sendMessage', { chat_id: chat, text });
  if (!result.ok && result.code !== 403 && result.code !== 400) throw new Error('Reply temporarily unavailable');
}

export async function deliver(env, now = Date.now()) {
  await env.DB.prepare("INSERT INTO runtime(key,value) VALUES('last_cron',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    .bind(new Date(now).toISOString()).run();
  // A disabled deployment can be verified safely before secrets/subscribers are imported.
  if (env.DELIVERY_ENABLED !== 'true') return;
  const slot = latestSlot(now);
  if (!slot) return;
  const { results } = await env.DB.prepare(`SELECT s.chat_id FROM subscribers s
    LEFT JOIN deliveries d ON d.chat_id=s.chat_id AND d.slot=?
    WHERE s.active=1 AND s.since<=? AND (d.status IS NULL OR (d.status='pending' AND d.lease_until<=?))
    ORDER BY COALESCE(d.attempts,0),s.chat_id LIMIT 10`)
    .bind(slot.key, slot.scheduledAt, now).all();
  let sent = 0;
  for (const row of results) {
    // Atomic lease prevents overlapping cron invocations from sending the same slot.
    const claim = await env.DB.prepare(`INSERT INTO deliveries(chat_id,slot,lease_until,attempts) VALUES(?,?,?,1)
      ON CONFLICT(chat_id,slot) DO UPDATE SET lease_until=excluded.lease_until,attempts=deliveries.attempts+1
      WHERE deliveries.status='pending' AND deliveries.lease_until<=? RETURNING chat_id`)
      .bind(row.chat_id, slot.key, now + 180000, now).first();
    if (!claim) continue;
    const active = await env.DB.prepare('SELECT active FROM subscribers WHERE chat_id=?').bind(row.chat_id).first();
    if (!active?.active) continue;
    const result = await telegram(env, 'sendMessage', {
      chat_id: row.chat_id, text: messages[messageIndex(slot, messages.length)],
    });
    if (result.ok) {
      await env.DB.prepare("UPDATE deliveries SET status='sent',lease_until=0 WHERE chat_id=? AND slot=?")
        .bind(row.chat_id, slot.key).run();
      sent++;
    } else if (result.code === 403) {
      await env.DB.prepare('UPDATE subscribers SET active=0 WHERE chat_id=?').bind(row.chat_id).run();
    } else {
      await env.DB.prepare('UPDATE deliveries SET lease_until=? WHERE chat_id=? AND slot=?')
        .bind(now + Math.max(60, result.retry) * 1000, row.chat_id, slot.key).run();
    }
  }
  console.log(JSON.stringify({ event: 'delivery', candidates: results.length, sent }));
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (request.method === 'GET' && path === '/health') return new Response('ok');
    if (request.method !== 'POST' || path !== '/telegram') return new Response('Not found', { status: 404 });
    if (!env.WEBHOOK_SECRET || request.headers.get('X-Telegram-Bot-Api-Secret-Token') !== env.WEBHOOK_SECRET)
      return new Response('Forbidden', { status: 403 });
    try {
      const raw = await request.text();
      if (raw.length > 65536) return new Response('Too large', { status: 413 });
      await handleUpdate(JSON.parse(raw), env);
      return new Response('ok');
    } catch {
      return new Response('Retry later', { status: 503 });
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(deliver(env, event.scheduledTime));
  },
};
