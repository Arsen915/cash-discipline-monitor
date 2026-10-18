import { useEffect, useRef } from 'react';
import { formatTimecode } from '../format.js';
import { ChevronIcon, CloseIcon } from './icons.jsx';

export default function Lightbox({ frames, index, title, onClose, onChange }) {
  const frame = frames[index];
  const dialogRef = useRef(null);
  const closeRef = useRef(null);

  // Фокус в диалог при открытии и возврат на исходный элемент при закрытии
  useEffect(() => {
    const previous = document.activeElement;
    closeRef.current?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight' && index < frames.length - 1) onChange(index + 1);
      if (event.key === 'ArrowLeft' && index > 0) onChange(index - 1);
      if (event.key === 'Tab') {
        // Простая ловушка фокуса внутри диалога
        const focusable = dialogRef.current?.querySelectorAll('button:not([disabled])');
        if (!focusable?.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [index, frames.length, onClose, onChange]);

  if (!frame) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/90 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="lightbox-title"
        className="relative w-full max-w-5xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between gap-4 text-white">
          <div className="min-w-0">
            <p id="lightbox-title" className="truncate text-sm font-semibold">
              {title}
            </p>
            <p className="num font-mono text-xs text-ink-300" aria-live="polite">
              Кадр {index + 1} из {frames.length} · {formatTimecode(frame.timestamp_sec)} (
              {frame.timestamp_sec.toFixed(2)} с)
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-control p-2 transition-colors duration-150 hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
            aria-label="Закрыть"
          >
            <CloseIcon className="h-6 w-6" />
          </button>
        </div>
        <img
          src={`data:image/jpeg;base64,${frame.image_base64}`}
          alt={`Кадр-доказательство ${formatTimecode(frame.timestamp_sec)}`}
          className="max-h-[78vh] w-full rounded-control object-contain"
        />
        {frames.length > 1 && (
          <div className="mt-3 flex justify-center gap-2">
            <button
              type="button"
              disabled={index === 0}
              onClick={() => onChange(index - 1)}
              className="rounded-control border border-white/15 bg-white/5 p-2 text-white transition-colors duration-150 hover:bg-white/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-white disabled:opacity-30"
              aria-label="Предыдущий кадр"
            >
              <ChevronIcon className="h-5 w-5 rotate-180" />
            </button>
            <button
              type="button"
              disabled={index === frames.length - 1}
              onClick={() => onChange(index + 1)}
              className="rounded-control border border-white/15 bg-white/5 p-2 text-white transition-colors duration-150 hover:bg-white/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-white disabled:opacity-30"
              aria-label="Следующий кадр"
            >
              <ChevronIcon className="h-5 w-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
