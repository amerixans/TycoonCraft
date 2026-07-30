/* TycoonCraft — sound.
 *
 * Everything is synthesised at runtime with the Web Audio API. No files, no
 * library, nothing to download — the same choice Poggle and Snowline make, and
 * on a 961 MB droplet shared with every other app it keeps the image small and
 * the first frame instant.
 *
 * The music is generative rather than a loop, for a specific reason: this is an
 * idle game, so the tab stays open for hours. A loop that is pleasant for three
 * minutes is unbearable for two hours — you start hearing the seam. So instead
 * there is a slow pad over a four-chord cycle with a long, sparse bell line on
 * top, and none of it is quantised tightly enough to form a hook that sticks.
 *
 * **The chord set widens as you unlock tiers.** Tier 1 is a bare open fifth:
 * industrial, unresolved, a bit bleak. By tier 6 it is a major ninth. So the
 * music brightens as you get richer, which is the whole arc of the game
 * expressed in the one channel that does not need any screen space.
 *
 * The discovery sound borrows Poggle's trick outright, because it works: each
 * consecutive discovery steps up a major pentatonic scale, so a run of finds
 * plays a rising phrase. Pentatonic because every interval in it is consonant,
 * so a lucky eight-discovery streak cannot land on a sour note.
 */

const STORAGE_KEY = 'tycooncraft.muted';

let ctx = null;
let master = null;
let musicBus = null;      // pad + bells, duckable and separately mutable
let sfxBus = null;
let started = false;
let musicTimer = null;
let chordIndex = 0;
let tier = 1;
let streak = 0;
let lastDiscoveryAt = 0;

let muted = (() => {
  try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
})();

/* ------------------------------------------------------------------ theory */

const ROOT = 110;                                    // A2

// Major pentatonic in semitones, extended over three octaves. Used for the
// discovery run and the bell line.
const PENT = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24, 26, 28, 31, 33];

// The pad's chord, per unlocked tier. Deliberately a widening sequence: bare
// fifth -> minor seventh -> minor ninth -> major seventh -> ninth -> major
// ninth. Getting richer sounds like getting richer.
const CHORDS = {
  1: [0, 7, 12],
  2: [0, 3, 7, 10],
  3: [0, 3, 7, 14],
  4: [0, 4, 7, 11],
  5: [0, 4, 7, 11, 14],
  6: [0, 4, 7, 11, 18],
};

// Where the root walks. Four bars, minor-ish, resolving back — slow enough
// (~13s a chord) that it reads as weather rather than as a progression.
const ROOT_WALK = [0, -3, 2, -5];
const CHORD_SECS = 13;

// Two oscillators per chord tone, a few cents either side of true. This is the
// difference between a thin synth tone and one with any body to it.
const DETUNE_CENTS = [-7, 7];

const semitone = (n) => ROOT * Math.pow(2, n / 12);

/* -------------------------------------------------------------------- init */

/** Browsers refuse to start audio before a gesture, so this is called from the
 *  first click or keypress rather than at load. Calling it again is free. */
export function unlock() {
  if (ctx) {
    if (ctx.state === 'suspended') ctx.resume();
    return;
  }
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;                                   // no audio here; game plays on

  ctx = new AC();

  master = ctx.createGain();
  master.gain.value = muted ? 0 : 0.9;
  master.connect(ctx.destination);

  musicBus = ctx.createGain();
  musicBus.gain.value = 0.16;                        // the pad sits well under the SFX
  musicBus.connect(master);

  sfxBus = ctx.createGain();
  sfxBus.gain.value = 0.5;
  sfxBus.connect(master);

  startMusic();
}

export function isMuted() { return muted; }

export function setMuted(value) {
  muted = value;
  try { localStorage.setItem(STORAGE_KEY, value ? '1' : '0'); } catch { /* ignore */ }
  if (!master) return;
  // Ramp rather than jump: a hard gain change on a running pad clicks.
  master.gain.cancelScheduledValues(ctx.currentTime);
  master.gain.linearRampToValueAtTime(value ? 0 : 0.9, ctx.currentTime + 0.25);
}

export function setTier(value) {
  tier = Math.max(1, Math.min(6, value | 0));
}

/* ------------------------------------------------------------------- music */

