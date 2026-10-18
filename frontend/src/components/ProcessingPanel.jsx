import { useEffect, useState } from 'react';
import { formatDuration } from '../format.js';
import { CheckIcon, CloseIcon, Spinner } from './icons.jsx';

const STEPS = [
  { key: 'upload', label: 'Загрузка видео' },
  { key: 'detect', label: 'Детекция людей и предметов' },
  { key: 'rules', label: 'Проверка правил' },
  { key: 'evidence', label: 'Кадры-доказательства' },
];

function activeStep(phase, stage = '') {
  if (phase === 'uploading') return 0;
  if (/доказательств|Готово/i.test(stage)) return 3;
  if (/Калибровка|правил/i.test(stage)) return 2;
  return 1;
}

export default function ProcessingPanel({ phase, uploadProgress, job, startedAt, fileName, onCancel }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const uploading = phase === 'uploading';
  const fraction = uploading ? uploadProgress : job?.progress ?? 0;
  const percent = Math.round(Math.min(Math.max(fraction, 0), 1) * 100);
  const stage = uploading ? 'Загрузка видео на сервер' : job?.stage || 'Ожидание начала обработки';
  const current = activeStep(phase, job?.stage);

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4 border-b border-ink-200 p-5 sm:p-6">
        <div className="min-w-0">
          <p className="eyebrow">{uploading ? 'Загрузка' : 'Анализ видео'}</p>
          <h2 className="mt-1 truncate text-lg font-semibold text-ink-950">{fileName || 'Видео'}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Spinner className="h-5 w-5 text-brand-600" />
          {onCancel && (
            <button type="button" className="btn-secondary h-9 px-3" onClick={onCancel}>
              <CloseIcon className="h-4 w-4" />
              {uploading ? 'Отменить загрузку' : 'Отменить анализ'}
            </button>
          )}
        </div>
      </div>

      <div className="p-5 sm:p-6">
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-medium text-ink-800" role="status" aria-live="polite">
            {stage}
          </span>
          <span className="num text-lg font-semibold text-ink-950">{percent}%</span>
        </div>
        <div
          className="mt-2 h-2 overflow-hidden rounded-full bg-ink-100"
          role="progressbar"
          aria-label={uploading ? 'Загрузка видео' : 'Анализ видео'}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <div
            className="progress-stripes h-full animate-stripes rounded-full bg-brand-600 transition-[width] duration-500"
            style={{ width: `${Math.max(percent, 3)}%` }}
          />
        </div>
        <div className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs text-ink-500">
          <span>{job?.queue_position ? `В очереди: ${job.queue_position}-я` : ''}</span>
          <span className="num">Прошло: {formatDuration((now - startedAt) / 1000)}</span>
        </div>

        <ol
          className="mt-6 grid overflow-hidden rounded-control border border-ink-200 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="Этапы обработки"
        >
          {STEPS.map((step, index) => {
            const done = index < current;
            const active = index === current;
            return (
              <li
                key={step.key}
                aria-current={active ? 'step' : undefined}
                className={`flex items-center gap-2.5 border-ink-200 px-3.5 py-3 text-sm max-sm:[&:not(:first-child)]:border-t sm:max-lg:[&:nth-child(n+3)]:border-t sm:max-lg:[&:nth-child(even)]:border-l lg:[&:not(:first-child)]:border-l ${
                  active ? 'bg-brand-50 font-medium text-ink-950' : done ? 'bg-white text-ink-700' : 'bg-white text-ink-400'
                }`}
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-2xs font-semibold ${
                    done
                      ? 'bg-brand-600 text-white'
                      : active
                        ? 'border-2 border-brand-600 text-brand-700'
                        : 'border border-ink-300 text-ink-400'
                  }`}
                >
                  {done ? <CheckIcon className="h-3 w-3" /> : index + 1}
                </span>
                <span className="sr-only">{done ? 'выполнено: ' : active ? 'выполняется: ' : 'ожидает: '}</span>
                {step.label}
              </li>
            );
          })}
        </ol>
        <p className="mt-5 text-xs leading-relaxed text-ink-500">
          Обычно анализ занимает до минуты. Вкладку можно закрыть — результат откроется по ссылке с идентификатором
          задачи.
        </p>
      </div>
    </div>
  );
}
