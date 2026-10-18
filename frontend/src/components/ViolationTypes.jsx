import { useCallback, useEffect, useState } from 'react';
import { getViolationTypes } from '../api.js';
import { typeLimit } from '../review.js';
import { ChevronIcon, ExternalIcon, RefreshIcon, Spinner } from './icons.jsx';

export default function ViolationTypes({ apiKey }) {
  const [types, setTypes] = useState([]);
  const [status, setStatus] = useState('idle'); // idle | loading | ready | error
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(
    (signal) => {
      setStatus('loading');
      setError(null);
      getViolationTypes(apiKey)
        .then((items) => {
          if (signal.cancelled) return;
          setTypes(Array.isArray(items) ? items.filter((item) => item && item.code) : []);
          setStatus('ready');
        })
        .catch((loadError) => {
          if (signal.cancelled) return;
          setError(
            loadError?.status === 401 ? 'API-ключ не принят — перечень недоступен.' : loadError?.message || 'Ошибка загрузки',
          );
          setStatus('error');
        });
    },
    [apiKey],
  );

  useEffect(() => {
    if (!apiKey) {
      setStatus('idle');
      return undefined;
    }
    const signal = { cancelled: false };
    load(signal);
    return () => {
      signal.cancelled = true;
    };
  }, [apiKey, load]);

  if (status === 'idle') return null;

  return (
    <section className="card" aria-labelledby="types-heading">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="types-list"
        disabled={status !== 'ready'}
        className="flex w-full items-center justify-between gap-3 rounded-panel px-5 py-4 text-left transition-colors duration-150 hover:bg-ink-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500 disabled:cursor-default disabled:hover:bg-transparent"
      >
        <span>
          <span id="types-heading" className="section-title block">
            Что проверяет сервис
          </span>
          <span className="mt-0.5 block text-sm text-ink-500">
            {status === 'loading' && 'Загрузка перечня…'}
            {status === 'error' && error}
            {status === 'ready' &&
              (types.length
                ? `${types.length} типов визуальных признаков с привязкой к актам НБРК`
                : 'Перечень пуст')}
          </span>
        </span>
        {status === 'loading' ? (
          <Spinner className="h-5 w-5 text-ink-400" />
        ) : (
          status === 'ready' && (
            <ChevronIcon className={`h-5 w-5 shrink-0 text-ink-400 transition ${open ? 'rotate-90' : ''}`} />
          )
        )}
      </button>
      {status === 'error' && (
        <div className="px-5 pb-5">
          <button type="button" className="btn-secondary" onClick={() => load({ cancelled: false })}>
            <RefreshIcon className="h-4 w-4" /> Повторить
          </button>
        </div>
      )}
      {open && status === 'ready' && (
        <ul id="types-list" className="divide-y divide-ink-200 border-t border-ink-200">
          {types.map((item) => (
            <li key={item.code} className="px-5 py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <p className="text-sm font-semibold text-ink-900">{item.type}</p>
                <code className="font-mono text-2xs text-ink-500">{item.code}</code>
              </div>
              <p className="mt-1 text-sm leading-relaxed text-ink-600">{item.detects}</p>
              {typeLimit(item.code) && (
                <p className="mt-1 text-sm text-ink-500">
                  <span className="font-medium text-ink-600">Не устанавливается по видео: </span>
                  {typeLimit(item.code)}
                </p>
              )}
              {item.rule?.url && (
                <a
                  href={item.rule.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="link mt-2 inline-flex items-center gap-1 text-xs"
                >
                  {item.rule.clause} · {String(item.rule.act || '').replace(/^Утверждены /, '')}
                  <ExternalIcon className="h-3 w-3" />
                  <span className="sr-only">(откроется в новой вкладке)</span>
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
