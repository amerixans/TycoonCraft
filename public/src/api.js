/* Server calls.
 *
 * Every URL is derived from the document, never hardcoded. Getting this wrong
 * is the classic microapp failure: an absolute `/api/state` resolves to the
 * *domain* root, so the app works locally at `/` and 404s everything the moment
 * it is mounted at `/tycooncraft/`. The server also strips BASE_PATH
 * defensively, so the two halves agree from both directions.
 *
 * Auth is a player id in an `X-Player` header, kept in localStorage. No
 * cookies, which means no CSRF surface -- a cross-origin form post cannot set
 * a custom header.
 */

const STORAGE_KEY = 'tycooncraft.player';

function computeBase() {
  const url = new URL(document.baseURI);
  let path = url.pathname;
  if (/\/[^/]*\.[^/]*$/.test(path)) {
    path = path.replace(/\/[^/]*$/, '/');      // .../index.html -> .../
  } else if (!path.endsWith('/')) {
    path += '/';                               // /tycooncraft -> /tycooncraft/
  }
  return url.origin + path;
}

export const BASE = computeBase();

export function resumeLink(id) {
  // The id goes in the fragment, not the query string. A fragment is never
  // sent to the server, so it stays out of the nginx access log and out of the
  // Referer header on any link the page later opens -- which matters because
  // this id is the whole credential, not a hint about one.
  return `${BASE}#p=${encodeURIComponent(id)}`;
}

export function savedPlayer() {
  // A resume link wins over whatever is stored, so opening your own link on a
  // device that already has a game switches to the linked one rather than
  // silently ignoring the link.
  //
  // ?p= is still read because links minted before the move to a fragment are
  // out there in people's bookmarks, and breaking them would strand a save.
  const url = new URL(location.href);
  const fromHash = new URLSearchParams(url.hash.replace(/^#/, '')).get('p');
  const fromLink = fromHash || url.searchParams.get('p');
  if (fromLink) {
    localStorage.setItem(STORAGE_KEY, fromLink);
    // Drop it from the address bar either way, so the id is not left sitting in
    // history or in a screenshot of the URL.
    history.replaceState({}, '', BASE);
    return fromLink;
  }
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;                               // private mode with storage off
  }
}

export function storePlayer(id) {
  try { localStorage.setItem(STORAGE_KEY, id); } catch { /* non-fatal */ }
}

export function forgetPlayer() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* non-fatal */ }
}

let playerId = null;
export function setPlayer(id) { playerId = id; }

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body || {};
    this.kind = this.body.kind || null;
  }
}
export { ApiError };

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (playerId) headers['X-Player'] = playerId;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  let res;
  try {
    res = await fetch(new URL(path, BASE), {
      ...options,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (cause) {
    // Offline or the droplet is down. Surfaced as a normal ApiError so callers
    // have one thing to catch.
    throw new ApiError('could not reach the server', 0, { kind: 'network' });
  }

  let body = null;
  try { body = await res.json(); } catch { /* empty or non-JSON body */ }

  if (!res.ok) {
    throw new ApiError((body && body.error) || `request failed (${res.status})`, res.status, body);
  }
  return body;
}

export const api = {
  health:   ()             => request('health'),
  create:   (name)         => request('api/new',      { method: 'POST', body: { name } }),
  state:    ()             => request('api/state'),
  feed:     ()             => request('api/feed'),
  craft:    (a, b)         => request('api/craft',    { method: 'POST', body: { a, b } }),
  gather:   (placement)    => request('api/gather',   { method: 'POST', body: { placement } }),
  sellAll:  (item)         => request('api/sell',     { method: 'POST', body: { item, all: true } }),
  unlock:   ()             => request('api/unlock',   { method: 'POST', body: {} }),
  remove:   (placement)    => request('api/remove',   { method: 'POST', body: { placement } }),
  autosell: (placement, on) => request('api/autosell', { method: 'POST', body: { placement, on } }),
  placeProducer: (item, autosell) =>
    request('api/place', { method: 'POST', body: { kind: 'producer', item, autosell } }),
  // Inputs are not passed: the output's key already records which two buckets
  // make it, so the server picks from the player's own stock.
  placeFactory: (output, autosell) =>
    request('api/place', { method: 'POST', body: { kind: 'factory', output, autosell } }),
};
