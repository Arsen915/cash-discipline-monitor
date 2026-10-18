import { formatTimecode } from '../format.js';

export default function Timeline({ duration, violations, onSelect }) {
  if (!duration) return null;
  const position = (seconds) => `${Math.min(Math.max(seconds / duration, 0), 1) * 100}%`;

  return (
    <div>
      <div
        className="relative h-10 rounded-control border border-ink-200 bg-ink-50 bg-[linear-gradient(to_right,theme(colors.ink.200)_1px,transparent_1px)] bg-[length:10%_100%]"
        role="group"
        aria-label={`Шкала записи длительностью ${formatTimecode(duration)}: ${violations.length} отметок`}
      >
        {violations.map((violation, index) => {
          const start = Math.min(violation.start_sec ?? violation.timecode_sec, violation.timecode_sec);
          const end = Math.max(violation.end_sec ?? start, start + duration * 0.01);
          return (
            <button
              key={`${violation.code}-${index}`}
              type="button"
              onClick={() => onSelect(index)}
              title={`${formatTimecode(violation.timecode_sec)} · ${violation.type}`}
              aria-label={`Признак ${index + 1}: ${violation.type}, ${formatTimecode(violation.timecode_sec)}`}
              className="group absolute inset-y-1.5 rounded-sm bg-warning-500/25 ring-1 ring-inset ring-warning-600/60 transition-colors duration-150 hover:bg-warning-500/45 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
              style={{ left: position(start), width: `calc(${position(end)} - ${position(start)})`, minWidth: '6px' }}
            >
              <span
                className="num absolute -top-1.5 left-0 flex h-5 min-w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded bg-ink-900 px-1 text-2xs font-semibold text-white"
                style={{ left: `calc(${position(violation.timecode_sec)} - ${position(start)})` }}
                aria-hidden
              >
                {index + 1}
              </span>
            </button>
          );
        })}
      </div>
      <div className="num mt-1.5 flex justify-between font-mono text-2xs text-ink-500">
        <span>00:00.0</span>
        <span>{formatTimecode(duration)}</span>
      </div>
    </div>
  );
}
