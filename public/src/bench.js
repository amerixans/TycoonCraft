/* The workbench: an open surface you drag things onto, then drag one thing onto
 * another to combine them.
 *
 * v1 had two labelled slots and a "Craft Now!" button, which is a form, not a
 * toy -- and it displayed the item's *name as text* in each slot, so the
 * generated art never even appeared while you were crafting. The tactile
 * pleasure of pushing two objects together is most of this genre's appeal, so
 * it gets the middle of the screen.
 *
 * Pointer Events throughout rather than HTML5 drag-and-drop: HTML5 DnD has no
 * usable touch story, and this has to work on a phone.
 */

import { burst, centerOf, puff, tierColor } from './fx.js';

const OVERLAP_PX = 46;   // how close two cards must be to count as a drop

/* Is a drag in flight?
 *
 * The shelf re-renders on every poll, and a full rebuild removes the card the
 * pointer is currently holding -- which silently kills the drag: pointerup
 * never fires on a detached node, so the ghost is stranded on screen and the
 * drop is lost. Renderers check this and defer. Found by dragging two items in
 * a row and watching the second one fail whenever a poll landed mid-gesture.
 */
let dragging = false;
const dragEndListeners = new Set();

export const isDragging = () => dragging;

export function onDragEnd(fn) { dragEndListeners.add(fn); }

function setDragging(value) {
  if (dragging === value) return;
  dragging = value;
  if (!value) for (const fn of dragEndListeners) fn();
}

export class Bench {
  /**
   * @param {HTMLElement} host   the bench surface
   * @param {(a, b, at) => void} onCombine  called with two item payloads
   */
  constructor(host, onCombine) {
    this.host = host;
    this.onCombine = onCombine;
    this.entries = [];
    this.nextUid = 1;
    this.busy = false;
  }

  get count() { return this.entries.length; }

  /** Put an item on the bench. `at` is in viewport coordinates. */
  add(item, at) {
    const rect = this.host.getBoundingClientRect();
    const x = at ? at.x - rect.left : rect.width * (0.25 + Math.random() * 0.5);
    const y = at ? at.y - rect.top : rect.height * (0.3 + Math.random() * 0.4);

    const el = document.createElement('div');
    el.className = 'bench-item born';
    el.style.setProperty('--tier-color', tierColor(item.tier));
    el.innerHTML = `
      <span class="item-emoji"></span>
      <span class="item-name"></span>`;
    // textContent rather than interpolation: names come from a language model
    // and flow through the database, so they are never trusted as markup.
    el.querySelector('.item-emoji').textContent = item.emoji || '?';
    el.querySelector('.item-name').textContent = item.name;

    const entry = { uid: this.nextUid++, item, x, y, el };
    this.place(entry);
    this.host.append(el);
    this.entries.push(entry);
    this.attachDrag(entry);
    this.host.classList.add('has-items');
    return entry;
  }

  place(entry) {
    const rect = this.host.getBoundingClientRect();
    // Keep cards on the surface: a card dragged to the edge and left there is
    // unrecoverable without a Clear button, which is a bad kind of stuck.
    entry.x = Math.max(40, Math.min(rect.width - 40, entry.x));
    entry.y = Math.max(24, Math.min(rect.height - 24, entry.y));
    entry.el.style.left = `${entry.x}px`;
    entry.el.style.top = `${entry.y}px`;
  }

  attachDrag(entry) {
    entry.el.addEventListener('pointerdown', (event) => {
      if (this.busy) return;
      event.preventDefault();
      entry.el.setPointerCapture(event.pointerId);
      entry.el.classList.add('dragging');
      setDragging(true);

      const rect = this.host.getBoundingClientRect();
      const grabDx = entry.x - (event.clientX - rect.left);
      const grabDy = entry.y - (event.clientY - rect.top);
      let hovered = null;
      let done = false;

      const move = (e) => {
        const r = this.host.getBoundingClientRect();
        entry.x = e.clientX - r.left + grabDx;
        entry.y = e.clientY - r.top + grabDy;
        this.place(entry);

        const next = this.overlapping(entry);
        if (next !== hovered) {
          if (hovered) hovered.el.classList.remove('target');
          if (next) next.el.classList.add('target');
          hovered = next;
        }
      };

      const finish = (cancelled) => {
        if (done) return;                     // pointerup and lostpointercapture both land here
        done = true;
        entry.el.removeEventListener('pointermove', move);
        entry.el.removeEventListener('pointerup', onUp);
        entry.el.removeEventListener('pointercancel', onCancel);
        entry.el.removeEventListener('lostpointercapture', onUp);
        entry.el.classList.remove('dragging');
        setDragging(false);
        if (hovered) {
          hovered.el.classList.remove('target');
          if (!cancelled) this.combine(entry, hovered);
        }
      };

      const onUp = () => finish(false);
      const onCancel = () => finish(true);

      entry.el.addEventListener('pointermove', move);
      entry.el.addEventListener('pointerup', onUp);
      entry.el.addEventListener('pointercancel', onCancel);
      entry.el.addEventListener('lostpointercapture', onUp);
    });
  }

