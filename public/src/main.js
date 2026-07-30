/* Entry point: sign-in, state, and the three columns.
 *
 * The polling story matters here. v1 hit `/api/game-state` every 1000ms, and
 * every one of those requests ran the economy and wrote a row -- one database
 * write per second per player, plus a full re-serialisation of every discovery
 * and placement. So: poll every three seconds, and interpolate coins and
 * progress rings locally at frame rate in between. It looks live and costs the
 * droplet almost nothing.
 */

import { ApiError, api, forgetPlayer, resumeLink, savedPlayer, setPlayer, storePlayer }
  from './api.js';
import * as audio from './audio.js';
import { Bench, dragFromShelf, isDragging, onDragEnd } from './bench.js';
import { burst, centerOf, floatNumber, shake, tierColor, toast } from './fx.js';

const POLL_MS = 3000;
const $ = (id) => document.getElementById(id);

const state = {
  player: null,
  data: null,
  itemsByKey: new Map(),
  // Last-seen held counts, so a shelf rebuild can flash the ones that moved --
  // otherwise a producer ticking over is completely invisible.
  lastHeld: new Map(),
  freshKeys: new Set(),
  search: '',
  traitFilter: new Set(),
  // Coins are interpolated between polls from the server's income figure, so
  // the counter moves smoothly instead of jumping every three seconds.
  displayCoins: 0,
  coinRate: 0,
  lastPoll: 0,
};

let bench;

/* ------------------------------------------------------------------ boot */

async function boot() {
  bench = new Bench($('bench'), onCombine);
  wireChrome();

  const existing = savedPlayer();
  if (existing) {
    setPlayer(existing);
    try {
      await refresh();
      enterGame(existing);
      return;
    } catch (err) {
      // A stale id from a wiped database, or the droplet is down. Either way,
      // fall back to the gate rather than showing a broken screen.
      if (err instanceof ApiError && err.status === 401) forgetPlayer();
      else $('gate-note').textContent = 'Could not reach the server. Try reloading.';
    }
  }
  $('join-name').focus();
}

$('join-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  try {
    const { player } = await api.create($('join-name').value.trim() || 'Anon');
    storePlayer(player);
    setPlayer(player);
    await refresh();
    enterGame(player);
    toast('Drag clay onto water to begin', 'gold');
  } catch (err) {
    $('gate-note').textContent = err.message;
    button.disabled = false;
  }
});

function enterGame(player) {
  state.player = player;
  $('gate').hidden = true;
  $('game').hidden = false;
  $('resume-link').value = resumeLink(player);
  setInterval(poll, POLL_MS);
  setInterval(loadFeed, 20000);
  loadFeed();
  requestAnimationFrame(animate);
}

/* ----------------------------------------------------------------- state */

async function refresh() {
  const data = await api.state();
  state.data = data;
  state.itemsByKey = new Map(data.items.map((i) => [i.key, i]));
  state.coinRate = data.income_per_hour / 3600;
  state.lastPoll = performance.now();

  // Trust the server on a jump (a sale, an unlock); only interpolate forward.
  if (Math.abs(data.coins - state.displayCoins) > 2) state.displayCoins = data.coins;

  // The pad widens its chord as tiers unlock, so it has to know the tier even
  // when the player arrives part-way through a run.
  audio.setTier(data.ceiling);

  render();
  return data;
}

async function poll() {
  try { await refresh(); } catch { /* transient; the next poll will retry */ }
}

function animate() {
  if (state.data) {
    const elapsed = (performance.now() - state.lastPoll) / 1000;
    const projected = state.data.coins + state.coinRate * elapsed;
    if (projected > state.displayCoins) state.displayCoins = projected;
    $('coins').textContent = Math.floor(state.displayCoins).toLocaleString();

    // Advance the rings locally so they sweep smoothly rather than stepping.
    for (const place of state.data.yard) {
      const ring = document.querySelector(`.ring[data-id="${place.id}"]`);
      if (!ring) continue;
      const p = place.stalled
        ? place.progress / place.secs
        : Math.min(1, (place.progress + elapsed) / place.secs);
      ring.style.setProperty('--p', p.toFixed(3));
    }
  }
  requestAnimationFrame(animate);
}

/* ---------------------------------------------------------------- render */

function render() {
  const d = state.data;
  if (!d) return;

  $('who-name').textContent = d.name;
  $('income').textContent = Math.round(d.income_per_hour).toLocaleString();
  $('tier').textContent = d.ceiling;
  $('tier-max').textContent = `of ${d.max_tier}`;
  $('slots').textContent = `${d.yard_used}/${d.yard_slots}`;

  const unlock = $('unlock');
  if (d.next_tier_cost == null) {
    unlock.hidden = d.ceiling < d.max_tier;
    if (!unlock.hidden) {
      unlock.textContent = 'All tiers open';
      unlock.disabled = true;
    }
  } else {
    unlock.hidden = false;
    unlock.disabled = d.coins < d.next_tier_cost;
    unlock.textContent = `Unlock tier ${d.ceiling + 1} — ${d.next_tier_cost.toLocaleString()}`;
  }

  renderTraitFilters();
  renderShelf();
  renderYard();
  bench.refresh(state.itemsByKey);
}

