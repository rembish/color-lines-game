// POST /api/name {id, name}: take a name for this member, or 409 if another member has it.
import { allowed, claim, cleanId, cleanName, json } from '../../lib/club.js';

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'bad request' }, 400);
  }
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (!(await allowed(env.TOP, ip, Date.now(), 'nl', 30))) return json({ error: 'too many names, try again later' }, 429);
  const id = cleanId(body.id), name = cleanName(body.name);
  if (!id || !name) return json({ error: 'bad name' }, 400);
  if (!(await claim(env.TOP, id, name))) return json({ error: 'taken' }, 409);
  return json({ name });
}
