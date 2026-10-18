import { useState } from 'react';
import { CheckCircleIcon, KeyIcon } from './icons.jsx';

export default function ApiKeyPanel({ apiKey, onChange, startEditing = false }) {
  const [editing, setEditing] = useState(startEditing || !apiKey);
  const [draft, setDraft] = useState(apiKey);
  const [visible, setVisible] = useState(false);

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-brand-50 text-brand-700">
            <CheckCircleIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink-900">API-ключ задан</p>
            <p className="font-mono text-xs text-ink-500">X-API-Key · •••• {apiKey.slice(-4)}</p>
          </div>
        </div>
        <button type="button" className="btn-secondary h-9 px-3" onClick={() => setEditing(true)}>
          Изменить
        </button>
      </div>
    );
  }

  const save = (event) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;
    onChange(value);
    setEditing(false);
  };

  return (
    <form onSubmit={save}>
      <label htmlFor="api-key" className="field-label flex items-center gap-2">
        <KeyIcon className="h-4 w-4 text-ink-500" />
        API-ключ <span className="font-normal text-ink-500">(заголовок X-API-Key)</span>
      </label>
      <p id="api-key-hint" className="field-hint mt-1">
        Ключ выдаёт команда сервиса; он хранится только в этом браузере.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          id="api-key"
          className="input font-mono"
          type={visible ? 'text' : 'password'}
          autoComplete="off"
          aria-describedby="api-key-hint"
          placeholder="Вставьте ключ, выданный командой"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            className="btn-secondary flex-1 sm:flex-none"
            aria-pressed={visible}
            onClick={() => setVisible((v) => !v)}
          >
            {visible ? 'Скрыть' : 'Показать'}
          </button>
          <button type="submit" className="btn-primary flex-1 sm:flex-none" disabled={!draft.trim()}>
            Сохранить
          </button>
        </div>
      </div>
    </form>
  );
}
