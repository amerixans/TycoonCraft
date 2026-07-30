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
  revealItem: null,
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
    const grew = (state.lastHeld.get(item.key) ?? item.held) < item.held;
    const card = document.createElement('div');
    card.className = [
      'item',
      item.held ? 'draggable' : 'out-of-stock',
      state.freshKeys.has(item.key) ? 'fresh' : '',
      ready.has(item.key) ? 'ready' : '',
    ].filter(Boolean).join(' ');
    card.style.setProperty('--tier-color', tierColor(item.tier));
    card.setAttribute('role', 'listitem');

    card.innerHTML = `
      <span class="item-emoji"></span>
      <span class="item-body">
        <span class="item-name"></span>
        <span class="item-sub">
          <span class="chip">T${item.tier}</span>
          <span class="traits"></span>
        </span>
      </span>
      <span class="item-held"></span>
      <span class="item-actions"></span>`;
    // textContent, not interpolation: names come from a language model and flow
    // through the database, so they are never trusted as markup.
    card.querySelector('.item-emoji').textContent = item.emoji || '?';
    card.querySelector('.item-name').textContent = item.name;
    card.querySelector('.traits').textContent = item.traits.join(' \u00b7 ');
    card.title = item.flavor || '';

    const heldEl = card.querySelector('.item-held');
    heldEl.textContent = item.held ? `\u00d7${item.held}` : '\u2014';
    heldEl.classList.toggle('none', !item.held);
    if (grew) heldEl.classList.add('tick');

    card.querySelector('.item-actions').append(...itemActions(item, card));

    if (item.held > 0) {
      dragFromShelf(card, item, bench, (payload, at) => bench.add(payload, at));
    }
    host.append(card);
  }

  state.lastHeld = new Map(items.map((i) => [i.key, i.held]));
  // One flash per discovery, not one per poll.
  state.freshKeys.clear();
}

/**
 * The actions an item can have. Both are ALWAYS rendered when they are
 * conceptually applicable to the item, and DISABLED with a reason when you
 * cannot act right now.
 *
 * Hiding them was the mistake. A control you have never seen cannot be learned,
 * so the whole build/sell mechanic read as arbitrary -- buttons appeared and
 * vanished as stock moved. And there is only one "Build" now: placing a Clay Pit
 * and placing a factory that makes Mud are the same player action ("put a machine
 * in the yard that makes this"), and giving them two labels -- Build and Auto --
 * was most of the confusion.
 */
function itemActions(item, card) {
  const out = [];
  const coins = state.data.coins;

  // --- Sell -----------------------------------------------------------------
  const takings = item.held * item.sells_for;
  out.push(action({
    className: 'act act-sell',
    label: 'Sell',
    amount: item.held ? takings : null,
    disabled: item.held < 1,
    title: item.held
      ? `Sell all ${item.held} for ${takings} coins`
      : `Nothing to sell \u2014 you hold none. Each one is worth ${item.sells_for}.`,
    onClick: async () => {
      const res = await guard(() => api.sellAll(item.key));
      if (!res) return;
      const at = centerOf(card);
      floatNumber(at.x, at.y, `+${res.coins}`);
      audio.sale(res.coins);
      await refresh();
    },
  }));

  // --- Build ----------------------------------------------------------------
  // A producer takes precedence over a factory: for a Kiln the interesting
  // machine is the one that makes charcoal, not one that makes more Kilns.
  const asProducer = Boolean(item.produces);
  if (asProducer || item.automatable) {
    const cost = asProducer ? item.produce_cost : item.factory_cost;
    const full = state.data.yard_used >= state.data.yard_slots;
    const broke = coins < cost;

    let why;
    if (full) {
      why = `Your yard is full (${state.data.yard_slots} slots). Remove something, `
          + `or unlock the next tier for more room.`;
    } else if (broke) {
      why = `Costs ${cost} coins \u2014 you have ${Math.floor(coins)}.`;
    } else if (asProducer) {
      why = `Build a ${item.produces}: makes ${item.name} on its own, forever.`;
    } else {
      why = `Build a machine that makes ${item.name} automatically, `
          + `consuming its ingredients from your stock.`;
    }

    out.push(action({
      className: 'act act-build',
      label: 'Build',
      amount: cost,
      disabled: full || broke,
      title: why,
      onClick: () => build(item),
    }));
  }

  return out;
}

function action({ className, label, amount, disabled, title, onClick }) {
  const b = document.createElement('button');
  b.className = className;
  b.disabled = Boolean(disabled);
  b.title = title;
  b.innerHTML = '<span></span><span class="n"></span>';
  b.children[0].textContent = label;
  // A zero cost renders as "Build 0", which reads like a bug rather than like
  // "free". Show nothing instead.
  b.children[1].textContent = (amount == null || amount === 0) ? '' : amount.toLocaleString();
  // A button press must not start a card drag.
  b.addEventListener('pointerdown', (e) => e.stopPropagation());
  b.addEventListener('click', (e) => { e.stopPropagation(); onClick(); });
  return b;
}

