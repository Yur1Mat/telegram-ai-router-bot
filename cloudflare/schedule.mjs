// Moscow has a fixed UTC+3 offset. Worker cron triggers use UTC.
const DAY = 86_400_000;
const MOSCOW = 3 * 3_600_000;
const EPOCH = Date.UTC(2026, 0, 1);

export function latestSlot(now = Date.now()) {
  const local = new Date(now + MOSCOW);
  const midnight = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate());
  const minutes = local.getUTCHours() * 60 + local.getUTCMinutes();
  if (minutes < 510) return null;
  const index = minutes >= 1050 ? 1 : 0;
  const scheduledAt = midnight + (index ? 1050 : 510) * 60_000 - MOSCOW;
  return {
    key: `${local.toISOString().slice(0, 10)}:${index}`,
    scheduledAt,
    sequence: Math.floor((midnight - EPOCH) / DAY) * 2 + index,
  };
}

export function messageIndex(slot, catalogLength) {
  return ((slot.sequence % catalogLength) + catalogLength) % catalogLength;
}