  overlapping(entry) {
    for (const other of this.entries) {
      if (other.uid === entry.uid) continue;
      const dx = other.x - entry.x;
      const dy = other.y - entry.y;
      if (Math.hypot(dx, dy) < OVERLAP_PX) return other;
    }
    return null;
  }

  combine(a, b) {
    // One craft at a time. Without this, a fast double-drag fires two requests
    // that both think they can spend the same coins.
    if (this.busy) return;
    this.busy = true;
    const at = centerOf(b.el);
    this.onCombine(a, b, at).finally(() => { this.busy = false; });
  }

  /** Both inputs were consumed; replace them with the result. */
  consume(a, b, result, at) {
    for (const entry of [a, b]) {
      entry.el.classList.add('consumed');
      setTimeout(() => this.drop(entry), 280);
    }
    burst(at.x, at.y, { color: tierColor(result.tier), count: 30, power: 5.5 });
    setTimeout(() => this.add(result, at), 200);
  }

  /** Nothing happened: shake both, puff, leave them where they are. */
  reject(a, b, at) {
    for (const entry of [a, b]) {
      entry.el.classList.remove('dud');
      // Reflow so the animation restarts if the same pair is tried twice.
      void entry.el.offsetWidth;
      entry.el.classList.add('dud');
    }
    puff(at.x, at.y);
    // Nudge them apart so the pair is not still overlapping and instantly
    // re-triggering on the next tiny drag.
    a.x -= 30; b.x += 30;
    this.place(a); this.place(b);
  }

  drop(entry) {
    entry.el.remove();
    this.entries = this.entries.filter((e) => e.uid !== entry.uid);
    if (!this.entries.length) this.host.classList.remove('has-items');
  }

  clear() {
    for (const entry of [...this.entries]) this.drop(entry);
  }

  /** Refresh names/emoji in place after a fallback name gets upgraded. */
  refresh(itemsByKey) {
    for (const entry of this.entries) {
      const fresh = itemsByKey.get(entry.item.key);
      if (!fresh) continue;
      entry.item = { ...entry.item, ...fresh };
      entry.el.querySelector('.item-emoji').textContent = entry.item.emoji || '?';
      entry.el.querySelector('.item-name').textContent = entry.item.name;
    }
  }
}

/**
 * Drag an item from the shelf onto the bench.
 *
 * A ghost follows the pointer so the gesture reads as carrying something,
 * rather than the card vanishing and reappearing.
 */
export function dragFromShelf(cardEl, item, bench, onDropped) {
  cardEl.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 && event.pointerType === 'mouse') return;
    event.preventDefault();
    setDragging(true);

    // Track the pointer ourselves rather than reading coordinates off whichever
    // terminal event happens to arrive. pointerup, pointercancel and
    // lostpointercapture do not all carry usable coordinates, and their order is
    // not something to depend on -- an earlier version bailed out of the drop
    // because lostpointercapture won the race.
    let lastX = event.clientX;
    let lastY = event.clientY;
    let done = false;

    const ghost = cardEl.cloneNode(true);
    // Capped width: the shelf card is full-column, and a full-width ghost
    // floating over the bench reads as a layout bug rather than as carrying
    // something. Also strip the action buttons, which make no sense in flight.
    ghost.querySelectorAll('.place-actions').forEach((el) => el.remove());
    ghost.style.cssText = `
      position:fixed; z-index:60; pointer-events:none; opacity:.92;
      width:${Math.min(cardEl.offsetWidth, 190)}px;
      transform:translate(-50%,-50%) scale(1.04) rotate(-1.5deg);
      box-shadow:0 12px 30px rgba(0,0,0,.5);`;
    document.body.append(ghost);

    const place = () => {
      ghost.style.left = `${lastX}px`;
      ghost.style.top = `${lastY}px`;
    };
    place();

    try { cardEl.setPointerCapture(event.pointerId); } catch { /* already gone */ }

    const move = (e) => {
      lastX = e.clientX;
      lastY = e.clientY;
      place();
    };

    const finish = (cancelled) => {
      if (done) return;                       // any of three events can get here
      done = true;
      cardEl.removeEventListener('pointermove', move);
      cardEl.removeEventListener('pointerup', onUp);
      cardEl.removeEventListener('pointercancel', onCancel);
      cardEl.removeEventListener('lostpointercapture', onUp);
      ghost.remove();
      setDragging(false);
      if (cancelled) return;

      // A few pixels of slack, so a click with a twitch in it is still a click
      // and does not fling the item onto the bench.
      const travelled = Math.abs(lastX - event.clientX) + Math.abs(lastY - event.clientY);
      if (travelled <= 4) return;

      const rect = bench.host.getBoundingClientRect();
      const inside =
        lastX >= rect.left && lastX <= rect.right &&
        lastY >= rect.top && lastY <= rect.bottom;
      if (inside) onDropped(item, { x: lastX, y: lastY });
    };

    const onUp = () => finish(false);
    const onCancel = () => finish(true);

    cardEl.addEventListener('pointermove', move);
    cardEl.addEventListener('pointerup', onUp);
    cardEl.addEventListener('pointercancel', onCancel);
    // If the shelf re-renders anyway and detaches this card, capture is lost and
    // this still completes the drop rather than stranding the ghost on screen.
    cardEl.addEventListener('lostpointercapture', onUp);
  });
}
