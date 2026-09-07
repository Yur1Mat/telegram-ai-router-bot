import test from 'node:test';
import assert from 'node:assert/strict';
import { latestSlot, messageIndex } from './schedule.mjs';

test('08:30 and 17:30 Moscow, not UTC', () => {
  assert.equal(latestSlot(Date.parse('2026-09-07T05:29:59Z')), null);
  const morning = latestSlot(Date.parse('2026-09-07T05:30:00Z'));
  assert.equal(morning.key, '2026-09-07:0');
  assert.equal(morning.scheduledAt, Date.parse('2026-09-07T05:30:00Z'));
  assert.equal(latestSlot(Date.parse('2026-09-07T14:29:59Z')).key, morning.key);
  const evening = latestSlot(Date.parse('2026-09-07T14:30:00Z'));
  assert.equal(evening.key, '2026-09-07:1');
  assert.equal(evening.sequence, morning.sequence + 1);
});

test('day boundary is Moscow midnight', () => {
  assert.equal(latestSlot(Date.parse('2026-09-07T21:00:00Z')), null);
});

test('2305 distinct indices cover three years of two wishes daily', () => {
  const indices = new Set();
  const start = Date.parse('2026-09-07T05:30:00Z');
  for (let day = 0; day < 1096; day++) {
    for (const hours of [0, 9]) {
      indices.add(messageIndex(latestSlot(start + day * 86_400_000 + hours * 3_600_000), 2305));
    }
  }
  assert.equal(indices.size, 2192);
});