function renderTraitFilters() {
  const host = $('trait-filters');
  const present = [...new Set(state.data.items.flatMap((i) => i.traits))].sort();
  if (host.dataset.sig === present.join(',')) return;   // avoid rebuilding on every poll
  host.dataset.sig = present.join(',');
  host.innerHTML = '';
  for (const trait of present) {
    const b = document.createElement('button');
    b.className = 'tfilter';
    b.textContent = trait;
    b.setAttribute('aria-pressed', state.traitFilter.has(trait));
    b.addEventListener('click', () => {
      if (state.traitFilter.has(trait)) state.traitFilter.delete(trait);
      else state.traitFilter.add(trait);
      b.setAttribute('aria-pressed', state.traitFilter.has(trait));
      renderShelf();
    });
    host.append(b);
  }
}

/**
 * Which shelf items could be automated right now -- i.e. you hold both
 * ingredients. A quiet nudge toward the next useful move, which matters once
 * the shelf is twenty items long and "what can I do" stops being obvious.
 */
function readyKeys() {
  const stockByBucket = new Map();
  for (const item of state.data.items) {
    if (item.held > 0) stockByBucket.set(item.bucket, true);
  }
  const ready = new Set();
  for (const item of state.data.items) {
    if (!item.automatable) continue;
    // The key encodes the two input buckets: `mud<clay+water`.
    const inputs = item.key.split('<')[1];
    if (!inputs) continue;
    const [a, b] = inputs.split('+');
    if (stockByBucket.get(a) && stockByBucket.get(b)) ready.add(item.key);
  }
  return ready;
}

function visibleItems() {
  const q = state.search.toLowerCase();
  return state.data.items.filter((i) => {
    if (q && !i.name.toLowerCase().includes(q)) return false;
    for (const t of state.traitFilter) if (!i.traits.includes(t)) return false;
    return true;
  });
}

let shelfRenderPending = false;

function renderShelf() {
  // Never rebuild mid-drag: replacing the card the pointer is holding detaches
  // it, so pointerup never fires and the drop is silently lost. Deferred until
  // the gesture ends, which is imperceptible.
  if (isDragging()) { shelfRenderPending = true; return; }
  shelfRenderPending = false;

  const host = $('shelf');
  host.innerHTML = '';
  const items = visibleItems();
  if (!items.length) {
    host.innerHTML = '<p class="yard-empty">Nothing matches.</p>';
    return;
  }

  // Best first: highest tier, then most held. The thing you just made is
  // usually the thing you want next.
  items.sort((a, b) => b.tier - a.tier || b.held - a.held || a.name.localeCompare(b.name));

  const ready = readyKeys();

  for (const item of items) {
    const card = document.createElement('div');
    const grew = (state.lastHeld.get(item.key) ?? item.held) < item.held;
    card.className = [
      'item',
      item.held ? '' : 'out-of-stock',
      state.freshKeys.has(item.key) ? 'fresh' : '',
      ready.has(item.key) ? 'ready' : '',
    ].filter(Boolean).join(' ');
    card.style.setProperty('--tier-color', tierColor(item.tier));
    card.setAttribute('role', 'listitem');
    card.title = item.flavor || '';

    card.innerHTML = `
      <span class="item-emoji"></span>
      <span class="item-body">
        <span class="item-name"></span>
        <span class="item-sub">
          <span class="chip">T${item.tier}</span>
          <span class="traits"></span>
        </span>
      </span>
      <span class="item-held"></span>`;
    card.querySelector('.item-emoji').textContent = item.emoji || '?';
    card.querySelector('.item-name').textContent = item.name;
    card.querySelector('.traits').textContent = item.traits.join(' · ');
    const heldEl = card.querySelector('.item-held');
    heldEl.textContent = item.held ? `×${item.held}` : '—';
    if (grew) heldEl.classList.add('tick');

    const actions = document.createElement('span');
    actions.className = 'place-actions';

    if (item.held > 0) {
      actions.append(button('Sell', `Sell all ${item.held} for ${item.held * item.sells_for}`,
        async (e) => {
          e.stopPropagation();
          const res = await guard(() => api.sellAll(item.key));
          if (res) {
            const at = centerOf(card);
            floatNumber(at.x, at.y, `+${res.coins}`);
            audio.sale(res.coins);
            await refresh();
          }
        }));
    }
    if (item.produces) {
      actions.append(button('Build', `Place a ${item.produces} — ${item.produce_cost}`,
        async (e) => {
          e.stopPropagation();
          const res = await guard(() => api.placeProducer(item.key, false));
          if (res) { audio.place(); toast(`${item.produces} built`); await refresh(); }
        }));
    }
    if (item.automatable) {
      actions.append(button('Auto', `Automate this recipe — ${item.factory_cost}`,
        async (e) => {
          e.stopPropagation();
          await automate(item);
        }));
    }
    if (actions.children.length) card.append(actions);

    if (item.held > 0) {
      dragFromShelf(card, item, bench, (payload, at) => bench.add(payload, at));
    } else {
      card.style.cursor = 'not-allowed';
      card.title = 'None in stock — produce or craft more';
    }

    host.append(card);
  }

  state.lastHeld = new Map(items.map((i) => [i.key, i.held]));
  // One flash per discovery, not one per poll.
  state.freshKeys.clear();
}

