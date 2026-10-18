import { useEffect, useMemo, useRef, useState } from 'react';
import { formatDuration, formatTimecode, pluralViolations, stripImages } from '../format.js';
import {
  DECISIONS,
  loadReview,
  requiresInvisibleData,
  saveReview,
  violationKey,
} from '../review.js';
import {
  AlertIcon,
  CheckCircleIcon,
  DownloadIcon,
  LinkIcon,
  PrintIcon,
  RefreshIcon,
} from './icons.jsx';
import Lightbox from './Lightbox.jsx';
import ScopeNotice from './ScopeNotice.jsx';
import Timeline from './Timeline.jsx';
import ViolationCard from './ViolationCard.jsx';

function VerdictBanner({ verdict, visualCount, outsideCount, children }) {
  const violation = verdict === 'violation';
  return (
    <section
      aria-labelledby="verdict-heading"
      className="card overflow-hidden print:break-inside-avoid"
    >
      <div className="flex">
        <div aria-hidden className={`w-1 shrink-0 ${violation ? 'bg-warning-500' : 'bg-success-500'}`} />
        <div className="flex min-w-0 flex-1 items-start gap-4 p-5 sm:p-6">
          <div
            className={`hidden h-10 w-10 shrink-0 items-center justify-center rounded-control sm:flex ${
              violation ? 'bg-warning-50 text-warning-700' : 'bg-success-50 text-success-700'
            }`}
          >
            {violation ? <AlertIcon className="h-5 w-5" /> : <CheckCircleIcon className="h-5 w-5" />}
          </div>
          <div className="min-w-0">
            <p className="eyebrow">Результат анализа</p>
            <h2 id="verdict-heading" className="mt-1 text-xl font-semibold tracking-tight text-ink-950 sm:text-2xl">
              {violation ? 'Обнаружены признаки возможных нарушений' : 'Нарушение не обнаружено'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-600">
              {violation ? (
                <>
                  {visualCount > 0 ? (
                    <>
                      Визуально наблюдаемых признаков: <span className="num font-semibold text-ink-900">{visualCount}</span>.
                      Это подсказка для проверяющего, а не заключение — подтвердите или отклоните каждый признак по
                      кадрам и видео.
                    </>
                  ) : (
                    <>Признаков, которые подтверждаются по видео, нет — см. пункты ниже.</>
                  )}
                  {outsideCount > 0 && (
                    <>
                      {' '}
                      Ещё {outsideCount} {pluralViolations(outsideCount)} требуют данных вне видео и нарушением не
                      считаются.
                    </>
                  )}
                </>
              ) : (
                <>
                  Визуально наблюдаемых признаков из перечня сервиса на записи не найдено. Это не подтверждает
                  отсутствие нарушений, которые по видео установить нельзя (проводки, сверки, документы).
                </>
              )}
            </p>
          </div>
        </div>
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="min-w-0 bg-white px-5 py-4">
      <dt className="text-xs text-ink-500">{label}</dt>
      <dd className="num mt-1 truncate text-base font-semibold text-ink-950" title={String(value)}>
        {value}
      </dd>
    </div>
  );
}

function ReviewSummary({ total, review, keys, saved }) {
  const counts = Object.fromEntries(DECISIONS.map((option) => [option.value, 0]));
  keys.forEach((key) => {
    const decision = review[key]?.decision;
    if (decision in counts) counts[decision] += 1;
  });
  const done = Object.values(counts).reduce((sum, value) => sum + value, 0);
  const percent = total ? Math.round((done / total) * 100) : 0;
  return (
    <section aria-labelledby="review-summary" className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="review-summary" className="section-title">
          Ручная проверка
        </h2>
        <p className="text-sm text-ink-600" aria-live="polite">
          Проверено{' '}
          <span className="num font-semibold text-ink-950">
            {done} из {total}
          </span>
        </p>
      </div>
      <div
        className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-100"
        role="progressbar"
        aria-label="Доля признаков с решением проверяющего"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div className="h-full rounded-full bg-brand-600 transition-[width]" style={{ width: `${percent}%` }} />
      </div>
      <ul className="mt-4 divide-y divide-ink-200 overflow-hidden rounded-control border border-ink-200">
        {DECISIONS.map((option) => (
          <li key={option.value} className="flex items-center justify-between gap-3 bg-white px-3.5 py-2.5 text-sm">
            <span className="flex items-center gap-2 text-ink-600">
              <span
                aria-hidden
                className={`h-2 w-2 rounded-full ${
                  option.value === 'confirmed'
                    ? 'bg-danger-500'
                    : option.value === 'rejected'
                      ? 'bg-success-500'
                      : 'bg-ink-500'
                }`}
              />
              {option.short}
            </span>
            <span className="num font-semibold text-ink-950">{counts[option.value]}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-ink-500">
        {saved
          ? 'Решения сохраняются только в этом браузере и не отправляются на сервер. Итоговое решение принимает проверяющий.'
          : 'Браузер запретил локальное хранение — решения пропадут после перезагрузки страницы. Скачайте протокол.'}
      </p>
    </section>
  );
}

function downloadBlob(content, name, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function ResultView({ job, videoUrl, onReset }) {
  const videoRef = useRef(null);
  const cardRefs = useRef([]);
  const [videoError, setVideoError] = useState(false);
  const [highlighted, setHighlighted] = useState(null);
  const [lightbox, setLightbox] = useState(null); // { violation, frame }
  const [showJson, setShowJson] = useState(false);
  const [review, setReview] = useState(() => loadReview(job.job_id));
  const [saved, setSaved] = useState(true);
  const [copied, setCopied] = useState(null);

  const violations = job.violations;
  const keys = useMemo(() => violations.map(violationKey), [violations]);
  const outside = useMemo(() => violations.map(requiresInvisibleData), [violations]);
  const outsideCount = outside.filter(Boolean).length;

  const canSeek = Boolean(videoUrl) && !videoError;
  const duration = job.video?.duration_sec;

  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    setSaved(saveReview(job.job_id, review));
  }, [job.job_id, review]);

  const updateReview = (index, patch) => {
    const key = keys[index];
    setReview((current) => ({
      ...current,
      [key]: { ...current[key], ...patch, updated_at: new Date().toISOString() },
    }));
  };

  const seek = (seconds) => {
    const video = videoRef.current;
    if (!video || !canSeek) return;
    video.currentTime = seconds;
    video.scrollIntoView({ behavior: 'smooth', block: 'center' });
    video.play().catch(() => {});
  };

  const selectViolation = (index) => {
    setHighlighted(index);
    cardRefs.current[index]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    seek(violations[index].timecode_sec);
  };

  const downloadProtocol = () => {
    const protocol = {
      document: 'Протокол ручной проверки видеозаписи кассы',
      notice:
        'Результат сервиса — подсказка для проверки человеком, а не юридическое или дисциплинарное заключение. ' +
        'Выводы о данных, которых нет на видео (проводки, сверки), сервисом не делаются.',
      job_id: job.job_id,
      filename: job.filename || null,
      service_verdict: job.verdict,
      exported_at: new Date().toISOString(),
      items: violations.map((violation, index) => ({
        number: index + 1,
        type: violation.type,
        code: violation.code || null,
        timecode_sec: violation.timecode_sec,
        timecode: formatTimecode(violation.timecode_sec),
        rule: violation.rule ? `${violation.rule.clause} — ${violation.rule.act}` : null,
        requires_data_outside_video: outside[index],
        reviewer_decision: review[keys[index]]?.decision || 'not_reviewed',
        reviewer_comment: review[keys[index]]?.comment || '',
      })),
    };
    downloadBlob(JSON.stringify(protocol, null, 2), `review_${job.job_id}.json`, 'application/json');
  };

  const copyLink = async () => {
    const link = `${window.location.origin}${window.location.pathname}#job=${job.job_id}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopied('Ссылка скопирована');
    } catch {
      setCopied(link);
    }
  };

  const activeViolation = lightbox ? violations[lightbox.violation] : null;

  return (
    <div className="space-y-6">
      <VerdictBanner
        verdict={job.verdict}
        visualCount={violations.length - outsideCount}
        outsideCount={outsideCount}
      >
        <dl className="grid grid-cols-2 gap-px border-t border-ink-200 bg-ink-200 sm:grid-cols-4">
          <Stat label="Файл" value={job.filename || '—'} />
          <Stat label="Длительность" value={duration ? formatDuration(duration) : '—'} />
          <Stat label="Проанализировано кадров" value={job.video?.frames_analyzed ?? '—'} />
          <Stat label="Время обработки" value={job.processing_time_sec ? formatDuration(job.processing_time_sec) : '—'} />
        </dl>
      </VerdictBanner>

      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <button type="button" className="btn-primary" onClick={onReset}>
          <RefreshIcon className="h-4 w-4" /> Проверить другое видео
        </button>
        {violations.length > 0 && (
          <button type="button" className="btn-secondary" onClick={downloadProtocol}>
            <DownloadIcon className="h-4 w-4" /> Протокол проверки
          </button>
        )}
        <button
          type="button"
          className="btn-secondary"
          onClick={() => downloadBlob(JSON.stringify(job, null, 2), `result_${job.job_id}.json`, 'application/json')}
        >
          <DownloadIcon className="h-4 w-4" /> Ответ API (JSON)
        </button>
        <button type="button" className="btn-secondary" onClick={() => window.print()}>
          <PrintIcon className="h-4 w-4" /> Печать / PDF
        </button>
        <button type="button" className="btn-ghost" onClick={copyLink}>
          <LinkIcon className="h-4 w-4" /> Ссылка на результат
        </button>
        <button
          type="button"
          className="btn-ghost"
          aria-expanded={showJson}
          aria-controls="api-json"
          onClick={() => setShowJson((v) => !v)}
        >
          {showJson ? 'Скрыть ответ API' : 'Показать ответ API'}
        </button>
      </div>
      {copied && (
        <p className="-mt-3 break-all text-xs text-ink-500 print:hidden" role="status">
          {copied}
        </p>
      )}

      {showJson && (
        <pre
          id="api-json"
          className="max-h-[480px] overflow-auto rounded-panel border border-ink-800 bg-ink-950 p-4 font-mono text-xs leading-relaxed text-ink-100 print:hidden"
        >
          {JSON.stringify(stripImages(job), null, 2)}
        </pre>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="card print:hidden" aria-labelledby="video-heading">
          <div className="flex items-center justify-between gap-3 border-b border-ink-200 px-5 py-3.5">
            <h2 id="video-heading" className="section-title">
              Видеозапись
            </h2>
            {duration > 0 && <span className="num font-mono text-xs text-ink-500">{formatTimecode(duration)}</span>}
          </div>
          <div className="p-5">
            {videoUrl && !videoError ? (
              <video
                ref={videoRef}
                src={videoUrl}
                controls
                playsInline
                aria-label="Проверяемая видеозапись"
                className="aspect-video w-full rounded-control bg-ink-950"
                onError={() => setVideoError(true)}
              />
            ) : (
              <div className="notice-neutral justify-center text-center">
                {videoError
                  ? 'Браузер не может воспроизвести этот файл (например, кодек HEVC в .mov). Используйте кадры-доказательства ниже.'
                  : 'Исходное видео не загружено в этой вкладке — доступны таймкоды и кадры-доказательства.'}
              </div>
            )}
            {duration > 0 && (
              <div className="mt-5">
                <p className="eyebrow mb-2">Шкала событий</p>
                <Timeline duration={duration} violations={violations} onSelect={selectViolation} />
              </div>
            )}
          </div>
        </section>

        <div className="space-y-6 lg:sticky lg:top-24">
          {violations.length > 0 && (
            <ReviewSummary total={violations.length} review={review} keys={keys} saved={saved} />
          )}
          <ScopeNotice compact />
        </div>
      </div>

      {violations.length > 0 && (
        <section className="space-y-4" aria-labelledby="signs-heading">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="signs-heading" className="text-lg font-semibold text-ink-950">
              Признаки для проверки
            </h2>
            <span className="num text-sm text-ink-500">
              {violations.length} {pluralViolations(violations.length)}
            </span>
          </div>
          {violations.map((violation, index) => (
            <ViolationCard
              key={keys[index]}
              ref={(node) => {
                cardRefs.current[index] = node;
              }}
              violation={violation}
              index={index}
              highlighted={highlighted === index}
              canSeek={canSeek}
              outsideVideo={outside[index]}
              review={review[keys[index]]}
              onReview={(patch) => updateReview(index, patch)}
              onSeek={(seconds) => {
                setHighlighted(index);
                seek(seconds);
              }}
              onOpenFrame={(frame) => setLightbox({ violation: index, frame })}
            />
          ))}
        </section>
      )}

      {activeViolation && activeViolation.evidence_frames.length > 0 && (
        <Lightbox
          frames={activeViolation.evidence_frames}
          index={lightbox.frame}
          title={`${lightbox.violation + 1}. ${activeViolation.type}`}
          onClose={() => setLightbox(null)}
          onChange={(frame) => setLightbox({ ...lightbox, frame })}
        />
      )}
    </div>
  );
}
