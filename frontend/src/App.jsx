import { useEffect, useRef, useState } from 'react';
import { getHealth, getJob, uploadVideo } from './api.js';
import ApiKeyPanel from './components/ApiKeyPanel.jsx';
import Header from './components/Header.jsx';
import { AlertIcon, RefreshIcon } from './components/icons.jsx';
import ProcessingPanel from './components/ProcessingPanel.jsx';
import ResultView from './components/ResultView.jsx';
import ScopeNotice from './components/ScopeNotice.jsx';
import UploadPanel, { isAcceptedVideo } from './components/UploadPanel.jsx';
import ViolationTypes from './components/ViolationTypes.jsx';
import { normalizeJob } from './review.js';

const KEY_STORAGE = 'cash-control.api-key';
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 10 * 60 * 1000;
const MAX_POLL_FAILURES = 8;

const FAQ_ITEMS = [
  {
    question: 'Что именно проверяет сервис?',
    answer:
      'Сервис анализирует запись с камеры над кассой и ищет визуально наблюдаемые признаки потенциальных нарушений кассовой дисциплины: люди у кассы, наличие посторонних предметов, действия, мешающие работе кассира, и другие события, которые затем проверяются человеком.',
  },
  {
    question: 'Какие форматы файлов поддерживаются?',
    answer:
      'Основной формат — .mov, но также принимаются .mp4, .m4v, .avi и .mkv. Важно, чтобы файл был видеозаписью с камеры над кассой и не превышал лимит по размеру.',
  },
  {
    question: 'Нужен ли интернет для анализа?',
    answer:
      'Нет. Анализ выполняется локально на сервере: модель детекции загружается один раз и работает без облачных AI-сервисов. Интернет нужен только для первичного скачивания модели и для доступа к UI, если вы открываете сервис удалённо.',
  },
  {
    question: 'Где хранится API-ключ?',
    answer:
      'Ключ хранится в браузере локально, в этом устройстве, и используется только для отправки запросов к API. Его можно сохранить на время сессии или удалить при необходимости.',
  },
  {
    question: 'Этот результат — доказательство или решение?',
    answer:
      'Результат является подсказкой для проверки человеком, а не окончательным юридическим или дисциплинарным заключением. Сервис показывает подозрительные фрагменты и помогает быстрее находить проблемные участки записи.',
  },
  {
    question: 'Что происходит с загруженным видео?',
    answer:
      'По умолчанию файлы удаляются после обработки. Сервис сохраняет только результаты задачи и её метаданные до истечения времени хранения, а исходная запись не используется для публичного хранения.',
  },
];

function storedKey() {
  const fallback = import.meta.env.VITE_DEFAULT_API_KEY || '';
  try {
    return localStorage.getItem(KEY_STORAGE) || fallback;
  } catch {
    return fallback;
  }
}

function jobFromHash() {
  const match = window.location.hash.match(/job=([\w-]+)/);
  return match ? match[1] : null;
}

// Сообщение для пользователя + вид ошибки, от которого зависит способ восстановления
function describe(error) {
  if (error?.status === 401) return { kind: 'auth', message: 'API-ключ не принят сервисом. Укажите верный ключ.' };
  if (error?.status === 404)
    return { kind: 'missing', message: 'Задача не найдена: результат мог быть удалён по истечении срока хранения.' };
  if (error?.status === 413) return { kind: 'upload', message: 'Файл слишком большой для загрузки на сервер.' };
  if (error?.status === 0) return { kind: 'network', message: error.message };
  return { kind: 'other', message: error?.message || 'Неизвестная ошибка' };
}

