// --- Запоминаем активную строку и её file-input ---
let activeRow = null;
let activeInput = null;

function findRow(el) {
  return el && el.closest ? el.closest('tr, .form-row, .inline-related') : null;
}

function findFileInput(row) {
  return row ? row.querySelector('input[type="file"][data-paste-target]') : null;
}

// Помечаем строку при любом взаимодействии
document.addEventListener('focusin', (e) => {
  const row = findRow(e.target);
  if (!row) return;
  activeRow = row;
  activeInput = findFileInput(row) || activeInput;
});
document.addEventListener('click', (e) => {
  const row = findRow(e.target);
  if (!row) return;
  activeRow = row;
  activeInput = findFileInput(row) || activeInput;
});
document.addEventListener('mouseover', (e) => {
  const row = findRow(e.target);
  if (!row) return;
  activeRow = row;
  activeInput = findFileInput(row) || activeInput;
});

// --- Вставка из буфера в нужную строку ---
document.addEventListener('paste', function (e) {
  const items = (e.clipboardData && e.clipboardData.items) ? e.clipboardData.items : null;
  if (!items) return;

  // 1) по умолчанию — последний активный инпут
  let input = activeInput;

  // 2) приоритет — строке, где сейчас фокус
  const focusedRow = findRow(document.activeElement);
  if (focusedRow) {
    const focusedInput = findFileInput(focusedRow);
    if (focusedInput) input = focusedInput;
  }

  // 3) fallback — строка, где случился paste
  if (!input) {
    const targetRow = findRow(e.target);
    input = findFileInput(targetRow);
  }

  if (!input) return;

  const item = Array.from(items).find(i => i.type && i.type.startsWith('image/'));
  if (!item) return;

  const blob = item.getAsFile();
  if (!blob) return;

  const ext = (blob.type.split('/')[1] || 'png').toLowerCase();
  const file = new File([blob], `pasted.${ext}`, { type: blob.type || 'image/png' });

  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;

  input.dispatchEvent(new Event('change', { bubbles: true }));
  e.preventDefault();
});