function button(label, title, onClick) {
  const b = document.createElement('button');
  b.className = 'toggle';
  b.textContent = label;
  b.title = title;
  b.addEventListener('pointerdown', (e) => e.stopPropagation());   // don't start a drag
  b.addEventListener('click', onClick);
  return b;
}

function renderYard() {
  const host = $('yard');
  host.innerHTML = '';
  const yard = state.data.yard;
  if (!yard.length) {
    host.innerHTML = '<p class="yard-empty">Nothing running. Build a producer from the shelf.</p>';
    return;
  }

  for (const place of yard) {
    const row = document.createElement('div');
    row.className = `place${place.stalled ? ' stalled' : ''}`;

    const ring = document.createElement('div');
    ring.className = `ring${place.kind === 'producer' ? ' clickable' : ''}`;
    ring.dataset.id = place.id;
    ring.style.setProperty('--p', (place.progress / place.secs).toFixed(3));
    ring.innerHTML = '<span></span>';
    ring.querySelector('span').textContent = place.output_emoji || '⚙';
    if (place.kind === 'producer') {
      ring.title = 'Click to hand-gather';
      ring.addEventListener('click', () => handGather(place, ring));
    }

    const body = document.createElement('div');
    body.className = 'place-body';
    const name = document.createElement('div');
    name.className = 'place-name';
    name.textContent = place.kind === 'producer' ? place.label : `→ ${place.output_name}`;
    const sub = document.createElement('div');
    sub.className = 'place-sub';
    sub.textContent = `${place.output_name} every ${place.secs}s`;
    if (place.stalled) {
      const warn = document.createElement('span');
      warn.className = 'stall';
      warn.textContent = ' — out of ingredients';
      sub.append(warn);
    }
    body.append(name, sub);

    const actions = document.createElement('div');
    actions.className = 'place-actions';
    const sell = document.createElement('button');
    sell.className = 'toggle';
    sell.textContent = 'Sell';
    sell.title = 'Sell output automatically instead of stocking it';
    sell.setAttribute('aria-pressed', place.autosell);
    sell.addEventListener('click', async () => {
      await guard(() => api.autosell(place.id, !place.autosell));
      await refresh();
    });

    const remove = document.createElement('button');
    remove.className = 'toggle';
    remove.textContent = '✕';
    remove.title = 'Remove — half your coins back';
    remove.addEventListener('click', async () => {
      const res = await guard(() => api.remove(place.id));
      if (res) { toast(`Removed, +${res.refund}`); await refresh(); }
    });

    actions.append(sell, remove);
    row.append(ring, body, actions);
    host.append(row);
  }
}

async function loadFeed() {
  try {
    const { feed } = await api.feed();
    const host = $('feed');
    host.innerHTML = '';
    if (!feed.length) {
      host.innerHTML = '<p class="feed-empty">Nothing discovered yet. Be first.</p>';
      return;
    }
    for (const row of feed) {
      const el = document.createElement('div');
      el.className = 'feed-row';
      el.innerHTML = '<span></span><span class="who"></span>';
      el.children[0].textContent = `${row.emoji} `;
      const who = el.children[1];
      who.innerHTML = '<b></b> found <b></b>';
      who.children[0].textContent = row.by || 'someone';
      who.children[1].textContent = row.name;
      host.append(el);
    }
  } catch { /* the feed is decoration; never let it break the game */ }
}

/* --------------------------------------------------------------- actions */

/** Run a call, turn any failure into a toast, and return null on failure. */
async function guard(fn) {
  try {
    return await fn();
  } catch (err) {
    const message = err instanceof ApiError ? err.message : 'Something went wrong';
    toast(message, 'bad');
    return null;
  }
}

