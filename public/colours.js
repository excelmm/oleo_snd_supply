const root = document.querySelector('#oleo-capacity-preview');
const find = selector => root.querySelector(selector);
const dialog = find('[data-colour-dialog]');
const options = find('[data-palette-options]');
const acid = find('[data-colour-acid]');
const alcohol = find('[data-colour-alcohol]');
const feedback = find('[data-colour-feedback]');
const apply = find('[data-apply-colours]');
const storageKey = 'oleo-product-colours';
const defaults = ['#176a60', '#63449c'];
const palettes = [
  ['Teal & Violet', defaults],
  ['Sinar Mas', ['#d71920', '#4b5563']],
  ['Ocean', ['#2563eb', '#b85c14']],
  ['Forest', ['#207451', '#884696']],
  ['Navy & Gold', ['#213c70', '#9a7010']],
];
const radios = [];
const samePair = (left, right) => left[0] === right[0] && left[1] === right[1];
let colours = defaults;

try {
  const saved = JSON.parse(localStorage.getItem(storageKey));
  if (Array.isArray(saved) && saved.length === 2 &&
      saved.every(value => typeof value === 'string' && /^#[\da-f]{6}$/.test(value)) &&
      saved[0] !== saved[1]) colours = saved;
} catch {
  // Use the default palette if the saved preference is unavailable.
}

function validateCustomColours() {
  const duplicate = acid.value === alcohol.value;
  feedback.hidden = !duplicate;
  apply.disabled = duplicate;
}

function showColours() {
  const isDefault = samePair(colours, defaults);
  for (const [index, property] of ['--fatty-acid-marker', '--fatty-alcohol-marker'].entries()) {
    if (isDefault) root.style.removeProperty(property);
    else root.style.setProperty(property, colours[index]);
  }
  [acid.value, alcohol.value] = colours;
  for (const [index, [, pair]] of palettes.entries()) radios[index].checked = samePair(colours, pair);
  validateCustomColours();
}

function chooseColours(pair) {
  colours = pair;
  showColours();
  try {
    localStorage.setItem(storageKey, JSON.stringify(colours));
  } catch {
    // The palette still applies to this page when storage is unavailable.
  }
}

for (const [name, pair] of palettes) {
  const label = document.createElement('label');
  const radio = document.createElement('input');
  radio.type = 'radio';
  radio.name = 'oleo-colour-palette';
  radio.value = name;
  radio.addEventListener('change', () => chooseColours(pair));
  radios.push(radio);

  const swatches = document.createElement('span');
  swatches.className = 'oleo-palette-swatches';
  swatches.setAttribute('aria-hidden', 'true');
  for (const colour of pair) {
    const swatch = document.createElement('i');
    swatch.style.backgroundColor = colour;
    swatches.append(swatch);
  }
  label.append(radio, name, swatches);
  options.append(label);
}

find('[data-open-colours]').addEventListener('click', () => {
  showColours();
  dialog.showModal();
});
find('[data-close-colours]').addEventListener('click', () => dialog.close());
find('[data-reset-colours]').addEventListener('click', () => chooseColours(defaults));
acid.addEventListener('input', validateCustomColours);
alcohol.addEventListener('input', validateCustomColours);
apply.addEventListener('click', () => chooseColours([acid.value, alcohol.value]));
showColours();
