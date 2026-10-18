import { OUT_OF_SCOPE } from '../review.js';
import { ChevronIcon, ScopeIcon } from './icons.jsx';

// Границы вывода сервиса: что он делает и чего не утверждает (ТЗ, раздел 7)
export default function ScopeNotice({ compact = false }) {
  return (
    <aside aria-label="Границы анализа" className={`card ${compact ? 'p-4 sm:p-5' : 'p-5'}`}>
      <div className="flex items-start gap-3">
        <ScopeIcon className="mt-0.5 h-5 w-5 shrink-0 text-ink-500" />
        <div className="min-w-0 space-y-3 text-sm text-ink-700">
          <p className="leading-relaxed">
            <strong className="font-semibold text-ink-950">Это подсказка для проверяющего, а не заключение.</strong>{' '}
            Сервис отмечает только то, что видно в кадре, и указывает, где смотреть. Юридическое или дисциплинарное
            решение принимает человек.
          </p>
          <details className="group" open={!compact}>
            <summary className="link inline-flex cursor-pointer select-none list-none items-center gap-1 [&::-webkit-details-marker]:hidden">
              <ChevronIcon className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
              Что сервис не устанавливает по видео
            </summary>
            <ul
              className={`mt-3 grid gap-y-2 text-ink-600 ${compact ? 'gap-x-8 sm:grid-cols-2' : ''}`}
            >
              {OUT_OF_SCOPE.map((item) => (
                <li key={item} className="flex gap-2.5">
                  <span aria-hidden className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-400" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 border-t border-ink-200 pt-3 text-xs text-ink-500">
              Если вывод зависит от таких данных, сервис не называет его обнаруженным нарушением.
            </p>
          </details>
        </div>
      </div>
    </aside>
  );
}
