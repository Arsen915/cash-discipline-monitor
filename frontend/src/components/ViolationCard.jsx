import { forwardRef, useId } from 'react';
import { confidenceLevel, formatTimecode } from '../format.js';
import { cleanRequirement, DECISIONS, requirementKind, splitDescription, typeLimit } from '../review.js';
import { AlertIcon, DocIcon, EyeIcon, ExternalIcon, PlayIcon, UserCheckIcon } from './icons.jsx';

function ReviewControls({ decision, comment, onDecide, onComment, title }) {
  const id = useId();
  return (
    <fieldset className="border-t border-ink-200 pt-5 print:border-0">
      <legend className="sr-only">Решение проверяющего: {title}</legend>
      <p className="eyebrow flex items-center gap-2">
        <UserCheckIcon className="h-4 w-4" /> Решение проверяющего
      </p>
      <div className="mt-3 flex flex-wrap gap-2 print:hidden" role="radiogroup" aria-label="Решение проверяющего">
        {DECISIONS.map((option) => {
          const active = decision === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onDecide(active ? null : option.value)}
              className={`decision decision-${option.value} ${active ? 'is-active' : ''}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="mt-2 hidden text-sm print:block">
        {DECISIONS.find((option) => option.value === decision)?.short || 'Не проверено'}
      </p>
      <label htmlFor={`${id}-comment`} className="mt-4 block text-xs font-medium text-ink-600">
        Комментарий (необязательно)
      </label>
      <textarea
        id={`${id}-comment`}
        rows={2}
        maxLength={1000}
        value={comment}
        onChange={(event) => onComment(event.target.value)}
        placeholder="Что увидели на кадрах и какие данные вне видео нужно запросить"
        className="input mt-1 resize-y"
      />
    </fieldset>
  );
}

const ViolationCard = forwardRef(function ViolationCard(
  { violation, index, highlighted, canSeek, onSeek, onOpenFrame, review, onReview, outsideVideo },
  ref,
) {
  const confidence = confidenceLevel(violation.confidence ?? 0);
  const rule = violation.rule;
  const { observed, checks } = splitDescription(violation.description);
  const limit = typeLimit(violation.code);
  const kind = rule ? requirementKind(rule.requirement) : null;
  const decided = DECISIONS.find((option) => option.value === review?.decision);

  return (
    <article
      ref={ref}
      aria-labelledby={`violation-${index}-title`}
      className={`card scroll-mt-24 overflow-hidden transition-shadow duration-150 print:break-inside-avoid print:shadow-none ${
        highlighted ? 'border-ink-900 ring-1 ring-ink-900' : ''
      }`}
    >
      <header className="flex flex-col gap-3 border-b border-ink-200 bg-ink-50/60 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={`num flex h-7 w-7 shrink-0 items-center justify-center rounded-control text-sm font-semibold ${
              outsideVideo ? 'border border-ink-300 bg-white text-ink-600' : 'bg-ink-900 text-white'
            }`}
            aria-hidden
          >
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className={`eyebrow ${outsideVideo ? '' : 'text-warning-700'}`}>
              {outsideVideo ? 'Требует данных вне видео' : 'Признак возможного нарушения'}
            </p>
            <h3 id={`violation-${index}-title`} className="mt-0.5 font-semibold leading-snug text-ink-950">
              {violation.type}
            </h3>
            {violation.code && <p className="mt-0.5 font-mono text-2xs text-ink-500">{violation.code}</p>}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {decided && (
            <span className={`status-pill status-${decided.value}`}>{decided.short}</span>
          )}
          {violation.confidence != null && (
            <span
              className={`badge ${confidence.className}`}
              title="Оценка модели детекции, а не вероятность нарушения"
            >
              Уверенность модели: <span className="num font-semibold">{Math.round(violation.confidence * 100)}%</span>
            </span>
          )}
          <button
            type="button"
            onClick={() => onSeek(violation.timecode_sec)}
            disabled={!canSeek}
            aria-label={`Перейти к ${formatTimecode(violation.timecode_sec)} в видео`}
            title={canSeek ? 'Перейти к моменту в видео' : 'Видео недоступно для воспроизведения в этой вкладке'}
            className="num inline-flex h-7 items-center gap-1.5 rounded-control border border-ink-300 bg-white px-2.5 font-mono text-xs font-semibold text-ink-900 transition-colors duration-150 hover:border-brand-600 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:cursor-default disabled:text-ink-400 disabled:hover:border-ink-300"
          >
            <PlayIcon className="h-3 w-3" />
            {formatTimecode(violation.timecode_sec)}
            {violation.end_sec > violation.timecode_sec && (
              <span className="font-normal text-ink-500">–{formatTimecode(violation.end_sec)}</span>
            )}
          </button>
        </div>
      </header>

      <div className="space-y-5 p-5">
        {outsideVideo && (
          <p className="notice-neutral">
            <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
            Вывод опирается на данные, которых нет на записи (учётная система, сверка). По видео он не
            подтверждается и не считается обнаруженным признаком — проверьте по первичным данным.
          </p>
        )}

        <div>
          <p className="eyebrow flex items-center gap-2">
            <EyeIcon className="h-4 w-4" /> Что видно на записи
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink-800">{observed || 'Описание не передано сервисом.'}</p>
        </div>

        {violation.evidence_frames.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {violation.evidence_frames.map((frame, frameIndex) => (
              <button
                key={`${frame.timestamp_sec}-${frameIndex}`}
                type="button"
                onClick={() => onOpenFrame(frameIndex)}
                aria-label={`Открыть кадр ${frameIndex + 1} (${formatTimecode(frame.timestamp_sec)}) крупно`}
                className="group relative overflow-hidden rounded-control border border-ink-200 bg-ink-100 transition-colors duration-150 hover:border-ink-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
              >
                <img
                  src={`data:image/jpeg;base64,${frame.image_base64}`}
                  alt={`Кадр-доказательство ${formatTimecode(frame.timestamp_sec)}`}
                  className="aspect-video w-full object-cover"
                  loading="lazy"
                />
                <span className="absolute bottom-2 left-2 rounded bg-ink-950/80 px-1.5 py-0.5 font-mono text-2xs text-white">
                  {formatTimecode(frame.timestamp_sec)}
                  {frameIndex === 0 ? ' · ключевой' : ''}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="notice-neutral text-ink-500">
            Кадры-доказательства не переданы — проверьте фрагмент по таймкоду в видео.
          </p>
        )}

        {(checks.length > 0 || limit) && (
          <div className="rounded-control border border-warning-200 border-l-warning-500 bg-warning-50 p-4 [border-left-width:3px]">
            <p className="eyebrow text-warning-800">Что подтвердить человеку</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-warning-950 marker:text-warning-500">
              {checks.map((check) => (
                <li key={check}>{check}</li>
              ))}
              {limit && <li>{limit}</li>}
            </ul>
          </div>
        )}

        {rule ? (
          <div className="panel-inset p-4">
            <p className="eyebrow flex flex-wrap items-center gap-2">
              <DocIcon className="h-4 w-4" /> Возможное нормативное основание · {rule.clause}
              <span
                className={`badge px-1.5 text-2xs normal-case tracking-normal ${
                  kind === 'quote' ? 'bg-white text-ink-700 ring-ink-300' : 'bg-ink-100 text-ink-600 ring-ink-200'
                }`}
              >
                {kind === 'quote' ? 'дословная цитата' : 'пересказ пункта'}
              </span>
            </p>
            <p className="mt-2 text-sm font-semibold text-ink-900">{rule.document}</p>
            <p className="mt-1 text-xs text-ink-500">{rule.act}</p>
            <blockquote className="mt-3 border-l-2 border-ink-300 pl-3 text-sm leading-relaxed text-ink-700">
              {kind === 'quote' ? rule.requirement : cleanRequirement(rule.requirement)}
            </blockquote>
            {rule.url && (
              <a
                href={rule.url}
                target="_blank"
                rel="noreferrer noopener"
                className="link mt-3 inline-flex items-center gap-1 text-sm print:hidden"
              >
                Текст акта на adilet.zan.kz <ExternalIcon className="h-3.5 w-3.5" />
                <span className="sr-only">(откроется в новой вкладке)</span>
              </a>
            )}
          </div>
        ) : (
          <p className="text-sm text-ink-500">Нормативное основание сервисом не передано.</p>
        )}

        <ReviewControls
          title={violation.type}
          decision={review?.decision ?? null}
          comment={review?.comment ?? ''}
          onDecide={(decision) => onReview({ decision })}
          onComment={(comment) => onReview({ comment })}
        />
      </div>
    </article>
  );
});

export default ViolationCard;
