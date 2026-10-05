// POST /api/game: a seed for a new game, signed so the result can be checked against it.
import { allowed, json, newToken } from '../../lib/club.js';

export async function onRequestPost({ request, env }) {
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (!(await allowed(env.TOP, ip))) return json({ error: 'too many games, try again later' }, 429);
  return json(await newToken(env.LINES_SECRET));
}
