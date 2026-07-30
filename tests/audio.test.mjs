/* Exercise public/src/audio.js under a stubbed Web Audio API.
 *
 *   node tests/audio.test.mjs
 *
 * Audio is the one part of the frontend with real arithmetic in it, and every
 * mistake it can make is silent: `exponentialRampToValueAtTime(0, …)` throws,
 * a NaN frequency plays nothing, an un-stopped oscillator leaks until the tab
 * is closed. None of that shows up in a screenshot, and you cannot hear a
 * screenshot either.
 *
 * So: a fake AudioContext that records every node and every scheduled value,
 * then assertions about what a real one would have been asked to do.
 */

import assert from 'node:assert/strict';

/* ------------------------------------------------------------------- stub */

const created = { osc: 0, gain: 0, filter: 0, buffer: 0, source: 0 };
const scheduled = [];       // every automation call, for range checking
let started = 0;
let stopped = 0;

function param(name, value = 0) {
  const record = (method, target, when) => {
    scheduled.push({ name, method, target, when });
    // A real AudioParam throws on a non-finite value; the stub should too, or
    // the test would happily pass on NaN.
    assert.ok(Number.isFinite(target), `${name}.${method} got a non-finite value: ${target}`);
    assert.ok(Number.isFinite(when), `${name}.${method} got a non-finite time: ${when}`);
  };
  return {
    value,
    setValueAtTime: (v, t) => record('setValueAtTime', v, t),
    linearRampToValueAtTime: (v, t) => record('linearRampToValueAtTime', v, t),
    exponentialRampToValueAtTime: (v, t) => {
      // This is the real constraint that bites: a zero or negative target on an
      // exponential ramp raises RangeError in every browser.
      assert.ok(v > 0, `exponentialRampToValueAtTime target must be > 0, got ${v}`);
      record('exponentialRampToValueAtTime', v, t);
    },
    cancelScheduledValues: (t) => record('cancelScheduledValues', 0, t),
  };
}

class FakeContext {
  constructor() {
    this.state = 'running';
    this.sampleRate = 48000;
    this._t = 0;
    this.destination = { connect() {} };
  }
  get currentTime() { return this._t; }
  advance(seconds) { this._t += seconds; }

  createGain() {
    created.gain++;
    return { gain: param('gain', 1), connect() {} };
  }
  createOscillator() {
    created.osc++;
    return {
      type: 'sine',
      frequency: param('frequency', 440),
      detune: param('detune', 0),
      connect() {},
      start(t) { started++; assert.ok(Number.isFinite(t), 'osc.start got a bad time'); },
      stop(t) { stopped++; assert.ok(Number.isFinite(t), 'osc.stop got a bad time'); },
    };
  }
  createBiquadFilter() {
    created.filter++;
    return { type: 'lowpass', frequency: param('filter.frequency', 350), Q: param('Q', 1), connect() {} };
  }
  createBuffer(channels, length) {
    created.buffer++;
    assert.ok(length > 0, 'createBuffer got a non-positive length');
    const data = new Float32Array(length);
    return { getChannelData: () => data, length };
  }
  createBufferSource() {
    created.source++;
    return {
      buffer: null,
      connect() {},
      start(t) { started++; assert.ok(Number.isFinite(t), 'source.start got a bad time'); },
    };
  }
  resume() { this.state = 'running'; }
}

const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
};
globalThis.window = { AudioContext: FakeContext };

/* -------------------------------------------------------------------- run */

const audio = await import('../public/src/audio.js');

let failures = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`  ok   ${name}`);
  } catch (err) {
    failures++;
    console.log(`  FAIL ${name}\n         ${err.message}`);
  }
}

console.log('\naudio.js');

test('nothing throws before unlock, and nothing is created', () => {
  audio.discovery(2, true);
  audio.dud();
  audio.sale(100);
  audio.gather();
  audio.place();
  audio.unlockTier(3);
  assert.equal(created.osc, 0, 'created nodes without a context');
});

test('unlock builds a context and starts the pad', () => {
  audio.unlock();
  assert.ok(created.osc > 0, 'the pad created no oscillators');
  assert.ok(created.gain >= 3, 'expected master, music and sfx buses');
  assert.equal(started, stopped, 'every oscillator must be stopped, or it leaks');
});

test('unlock is idempotent', () => {
  const before = created.osc;
  audio.unlock();
  assert.equal(created.osc, before, 'a second unlock built a second graph');
});

test('a tier-1 chord is sparser than a tier-6 chord', () => {
  // Chord width is the whole "the music brightens as you get richer" idea, so
  // it is worth asserting rather than trusting.
  const count = () => {
    const before = created.osc;
    audio._scheduleChordForTest();
    return created.osc - before;
  };
  audio.setTier(1);
  const thin = count();
  audio.setTier(6);
  const wide = count();
  assert.ok(wide > thin, `tier 6 (${wide}) should use more voices than tier 1 (${thin})`);
});

test('a discovery run climbs and then plateaus safely', () => {
  audio.resetStreak();
  const freqs = [];
  const seen = scheduled.length;
  for (let i = 0; i < 30; i++) audio.discovery(2, false);
  for (const s of scheduled.slice(seen)) {
    if (s.name === 'frequency' && s.method === 'setValueAtTime') freqs.push(s.target);
  }
  assert.ok(freqs.length >= 30, 'expected a note per discovery');
  // Climbs at first...
  assert.ok(freqs[3] > freqs[0], 'the run should rise');
  // ...and never runs off the end of the scale into a NaN or a dog whistle.
  assert.ok(Math.max(...freqs) < 20000, `a note reached ${Math.max(...freqs)} Hz`);
});

test('a dud breaks the streak', () => {
  audio.resetStreak();
  audio.discovery(2, false);
  audio.discovery(2, false);
  audio.discovery(2, false);
  const beforeDud = scheduled.filter((s) => s.name === 'frequency').at(-1).target;
  audio.dud();
  audio.discovery(2, false);
  const afterDud = scheduled.filter((s) => s.name === 'frequency').at(-1).target;
  assert.ok(afterDud < beforeDud, 'a dud should reset the run to the bottom of the scale');
});

test('every sound effect runs clean', () => {
  audio.resetStreak();
  for (const call of [
    () => audio.discovery(1, false),
    () => audio.discovery(6, true),
    () => audio.dud(),
    () => audio.sale(0),
    () => audio.sale(1),
    () => audio.sale(1_000_000),
    () => audio.gather(),
    () => audio.place(),
    () => audio.unlockTier(6),
  ]) call();
});

test('muting ramps rather than jumping, and persists', () => {
  audio.setMuted(true);
  assert.equal(audio.isMuted(), true);
  const ramps = scheduled.filter((s) => s.method === 'linearRampToValueAtTime');
  assert.ok(ramps.some((r) => r.target === 0), 'muting should ramp the master to zero');
  assert.equal(store.get('tycooncraft.muted'), '1', 'mute should be remembered');
  audio.setMuted(false);
  assert.equal(store.get('tycooncraft.muted'), '0');
});

test('no oscillator is left running', () => {
  assert.equal(started - created.source, stopped,
    `${started - created.source - stopped} oscillators were never stopped`);
});

test('setTier clamps to the authored range', () => {
  audio.setTier(0);
  audio.setTier(99);
  audio.setTier(-5);
  audio._scheduleChordForTest();       // must not throw on a clamped tier
});

console.log(
  `\n${failures ? `${failures} failed` : 'all passed'} ` +
  `(${created.osc} oscillators, ${created.gain} gains, ${scheduled.length} automation calls)\n`
);
process.exit(failures ? 1 : 0);
