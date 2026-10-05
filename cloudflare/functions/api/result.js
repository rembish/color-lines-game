// POST /api/result {token, id, name, moves}: replays the game with the core and books its score
// into the Top Ten.
import coreModule from '../../lib/core.wasm';
import { claim, cleanId, cleanName, json, publicTop, readToken, record, replay, top } from '../../lib/club.js';

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'bad request' }, 400);
  }
  const t = await readToken(env.LINES_SECRET, body.token);
  if (!t) return json({ error: 'unknown or expired game' }, 403);
  const id = cleanId(body.id), name = cleanName(body.name);
  if (!id || !name) return json({ error: 'bad name' }, 400);
  if (!(await claim(env.TOP, id, name))) return json({ error: 'taken' }, 409);
  if (await env.TOP.get(`used:${t.nonce}`)) return json({ error: 'this game was already booked' }, 409);
  const r = replay(coreModule, t.seed, body.moves);
  if (r.status !== 'ok') return json({ error: `the game does not replay (${r.status})` }, 422);
  // the thinking times the moves claim must fit in the time since the game was dealt
  if (r.thought > (Date.now() - t.issued) / 1000 + 120) return json({ error: 'the times do not add up' }, 422);
  await env.TOP.put(`used:${t.nonce}`, '1', { expirationTtl: 2 * 24 * 3600 });
  const rank = await record(env.TOP, id, name, r.score);
  return json({ score: r.score, rank, top: publicTop(await top(env.TOP)) });
}
