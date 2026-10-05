// node --test cloudflare/test.mjs (after cloudflare/build.sh has built lib/core.wasm)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { allowed, claim, cleanName, newToken, readToken, record, replay, top, TOKEN_TTL } from './lib/club.js';

const here = new URL('.', import.meta.url);
const core = new WebAssembly.Module(readFileSync(new URL('lib/core.wasm', here)));
// three games recorded from the original LINES.EXE (re/emu/record.py): the seed, the moves with
// their clock readings, and the original's final score
const games = JSON.parse(readFileSync(new URL('../tests/fixtures/games.json', here)));

function memoryKv(store = new Map()) {
  return { get: async (k, t) => (store.has(k) ? (t === 'json' ? JSON.parse(store.get(k)) : store.get(k)) : null),
           put: async (k, v) => { store.set(k, v); }, delete: async (k) => { store.delete(k); } };
}

test('the core replays recorded games to the original scores', () => {
  for (const g of games) {
    const r = replay(core, g.seed, g.moves);
    assert.equal(r.status, 'ok');
    assert.equal(r.score, g.score);
    assert.equal(r.over, true);
  }
});

test('an illegal or malformed move is refused', () => {
  const g = games[0];
  const moves = g.moves.map((m) => [...m]);
  moves[3] = [moves[3][2], moves[3][3], moves[3][0], moves[3][1], moves[3][4], moves[3][5]];
  assert.equal(replay(core, g.seed, moves).status, 'illegal');
  assert.equal(replay(core, g.seed, [[0, 1, 2, 3, 0, 0]]).status, 'bad-moves');
  assert.equal(replay(core, g.seed, 'x').status, 'bad-moves');
  assert.equal(replay(core, g.seed, [...g.moves, g.moves[0]]).status, 'illegal'); // after the end
});

test('tokens are signed, expire, and carry the seed', async () => {
  const { seed, token } = await newToken('s3cret', 1000);
  assert.equal((await readToken('s3cret', token, 2000)).seed, seed);
  assert.equal(await readToken('other', token, 2000), null);
  assert.equal(await readToken('s3cret', token, 1000 + TOKEN_TTL + 1), null);
});

test('names', () => {
  assert.equal(cleanName(' Mom '), 'Mom');
  assert.equal(cleanName('x'.repeat(11)), null);
  assert.equal(cleanName('Мама'), null); // the game's font has no Cyrillic
});

test('names are unique, case-insensitively', async () => {
  const kv = memoryKv();
  assert.equal(await claim(kv, 'aaaaaaaa', 'Mom'), true);
  assert.equal(await claim(kv, 'bbbbbbbb', 'MOM'), false);
  assert.equal(await claim(kv, 'aaaaaaaa', 'Dad'), true);
  assert.equal(await claim(kv, 'bbbbbbbb', 'mom'), true);
});

test('the Top Ten: a score goes above the first strictly lower one', async () => {
  const kv = memoryKv();
  assert.equal(await record(kv, 'a', 'A', 100), 1);
  assert.equal(await record(kv, 'b', 'B', 200), 1);
  assert.equal(await record(kv, 'c', 'C', 100), 3); // equal does not displace
  assert.deepEqual((await top(kv)).map((r) => r.name), ['B', 'A', 'C']);
});

test('rate limits count per kind, address and hour', async () => {
  const kv = memoryKv();
  for (let i = 0; i < 3; i++) assert.equal(await allowed(kv, '1.2.3.4', 0, 'nl', 3), true);
  assert.equal(await allowed(kv, '1.2.3.4', 0, 'nl', 3), false);
});
