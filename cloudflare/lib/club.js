// The global Color Lines Top Ten: games are dealt with a server seed and checked by replaying
// them with the game's own core (core.wasm, the same C as the game), so a score cannot be made
// up. The repository is public: nothing here relies on being secret except LINES_SECRET.
export const TOKEN_TTL = 24 * 3600 * 1000; // a game must be submitted within a day
export const TOP_KEEP = 100;
export const DAY = 24 * 360000;            // hundredths of a second
const TOKENS_PER_HOUR = 60;

const enc = new TextEncoder();
const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

async function hmac(secret, text) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']);
  return b64url(await crypto.subtle.sign('HMAC', key, enc.encode(text)));
}

export function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

// seed.issued.nonce.signature
export async function newToken(secret, now = Date.now()) {
  const r = crypto.getRandomValues(new Uint32Array(3));
  const payload = `${r[0]}.${now}.${r[1].toString(36)}${r[2].toString(36)}`;
  return { seed: r[0], token: `${payload}.${await hmac(secret, payload)}` };
}

export async function readToken(secret, token, now = Date.now()) {
  const parts = String(token || '').split('.');
  if (parts.length !== 4) return null;
  const payload = parts.slice(0, 3).join('.');
  if (await hmac(secret, payload) !== parts[3]) return null;
  const seed = Number(parts[0]), issued = Number(parts[1]);
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff || !Number.isFinite(issued)) return null;
  if (now - issued > TOKEN_TTL || issued > now + 60000) return null;
  return { seed, issued, nonce: parts[2] };
}

// names as the game's font can draw them: up to 10 characters, ASCII 32..122
export function cleanName(name) {
  const s = String(name || '').trim();
  if (!s.length || s.length > 10) return null;
  return /^[\x20-\x7a]+$/.test(s) ? s : null;
}

export const cleanId = (id) => (/^[a-z0-9-]{8,64}$/.test(String(id || '')) ? id : null);

// coreModule: core.wasm as a WebAssembly.Module (the Pages bundler imports it, tests read it).
// moves: [fx, fy, tx, ty, t0, t1] each (t0, t1 hundredths of a second since midnight).
const instances = new WeakMap();
export function replay(coreModule, seed, moves) {
  if (!Array.isArray(moves) || !moves.every((m) => Array.isArray(m) && m.length === 6 &&
      m.every((v, i) => Number.isInteger(v) && (i < 4 ? v >= 1 && v <= 9 : v >= 0 && v < DAY)))) {
    return { status: 'bad-moves' };
  }
  let instance = instances.get(coreModule);
  if (!instance) {
    instance = new WebAssembly.Instance(coreModule, {});
    instance.exports._initialize?.();
    instances.set(coreModule, instance);
  }
  const x = instance.exports;
  if (moves.length > x.capacity()) return { status: 'too-long' };
  new Int32Array(x.memory.buffer, x.buffer(), moves.length * 6).set(moves.flat());
  const score = x.verify(seed >>> 0, moves.length);
  if (score < 0) return { status: 'illegal' };
  return { status: 'ok', score, thought: x.thought() / 100, over: !!x.over() };
}

// at most `limit` requests of a kind per address and hour (games started, names tried)
export async function allowed(kv, ip, now = Date.now(), kind = 'rl', limit = TOKENS_PER_HOUR) {
  const key = `${kind}:${ip}:${Math.floor(now / 3600000)}`;
  const n = Number(await kv.get(key)) || 0;
  if (n >= limit) return false;
  await kv.put(key, String(n + 1), { expirationTtl: 7200 });
  return true;
}

export async function top(kv) {
  return (await kv.get('top', 'json')) || [];
}

// Books a checked game into the Top Ten (and its longer list); the rank, 1-based, 0 if not in.
// As in the original, a new score goes above the first entry with a strictly lower score.
export async function record(kv, id, name, score, now = Date.now()) {
  const list = await top(kv);
  let at = list.findIndex((r) => r.score < score);
  if (at < 0) at = list.length;
  if (at >= TOP_KEEP) return 0;
  list.splice(at, 0, { id, name, score, at: now });
  await kv.put('top', JSON.stringify(list.slice(0, TOP_KEEP)));
  return at + 1;
}

export const publicTop = (list) => list.slice(0, 10).map(({ name, score }) => ({ name, score }));

// Names are unique in the club, compared as the original did (upper case). A name belongs to
// the first member (browser) that took it; renaming frees the old one.
export const foldName = (name) => name.toUpperCase();

export async function claim(kv, id, name) {
  const key = `n:${foldName(name)}`;
  const owner = await kv.get(key);
  if (owner && owner !== id) return false;
  if (!owner) {
    const m = await kv.get(`m:${id}`, 'json');
    if (m && m.name && foldName(m.name) !== foldName(name)) await kv.delete(`n:${foldName(m.name)}`);
    await kv.put(key, id);
    await kv.put(`m:${id}`, JSON.stringify({ ...(m || {}), name }));
  }
  return true;
}
