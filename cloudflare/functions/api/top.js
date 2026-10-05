// GET /api/top: the Top Ten.
import { json, publicTop, top } from '../../lib/club.js';

export async function onRequestGet({ env }) {
  return json({ top: publicTop(await top(env.TOP)) });
}
