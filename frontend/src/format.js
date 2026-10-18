export function formatTimecode(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const rest = safe - minutes * 60;
  return `${String(minutes).padStart(2, '0')}:${rest.toFixed(1).padStart(4, '0')}`;
}

export function formatDuration(seconds) {
  const safe = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return minutes ? `${minutes} мин ${rest} с` : `${rest} с`;
}

export function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

export function pluralViolations(count) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'признак';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'признака';
  return 'признаков';
}

// Уверенность модели детекции — не вероятность нарушения, поэтому нейтральные цвета
export function confidenceLevel(value) {
  if (value >= 0.8) return { label: 'высокая', className: 'bg-ink-800 text-white ring-ink-800' };
  if (value >= 0.6) return { label: 'средняя', className: 'bg-ink-100 text-ink-700 ring-ink-200' };
  return { label: 'низкая', className: 'bg-white text-ink-600 ring-ink-300' };
}

// Для просмотра JSON в интерфейсе: длинные base64 заменяем на пометку с размером
export function stripImages(value) {
  return JSON.parse(
    JSON.stringify(value, (key, item) =>
      key === 'image_base64' && typeof item === 'string'
        ? `<JPEG base64, ${(item.length * 0.75 / 1024).toFixed(0)} КБ>`
        : item,
    ),
  );
}