async function onCombine(a, b, at) {
  const msg = $('bench-msg');
  msg.className = 'bench-msg';
  msg.textContent = '…';

  let res;
  try {
    res = await api.craft(a.item.key, b.item.key);
  } catch (err) {
    msg.className = 'bench-msg bad';
    msg.textContent = err instanceof ApiError ? err.message : 'Could not craft that';
    bench.reject(a, b, at);
    return;
  }

  if (res.dud) {
    // Free and instant -- no coins, no row. The reason is shown so the player
    // learns the system instead of just losing a click.
    msg.className = 'bench-msg warn';
    msg.textContent = res.reason;
    audio.dud();
    bench.reject(a, b, at);
    return;
  }

  msg.textContent = `−${res.cost} · ${res.item.name}`;
  audio.discovery(res.item.tier, res.first_in_world);
  bench.consume(a, b, res.item, at);

  if (res.new_to_you) {
    state.freshKeys.add(res.item.key);
    showReveal(res.item, res.first_in_world);
    if (res.first_in_world) { shake(7); burst(at.x, at.y, { color: '#e8b04b', count: 44, power: 8 }); }
  }
  await refresh();
}

async function handGather(place, ring) {
  ring.classList.remove('pop');
  void ring.offsetWidth;
  ring.classList.add('pop');
  const res = await guard(() => api.gather(place.id));
  if (res) { audio.gather(); await refresh(); }
}

async function automate(item) {
  const res = await guard(() => api.placeFactory(item.key, true));
  if (res) {
    audio.place();
    toast(`Automated ${item.name} — selling output`, 'gold');
    await refresh();
  }
}

$('unlock').addEventListener('click', async () => {
  const res = await guard(() => api.unlock());
  if (!res) return;
  audio.unlockTier(res.ceiling);
  shake(9);
  const at = centerOf($('unlock'));
  burst(at.x, at.y, { color: '#e8b04b', count: 50, power: 9 });
  toast(`Tier ${res.ceiling} open — try your old combinations again`, 'gold');
  await refresh();
});

/* ---------------------------------------------------------------- chrome */

function wireChrome() {
  onDragEnd(() => { if (shelfRenderPending) renderShelf(); });

  // Browsers refuse to start audio before a gesture, so the context is created
  // on the first interaction rather than at load. `once` because after that the
  // context exists and unlock() is a no-op.
  for (const event of ['pointerdown', 'keydown']) {
    document.addEventListener(event, () => audio.unlock(), { once: true });
  }

  const soundBtn = $('sound');
  const paintSound = () => {
    const on = !audio.isMuted();
    soundBtn.setAttribute('aria-pressed', String(on));
    soundBtn.textContent = on ? '\u266a' : '\u2715';
    soundBtn.title = on ? 'Sound on \u2014 click to mute' : 'Muted \u2014 click for sound';
  };
  paintSound();
  soundBtn.addEventListener('click', () => {
    audio.unlock();
    audio.setMuted(!audio.isMuted());
    paintSound();
  });

  $('search').addEventListener('input', (e) => {
    state.search = e.target.value;
    renderShelf();
  });
  $('clear-bench').addEventListener('click', () => bench.clear());

  $('reveal-ok').addEventListener('click', () => { $('reveal').hidden = true; });
  $('reveal').addEventListener('click', (e) => {
    if (e.target === $('reveal')) $('reveal').hidden = true;
  });

  $('menu-btn').addEventListener('click', async () => {
    $('menu').hidden = false;
    try {
      const h = await api.health();
      $('build-note').textContent =
        `${h.buckets} items across ${h.tiers_available} tiers · ` +
        `names: ${h.llm === 'ready' ? 'live' : 'placeholder (no API key yet)'}`;
    } catch { /* the menu still works without it */ }
  });
  $('menu-close').addEventListener('click', () => { $('menu').hidden = true; });
  $('copy-link').addEventListener('click', async () => {
    const input = $('resume-link');
    try {
      await navigator.clipboard.writeText(input.value);
      toast('Link copied');
    } catch {
      input.select();                       // clipboard blocked; let them copy
      toast('Press ⌘C to copy');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    $('reveal').hidden = true;
    $('menu').hidden = true;
  });
}

function showReveal(item, firstInWorld) {
  const card = $('reveal-card');
  card.style.setProperty('--tier-color', tierColor(item.tier));
  const banner = $('reveal-banner');
  banner.className = `reveal-banner${firstInWorld ? ' first' : ''}`;
  banner.textContent = firstInWorld
    ? '✦ First in the world ✦'
    : `New to you · tier ${item.tier}`;
  $('reveal-emoji').textContent = item.emoji || '?';
  $('reveal-name').textContent = item.name;
  $('reveal-flavor').textContent = item.flavor || '';

  const traits = $('reveal-traits');
  traits.innerHTML = '';
  for (const t of item.traits) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = t;
    traits.append(chip);
  }
  $('reveal').hidden = false;
}

boot();
