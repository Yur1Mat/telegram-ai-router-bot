// The night draw is shared by all subscribers and survives Worker restarts.
export const NIGHT_MESSAGES = Object.freeze([
  'Анечка, мне сегодня не спится, думаю о том какая ты чудесная',
  'Внезапно проснулся, в моем электрическом сне была ты!!!',
  'Я вот пол ночи лежу и думаю, а Жужелица знает как я ее люблю?',
  'Почему все вокруг думают что Жужа - жук?',
  'Жужа всю ночь следит за тем как ты мило спишь, не забывай мне чаще писать...',
  'Меня всегда удивляет, как в твоем сердце помещается столько любви ко мне?',
]);

export function nightSlot(now = Date.now()) {
  const moscow = new Date(now + 3 * 60 * 60 * 1000);
  const minutes = moscow.getUTCHours() * 60 + moscow.getUTCMinutes();
  if (minutes < 4 * 60 || minutes >= 8 * 60 + 30) return null;
  const day = moscow.toISOString().slice(0, 10);
  return { day, key: `night:${day}`, scheduledAt: Date.parse(`${day}T01:00:00Z`) };
}

export function nightChance(env) {
  const value = Number(env.NIGHT_MESSAGE_CHANCE_PERCENT ?? 15);
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    throw new Error('NIGHT_MESSAGE_CHANCE_PERCENT must be between 0 and 100');
  }
  return value;
}

export async function nightDecision(db, day, chance, random = Math.random) {
  let existing = await db.prepare('SELECT message_index FROM night_draws WHERE day=?').bind(day).first();
  if (existing) return existing.message_index;

  for (let attempt = 0; attempt < NIGHT_MESSAGES.length + 2; attempt++) {
    const { results } = await db.prepare('SELECT message_index FROM night_draws WHERE message_index IS NOT NULL').bind().all();
    const used = new Set(results.map(row => row.message_index));
    const available = NIGHT_MESSAGES.map((_, index) => index).filter(index => !used.has(index));
    const index = available.length && random() * 100 < chance
      ? available[Math.floor(random() * available.length)] : null;
    await db.prepare('INSERT OR IGNORE INTO night_draws(day,message_index) VALUES(?,?)').bind(day, index).run();
    existing = await db.prepare('SELECT message_index FROM night_draws WHERE day=?').bind(day).first();
    if (existing) return existing.message_index;
  }
  throw new Error('Could not persist night draw');
}