function startMusic() {
  if (started || !ctx) return;
  started = true;
  scheduleChord();
  // One chord at a time, scheduled just ahead. Simpler than a lookahead
  // scheduler and accurate enough for something moving this slowly.
  musicTimer = setInterval(scheduleChord, CHORD_SECS * 1000);
}

function scheduleChord() {
  if (!ctx || ctx.state !== 'running') return;

  const now = ctx.currentTime;
  const walk = ROOT_WALK[chordIndex % ROOT_WALK.length];
  chordIndex += 1;

  const chord = CHORDS[tier] || CHORDS[1];

  for (const [voice, interval] of chord.entries()) {
    // Two oscillators per note, detuned a few cents apart, which is what turns
    // a thin synth tone into something with body.
    for (const detune of DETUNE_CENTS) {
      const osc = ctx.createOscillator();
      osc.type = 'sawtooth';
      osc.frequency.value = semitone(walk + interval);
      osc.detune.value = detune;

      const filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      // Higher notes get opened up slightly less, so the chord does not turn
      // buzzy at the top.
      filter.frequency.value = 420 - voice * 30;
      filter.Q.value = 0.7;

      // A slow swell. Long attack and release so consecutive chords overlap
      // and there is never a gap or a seam.
      const gain = ctx.createGain();
      const peak = 0.30 / chord.length;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(peak, now + 4.5);
      gain.gain.linearRampToValueAtTime(peak * 0.75, now + CHORD_SECS * 0.7);
      gain.gain.linearRampToValueAtTime(0.0001, now + CHORD_SECS + 3.5);

      osc.connect(filter);
      filter.connect(gain);
      gain.connect(musicBus);
      osc.start(now);
      osc.stop(now + CHORD_SECS + 4);
    }
  }

  // A sparse bell line: two or three notes per chord, placed off the beat so
  // nothing lines up into a rhythm you could tap along to.
  const bells = 2 + (chordIndex % 2);
  for (let i = 0; i < bells; i++) {
    const at = now + 1.5 + Math.random() * (CHORD_SECS - 3);
    const step = PENT[4 + Math.floor(Math.random() * 7)];
    bell(at, semitone(walk + step + 12), 0.05 + Math.random() * 0.04);
  }
}

function bell(at, freq, level) {
  const osc = ctx.createOscillator();
  osc.type = 'triangle';
  osc.frequency.value = freq;

  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(level, at + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + 2.4);

  osc.connect(gain);
  gain.connect(musicBus);
  osc.start(at);
  osc.stop(at + 2.5);
}

/* --------------------------------------------------------------------- sfx */

/** A short filtered-noise transient. This is what makes a hit read as physical
 *  rather than as a beep -- the same observation Poggle's peg sound rests on. */
function transient(at, level, freq = 2400) {
  const length = Math.ceil(ctx.sampleRate * 0.02);
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / length);   // decaying, so a click
  }
  const src = ctx.createBufferSource();
  src.buffer = buffer;

  const bp = ctx.createBiquadFilter();
  bp.type = 'bandpass';
  bp.frequency.value = freq;
  bp.Q.value = 0.9;

  const gain = ctx.createGain();
  gain.gain.value = level;

  src.connect(bp); bp.connect(gain); gain.connect(sfxBus);
  src.start(at);
}

function pluck(at, freq, { type = 'triangle', decay = 0.28, level = 0.3, bend = 0 } = {}) {
  const osc = ctx.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, at);
  if (bend) osc.frequency.exponentialRampToValueAtTime(freq * Math.pow(2, bend / 12), at + decay);

  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(level, at + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + decay);

  osc.connect(gain);
  gain.connect(sfxBus);
  osc.start(at);
  osc.stop(at + decay + 0.05);
}

/**
 * A discovery. Steps up a pentatonic scale for each consecutive find, so a run
 * plays a rising phrase instead of the same note eight times.
 *
 * `resultTier` voices it: higher tiers get a fifth stacked on top, so you can
 * hear that you made something good without looking at the card.
 */