/** One verb for "put a machine in the yard that makes this". */
async function build(item) {
  const res = item.produces
    ? await guard(() => api.placeProducer(item.key, false))
    : await guard(() => api.placeFactory(item.key, true));
  if (!res) return;
  audio.place();
  toast(item.produces
    ? `${item.produces} built \u2014 making ${item.name}`
    : `Now making ${item.name} automatically, and selling it`, 'gold');
  await refresh();
}


function renderYard() {
  const host = $('yard');
  host.innerHTML = '';
  const yard = state.data.yard;
  if (!yard.length) {
    // An empty state that says what to do, not just that nothing is here.
    host.innerHTML =
      '<p class="yard-empty">Nothing running yet.<br><br>'
      + 'Press <b>Build</b> on any item in your shelf to put a machine here. '
      + 'Machines keep making things while you are away \u2014 that is where the '
      + 'money comes from.</p>';
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
    ring.querySelector('span').textContent = place.output_emoji || '\u2699';
    if (place.kind === 'producer') {
      ring.title = 'Click to hurry it along by hand';
      ring.addEventListener('click', () => handGather(place, ring));
    }

    const body = document.createElement('div');
    body.className = 'place-body';

    const name = document.createElement('div');
    name.className = 'place-name';
    // Say what it MAKES, which is what the player cares about. The machine's own
    // name is secondary and goes in the line below.
    name.textContent = place.output_name;

    const sub = document.createElement('div');
    sub.className = 'place-sub';
    const per = place.secs >= 60
      ? `${(place.secs / 60).toFixed(1)} min`
      : `${place.secs}s`;
    const what = place.kind === 'producer' ? place.label : 'Factory';
    sub.textContent = `${what} \u00b7 one every ${per}`;

    // What it is worth per hour. The actual question you ask of a machine, and
    // the row had a wide empty gap to put the answer in.
    const unit = state.itemsByKey.get(place.output)?.sells_for;
    if (unit) {
      const rate = document.createElement('span');
      rate.className = 'place-rate';
      const perHour = Math.round((3600 / place.secs) * unit);
      rate.textContent = ` \u00b7 ${unit} each, ${perHour.toLocaleString()}/hr`;
      rate.title = place.autosell
        ? 'Being sold automatically, so this is real income'
        : 'Stocking to your shelf. Turn on Auto-sell to earn this.';
      sub.append(rate);
    }

    if (place.kind === 'factory' && place.inputs.length) {
      const needs = document.createElement('span');
      needs.className = 'needs';
      const names = place.inputs
        .map((k) => state.itemsByKey.get(k)?.name || k)
        .join(' + ');
      needs.textContent = ` \u00b7 needs ${names}`;
      sub.append(needs);
    }
    if (place.stalled) {
      const warn = document.createElement('span');
      warn.className = 'stall';
      warn.textContent = ' \u00b7 out of ingredients';
      sub.append(warn);
    }
    body.append(name, sub);

    const actions = document.createElement('div');
    actions.className = 'place-actions';

    const sell = document.createElement('button');
    sell.className = 'autosell';
    sell.textContent = 'Auto-sell';
    sell.setAttribute('aria-pressed', String(place.autosell));
    sell.title = place.autosell
      ? 'Selling the output as it is made. Click to stock it instead.'
      : 'Adding the output to your shelf. Click to sell it automatically instead.';
    sell.addEventListener('click', async () => {
      await guard(() => api.autosell(place.id, !place.autosell));
      await refresh();
    });

    const remove = document.createElement('button');
    remove.className = 'place-remove';
    remove.textContent = '\u2715';
    remove.title = 'Remove this machine \u2014 half your coins back';
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
  $('reveal-build').addEventListener('click', async () => {
    $('reveal').hidden = true;
    if (state.revealItem) await build(state.revealItem);
  });
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

  // Offer to industrialise it on the spot. Discovering something and then
  // immediately automating it is the whole loop in one gesture, and it teaches
  // what Build means at the moment the player is most receptive to learning it.
  state.revealItem = item;
  const buildBtn = $('reveal-build');
  const canBuild = Boolean(item.produces || item.automatable);
  const cost = item.produces ? item.produce_cost : item.factory_cost;
  const room = state.data && state.data.yard_used < state.data.yard_slots;
  const affordable = state.data && state.data.coins >= cost;
  buildBtn.hidden = !canBuild;
  if (canBuild) {
    buildBtn.disabled = !room || !affordable;
    buildBtn.textContent = affordable
      ? `Build one \u2014 ${cost.toLocaleString()}`
      : `Build one (need ${cost.toLocaleString()})`;
    if (!room) buildBtn.textContent = 'Yard is full';
  }
  $('reveal-ok').textContent = canBuild ? 'Later' : 'Good';

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