function FailedPanel({ error, onReset, onRetry, retryLabel, apiKey, onKey }) {
  return (
    <div className="card overflow-hidden" role="alert">
      <div className="h-1 bg-danger-500" aria-hidden />
      <div className="flex items-start gap-4 p-6 sm:p-8">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-danger-50 text-danger-600">
          <AlertIcon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold text-ink-950">
            {error.kind === 'auth' ? 'Нужен действующий API-ключ' : 'Не удалось получить результат'}
          </h2>
          <p className="mt-1 text-sm text-ink-600">{error.message}</p>
          {error.kind === 'auth' && (
            <div className="mt-4">
              <ApiKeyPanel apiKey={apiKey} onChange={onKey} startEditing />
            </div>
          )}
          <div className="mt-5 flex flex-wrap gap-3">
            {onRetry && error.kind !== 'auth' && (
              <button type="button" className="btn-primary" onClick={onRetry}>
                <RefreshIcon className="h-4 w-4" /> {retryLabel}
              </button>
            )}
            <button type="button" className="btn-secondary" onClick={onReset}>
              Загрузить другое видео
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [apiKey, setApiKey] = useState(storedKey);
  const [health, setHealth] = useState(undefined);
  const [file, setFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [jobId, setJobId] = useState(jobFromHash);
  const [phase, setPhase] = useState(() => (jobFromHash() ? 'processing' : 'idle'));
  const [job, setJob] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null); // { kind, message }
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const uploadController = useRef(null);

  useEffect(() => {
    getHealth()
      .then((data) => setHealth(data || null))
      .catch(() => setHealth(null));
  }, []);

  // Ссылка вида #job=<id> открывает результат ранее запущенной задачи
  useEffect(() => {
    const onHashChange = () => {
      const fromHash = jobFromHash();
      if (!fromHash || fromHash === jobId) return;
      setFile(null);
      setJob(null);
      setError(null);
      setJobId(fromHash);
      setStartedAt(Date.now());
      setPhase('processing');
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [jobId]);

  // Локальная ссылка на выбранный файл — чтобы проигрывать видео и переходить по таймкодам
  useEffect(() => {
    if (!file) {
      setVideoUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setVideoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Отменяем незавершённую загрузку при закрытии страницы/размонтировании
  useEffect(() => () => uploadController.current?.abort(), []);

  const saveKey = (value) => {
    setApiKey(value);
    try {
      localStorage.setItem(KEY_STORAGE, value);
    } catch {
      // приватный режим браузера — ключ живёт до перезагрузки
    }
  };

  // После исправления ключа продолжаем с того места, где остановились
  const saveKeyAndResume = (value) => {
    saveKey(value);
    setError(null);
    if (jobId) {
      setStartedAt(Date.now());
      setPhase('processing');
    } else {
      setPhase('idle');
    }
  };

  const chooseFile = (candidate) => {
    if (!isAcceptedVideo(candidate)) {
      setError({ kind: 'file', message: 'Поддерживаются видеофайлы .mov (а также .mp4, .m4v, .avi, .mkv)' });
      return;
    }
    if (!candidate.size) {
      setError({ kind: 'file', message: 'Файл пустой — выберите другую запись.' });
      return;
    }
    setError(null);
    setFile(candidate);
  };

  const start = async () => {
    if (!apiKey) {
      setError({ kind: 'auth', message: 'Укажите API-ключ' });
      return;
    }
    if (!file) return;
    const controller = new AbortController();
    uploadController.current = controller;
    setError(null);
    setJob(null);
    setUploadProgress(0);
    setStartedAt(Date.now());
    setPhase('uploading');
    try {
      const { job_id: newJobId } = await uploadVideo(file, apiKey, setUploadProgress, controller.signal);
      setJobId(newJobId);
      window.history.replaceState(null, '', `#job=${newJobId}`);
      setPhase('processing');
    } catch (uploadError) {
      if (uploadError?.name === 'AbortError') {
        setError({ kind: 'cancelled', message: 'Загрузка отменена.' });
      } else {
        setError(describe(uploadError));
      }
      setPhase('idle');
    } finally {
      uploadController.current = null;
    }
  };

  const cancelUpload = () => uploadController.current?.abort();

  // Опрос статуса задачи
  useEffect(() => {
    if (phase !== 'processing' || !jobId) return undefined;
    let cancelled = false;
    let timer;
    let failures = 0;
    const controller = new AbortController();
    const begin = Date.now();

    const fail = (failure) => {
      setError(failure);
      setPhase('failed');
    };

    const poll = async () => {
      try {
        const raw = await getJob(jobId, apiKey, controller.signal);
        if (cancelled) return;
        failures = 0;
        if (!raw || typeof raw !== 'object' || !raw.status) {
          fail({ kind: 'poll', message: 'Сервис вернул ответ в неожиданном формате.' });
          return;
        }
        const data = normalizeJob(raw);
        setJob(data);
        if (data.status === 'done') {
          setPhase('done');
          return;
        }
        if (data.status === 'failed') {
          fail({ kind: 'job', message: data.error || 'Обработка завершилась ошибкой' });
          return;
        }
      } catch (pollError) {
        if (cancelled || pollError.name === 'AbortError') return;
        if (pollError.status === 401 || pollError.status === 404) {
          fail(describe(pollError));
          return;
        }
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) {
          fail({ ...describe(pollError), kind: 'poll' });
          return;
        }
      }
      if (Date.now() - begin > POLL_TIMEOUT_MS) {
        fail({ kind: 'poll', message: 'Превышено время ожидания результата. Попробуйте обновить статус позже.' });
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [phase, jobId, apiKey]);

  const reset = () => {
    uploadController.current?.abort();
    setPhase('idle');
    setJob(null);
    setJobId(null);
    setFile(null);
    setError(null);
    window.history.replaceState(null, '', window.location.pathname);
  };

  const resumePolling = () => {
    setError(null);
    setStartedAt(Date.now());
    setPhase('processing');
  };

  // Повтор: при сбое опроса — ещё раз запросить статус; при ошибке обработки — загрузить файл заново
  const retry =
    error?.kind === 'poll' || error?.kind === 'network'
      ? { action: jobId ? resumePolling : null, label: 'Обновить статус' }
      : { action: file ? start : null, label: 'Повторить загрузку' };

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-control bg-white px-4 py-2 text-sm font-semibold text-brand-700 shadow-overlay focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        К содержимому
      </a>
      <Header health={health} />

      <main id="main" className="mx-auto w-full max-w-content flex-1 space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {phase === 'idle' && (
          <>
            <div className="max-w-3xl">
              <p className="eyebrow">Кассовый контроль</p>
              <h2 id="upload-heading" className="page-title mt-1">
                Проверка видеозаписи
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-ink-600">
                Загрузите запись с камеры над кассой. Сервис найдёт визуально наблюдаемые признаки возможных
                нарушений и покажет таймкод, кадры и пункт норматива — для решения проверяющего.
              </p>
            </div>
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
              <div className="space-y-6">
                <section className="card divide-y divide-ink-200" aria-labelledby="upload-heading">
                  <div className="p-5 sm:p-6">
                    <ApiKeyPanel apiKey={apiKey} onChange={saveKey} />
                  </div>
                  <div className="p-5 sm:p-6">
                    <UploadPanel
                      file={file}
                      onFile={chooseFile}
                      onSubmit={start}
                      disabled={!apiKey}
                      error={error?.message}
                    />
                  </div>
                </section>
                <ViolationTypes apiKey={apiKey} />

                <section className="card" aria-labelledby="faq-heading">
                  <div className="border-b border-ink-200 px-5 py-4 sm:px-6">
                    <p className="eyebrow">FAQ</p>
                    <h3 id="faq-heading" className="mt-1 text-lg font-semibold text-ink-950">
                      Частые вопросы
                    </h3>
                  </div>
                  <div className="divide-y divide-ink-200">
                    {FAQ_ITEMS.map(({ question, answer }) => (
                      <details key={question} className="group px-5 py-4 sm:px-6">
                        <summary className="list-none cursor-pointer select-none text-sm font-medium text-ink-900 marker:content-none">
                          <span className="flex items-center justify-between gap-4">
                            <span>{question}</span>
                            <span className="text-base text-ink-500 transition-transform duration-150 group-open:rotate-45">
                              +
                            </span>
                          </span>
                        </summary>
                        <p className="mt-3 pr-8 text-sm leading-relaxed text-ink-600">{answer}</p>
                      </details>
                    ))}
                  </div>
                </section>
              </div>
              <div className="lg:sticky lg:top-24">
                <ScopeNotice />
              </div>
            </div>
          </>
        )}

        {(phase === 'uploading' || phase === 'processing') && (
          <ProcessingPanel
            phase={phase}
            uploadProgress={uploadProgress}
            job={job}
            startedAt={startedAt}
            fileName={file?.name || job?.filename}
            onCancel={cancelUpload}
          />
        )}

        {phase === 'done' && job && <ResultView job={job} videoUrl={videoUrl} onReset={reset} />}

        {phase === 'failed' && error && (
          <FailedPanel
            error={error}
            onReset={reset}
            onRetry={retry.action}
            retryLabel={retry.label}
            apiKey={apiKey}
            onKey={saveKeyAndResume}
          />
        )}
      </main>

      <footer className="app-chrome mt-8 border-t border-ink-200 bg-white">
        <div className="mx-auto flex max-w-content flex-col gap-3 px-4 py-5 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex min-w-0 items-start gap-3">
            <span className="shrink-0 font-semibold text-ink-800">Fintruism</span>
            <span>
              Результат — подсказка для проверки человеком, не юридическое и не дисциплинарное заключение · модели
              работают локально · лица не распознаются
            </span>
          </div>
          <a href="/docs" className="link shrink-0">
            Документация API
          </a>
        </div>
      </footer>
    </div>
  );
}