export function discovery(resultTier = 2, firstInWorld = false) {
  if (!ctx || ctx.state !== 'running') return;
  const now = ctx.currentTime;

  // The streak lapses if you wander off, so coming back does not start you
  // three octaves up.
  if (now - lastDiscoveryAt > 20) streak = 0;
  lastDiscoveryAt = now;

  const step = PENT[Math.min(streak, PENT.length - 1)];
  streak += 1;

  transient(now, 0.22);
  pluck(now, semitone(24 + step), { decay: 0.3, level: 0.32 });

  // From the third in a row a quiet fifth joins on top, and later hits ease off
  // in level, so a long run swells rather than turning into a wall.
  if (streak >= 3) {
    pluck(now + 0.012, semitone(24 + step + 7), {
      decay: 0.26, level: 0.14 * Math.max(0.4, 1 - streak * 0.05),
    });
  }
  if (resultTier >= 3) {
    pluck(now + 0.05, semitone(36 + step), { type: 'sine', decay: 0.5, level: 0.1 });
  }

  if (firstInWorld) fanfare(now + 0.1);
}

/** World-first: a short rising arpeggio. Rare enough to be worth the emphasis. */
function fanfare(at) {
  [0, 4, 7, 12].forEach((step, i) => {
    pluck(at + i * 0.075, semitone(24 + step), {
      type: 'triangle', decay: 0.55, level: 0.2,
    });
  });
}

/** A dud. Dull, unpitched, brief -- "nothing happened", not "you failed".
 *  It also breaks the streak, which is the point. */
export function dud() {
  if (!ctx || ctx.state !== 'running') return;
  streak = 0;
  const now = ctx.currentTime;
  transient(now, 0.1, 500);
  pluck(now, semitone(3), { type: 'sine', decay: 0.16, level: 0.14, bend: -3 });
}

/** Coins in. Scales very slightly with size so a big sale sounds bigger. */
export function sale(amount = 1) {
  if (!ctx || ctx.state !== 'running') return;
  const now = ctx.currentTime;
  const level = Math.min(0.26, 0.1 + Math.log10(1 + amount) * 0.05);
  transient(now, 0.08, 5200);
  pluck(now, semitone(31), { type: 'sine', decay: 0.2, level });
  pluck(now + 0.045, semitone(36), { type: 'sine', decay: 0.26, level: level * 0.7 });
}

/** Hand-gathering. Quiet and dry: it happens a lot, so it must not nag. */
export function gather() {
  if (!ctx || ctx.state !== 'running') return;
  transient(ctx.currentTime, 0.07, 1500);
}

/** A placement lands. A low mechanical thunk. */
export function place() {
  if (!ctx || ctx.state !== 'running') return;
  const now = ctx.currentTime;
  transient(now, 0.16, 900);
  pluck(now, semitone(-12), { type: 'square', decay: 0.22, level: 0.16 });
}

/** Tier unlock: the big one. A swell plus a rising run, and the pad
 *  immediately picks up the wider chord on its next change. */
export function unlockTier(newTier) {
  if (!ctx || ctx.state !== 'running') return;
  setTier(newTier);
  const now = ctx.currentTime;

  // A short noise swell underneath, like a furnace catching.
  const length = Math.ceil(ctx.sampleRate * 1.1);
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i++) {
    const t = i / length;
    data[i] = (Math.random() * 2 - 1) * Math.sin(Math.PI * t) * 0.5;
  }
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  const lp = ctx.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.setValueAtTime(300, now);
  lp.frequency.linearRampToValueAtTime(2600, now + 0.9);
  const swell = ctx.createGain();
  swell.gain.value = 0.13;
  src.connect(lp); lp.connect(swell); swell.connect(sfxBus);
  src.start(now);

  [0, 4, 7, 12, 16, 19].forEach((step, i) => {
    pluck(now + 0.16 + i * 0.09, semitone(24 + step), {
      type: 'triangle', decay: 0.7, level: 0.22,
    });
  });

  // Force the pad onto the new chord now rather than waiting up to 13 seconds,
  // so the brightening lands with the moment.
  scheduleChord();
}

export function resetStreak() { streak = 0; }

/** Exposed only for `tests/audio.test.mjs`, which drives the pad under a stubbed
 *  AudioContext -- every mistake this module can make is silent, and you cannot
 *  hear a screenshot. */
export function _scheduleChordForTest() { scheduleChord(); }
