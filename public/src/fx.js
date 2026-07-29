/* Juice: particles, toasts, floating numbers, screen shake.
 *
 * All of it is decorative -- nothing here carries information that is not also
 * in the DOM, which is what makes honouring `prefers-reduced-motion` a matter
 * of skipping work rather than degrading the game.
 *
 * One canvas, one requestAnimationFrame loop, and the loop stops itself when
 * there is nothing to draw. An idle game leaves a tab open for hours; a rAF
 * loop spinning on an empty particle array all afternoon is a real battery cost
 * for no benefit.
 */

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const canvas = document.getElementById('fx');
const ctx = canvas.getContext('2d');
const particles = [];
let running = false;
let dpr = 1;

function resize() {
  dpr = Math.min(window.devicePixelRatio || 1, 2);   // 3x on phones buys nothing
  canvas.width = Math.floor(innerWidth * dpr);
  canvas.height = Math.floor(innerHeight * dpr);
  canvas.style.width = `${innerWidth}px`;
  canvas.style.height = `${innerHeight}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
resize();
addEventListener('resize', resize);

const TIER_COLORS = ['#8b8377', '#8b8377', '#a8724a', '#cd7038', '#6d92b5', '#9d7bc0', '#e8b04b'];
export const tierColor = (tier) => TIER_COLORS[Math.max(0, Math.min(6, tier))];

function loop() {
  if (!particles.length) { running = false; return; }
  ctx.clearRect(0, 0, innerWidth, innerHeight);

  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.life -= 1 / 60;
    if (p.life <= 0) { particles.splice(i, 1); continue; }

    p.vy += p.gravity;
    p.vx *= 0.985;
    p.vy *= 0.985;
    p.x += p.vx;
    p.y += p.vy;

    const alpha = Math.min(1, p.life / p.fade);
    ctx.globalAlpha = alpha;

    if (p.text) {
      ctx.fillStyle = p.color;
      ctx.font = `600 ${p.size}px ui-monospace, Menlo, monospace`;
      ctx.textAlign = 'center';
      ctx.fillText(p.text, p.x, p.y);
    } else {
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * alpha, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
  requestAnimationFrame(loop);
}

function start() {
  if (!running) { running = true; requestAnimationFrame(loop); }
}

/** A burst of sparks. Used on a discovery, scaled up for a world first. */
export function burst(x, y, { color = '#cd7038', count = 26, power = 5 } = {}) {
  if (REDUCED) return;
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
    const speed = power * (0.45 + Math.random());
    particles.push({
      x, y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 1.2,
      size: 1.6 + Math.random() * 2.6,
      gravity: 0.14,
      life: 0.8 + Math.random() * 0.6,
      fade: 0.7,
      color,
    });
  }
  start();
}

/** A puff of smoke for a dud: grey, slow, downward. Reads as "nothing". */
export function puff(x, y) {
  if (REDUCED) return;
  for (let i = 0; i < 12; i++) {
    particles.push({
      x: x + (Math.random() - 0.5) * 18,
      y: y + (Math.random() - 0.5) * 10,
      vx: (Math.random() - 0.5) * 1.1,
      vy: -0.5 - Math.random() * 0.7,
      size: 3 + Math.random() * 5,
      gravity: -0.012,
      life: 0.7 + Math.random() * 0.4,
      fade: 0.9,
      color: 'rgba(150,136,122,0.5)',
    });
  }
  start();
}

/** A number that floats up and fades. The universal "you got paid" signal. */
export function floatNumber(x, y, text, color = '#e8b04b') {
  if (REDUCED) return;
  particles.push({
    x, y,
    vx: (Math.random() - 0.5) * 0.5,
    vy: -1.5,
    size: 15,
    gravity: 0.028,
    life: 1.1,
    fade: 1.0,
    color,
    text,
  });
  start();
}

export function shake(intensity = 6) {
  if (REDUCED) return;
  const game = document.getElementById('game');
  if (!game) return;
  const start = performance.now();
  const duration = 320;
  function frame(now) {
    const t = (now - start) / duration;
    if (t >= 1) { game.style.transform = ''; return; }
    const decay = intensity * (1 - t);
    game.style.transform =
      `translate(${(Math.random() - 0.5) * decay}px, ${(Math.random() - 0.5) * decay}px)`;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

const toastHost = document.getElementById('toasts');

export function toast(message, variant = '') {
  const el = document.createElement('div');
  el.className = `toast ${variant}`.trim();
  el.textContent = message;
  toastHost.append(el);
  setTimeout(() => {
    el.classList.add('out');
    // Wait for the exit animation, but not forever if it was skipped.
    setTimeout(() => el.remove(), 300);
  }, 2200);
}

/** Centre of an element in viewport coordinates -- where to originate effects. */
export function centerOf(el) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}
