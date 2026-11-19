const root = document.getElementById('oleo-capacity-preview');
const find = selector => root.querySelector(selector);
const board = find('.oleo-overview');
const panels = {
  mapHeight: find('#oleo-map-viewport'),
  tableHeight: find('#oleo-table-viewport'),
};
const dialog = find('[data-panel-sizes-dialog]');
const stacked = matchMedia('(max-width: 560px)');
const storageKey = 'global-oleochemicals-panel-sizes';
const defaults = { split: 74, mapHeight: null, tableHeight: null };
const heights = {
  mapHeight: { min: 180, max: 2000, property: '--oleo-map-height' },
  tableHeight: { min: 140, max: 2000, property: '--oleo-table-height' },
};
const handles = [...root.querySelectorAll('[data-resize]')];
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
let sizes = { ...defaults };
let drag = null;

try {
  const saved = JSON.parse(localStorage.getItem(storageKey));
  if (Number.isFinite(saved?.split)) sizes.split = clamp(saved.split, 25, 85);
  for (const [key, { min, max }] of Object.entries(heights)) {
    if (Number.isFinite(saved?.[key])) sizes[key] = clamp(saved[key], min, max);
  }
} catch {
  // Resizing remains available when browser storage is disabled.
}

function widthBounds() {
  const available = Math.max(1, board.clientWidth - find('[data-resize="split"]').offsetWidth);
  const min = Math.min(55, Math.max(25, Math.ceil(240 / available * 100)));
  const max = Math.max(min, Math.min(85, Math.floor((available - 205) / available * 100)));
  return { min, max, available };
}

const bounds = key => key === 'split' ? widthBounds() : heights[key];
function currentSize(key) {
  if (key !== 'split') return panels[key].clientHeight;
  const { min, max } = widthBounds();
  return clamp(sizes.split, min, max);
}

function syncControls() {
  const isStacked = stacked.matches;
  find('[data-stacked-layout]').hidden = !isStacked;
  for (const handle of handles) {
    const key = handle.dataset.resize;
    const { min, max } = bounds(key);
    const value = Math.round(currentSize(key));
    const accessibleValue = clamp(value, min, max);
    handle.tabIndex = key === 'split' && isStacked ? -1 : 0;
    handle.setAttribute('aria-valuemin', min);
    handle.setAttribute('aria-valuemax', max);
    handle.setAttribute('aria-valuenow', accessibleValue);
    handle.setAttribute('aria-valuetext', key === 'split' ? `Map ${value}%, plant panel ${100 - value}%` : `${value} pixels`);

    if (!dialog.open) continue;
    const input = find(`[data-size-input="${key}"]`);
    input.min = min;
    input.max = max;
    input.disabled = key === 'split' && isStacked;
    input.value = value >= min && value <= max ? value : '';
  }
}

function applySizes() {
  const split = currentSize('split');
  board.style.setProperty('--oleo-map-track', `${split}fr`);
  board.style.setProperty('--oleo-details-track', `${100 - split}fr`);
  for (const [key, { property }] of Object.entries(heights)) {
    if (sizes[key] == null) root.style.removeProperty(property);
    else root.style.setProperty(property, `${sizes[key]}px`);
  }
  syncControls();
}

function saveSizes() {
  try { localStorage.setItem(storageKey, JSON.stringify(sizes)); } catch {}
}

function setSize(key, value) {
  const { min, max } = bounds(key);
  sizes[key] = value == null ? defaults[key] : clamp(Math.round(value), min, max);
  applySizes();
}

function finishDrag(event, cancel = false) {
  if (!drag || (event && drag.pointerId !== event.pointerId)) return;
  const { handle, pointerId, initialSizes } = drag;
  drag = null;
  if (cancel) sizes = initialSizes;
  delete root.dataset.resizingPanel;
  if (handle.hasPointerCapture(pointerId)) handle.releasePointerCapture(pointerId);
  applySizes();
  if (!cancel) saveSizes();
}

for (const handle of handles) {
  const key = handle.dataset.resize;
  const width = key === 'split';
  const position = event => width ? event.clientX : event.clientY;
  handle.addEventListener('pointerdown', event => {
    if (drag || event.button !== 0 || (width && stacked.matches)) return;
    event.preventDefault();
    drag = {
      handle,
      pointerId: event.pointerId,
      origin: position(event),
      startSize: currentSize(key),
      pixelsToUnits: width ? 100 / widthBounds().available : 1,
      initialSizes: { ...sizes },
    };
    root.dataset.resizingPanel = key;
    handle.setPointerCapture(event.pointerId);
  });
  handle.addEventListener('pointermove', event => {
    if (drag?.handle !== handle || drag.pointerId !== event.pointerId) return;
    setSize(key, drag.startSize + (position(event) - drag.origin) * drag.pixelsToUnits);
  });
  handle.addEventListener('pointerup', event => finishDrag(event));
  handle.addEventListener('pointercancel', event => finishDrag(event, true));
  handle.addEventListener('lostpointercapture', event => finishDrag(event));
  handle.addEventListener('dblclick', () => { setSize(key, null); saveSizes(); });
  handle.addEventListener('keydown', event => {
    if (width && stacked.matches) return;
    const decrease = width ? 'ArrowLeft' : 'ArrowUp';
    const increase = width ? 'ArrowRight' : 'ArrowDown';
    if (![decrease, increase, 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const step = width ? (event.shiftKey ? 10 : 2) : (event.shiftKey ? 100 : 20);
    const { min, max } = bounds(key);
    let value = clamp(currentSize(key), min, max);
    if (event.key === 'Home') value = min;
    else if (event.key === 'End') value = max;
    else value += event.key === decrease ? -step : step;
    setSize(key, value);
    saveSizes();
  });
}

for (const input of dialog.querySelectorAll('[data-size-input]')) {
  input.addEventListener('change', () => {
    if (input.validity.badInput) {
      syncControls();
      return;
    }
    setSize(input.dataset.sizeInput, input.value === '' ? null : input.valueAsNumber);
    saveSizes();
  });
}
find('[data-open-panel-sizes]').addEventListener('click', () => { dialog.showModal(); syncControls(); });
find('[data-close-panel-sizes]').addEventListener('click', () => dialog.close());
find('[data-reset-panel-sizes]').addEventListener('click', () => {
  sizes = { ...defaults };
  applySizes();
  saveSizes();
});
root.addEventListener('keydown', event => {
  if (drag && event.key === 'Escape') {
    event.preventDefault();
    finishDrag(null, true);
  }
});
stacked.addEventListener('change', applySizes);
const observer = new ResizeObserver(applySizes);
observer.observe(board);
observer.observe(panels.tableHeight);
applySizes();
