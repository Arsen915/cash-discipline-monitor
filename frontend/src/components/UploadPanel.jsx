import { useRef, useState } from 'react';
import { formatBytes } from '../format.js';
import { AlertIcon, UploadIcon, VideoIcon } from './icons.jsx';

const ACCEPTED = ['.mov', '.mp4', '.m4v', '.avi', '.mkv'];

export function isAcceptedVideo(file) {
  const name = file?.name?.toLowerCase() || '';
  return ACCEPTED.some((extension) => name.endsWith(extension));
}

export default function UploadPanel({ file, onFile, onSubmit, disabled, error }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const pick = (candidate) => {
    if (candidate) onFile(candidate);
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="field-label">Видеозапись</p>
        <p className="field-hint mt-1">Запись с камеры над кассой: .mov, .mp4, .m4v, .avi или .mkv.</p>
      </div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Выбрать видеофайл для проверки (.mov) или перетащить его сюда"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          pick(event.dataTransfer.files?.[0]);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-panel border border-dashed px-6 py-10 text-center transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 sm:py-12 ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-ink-300 bg-ink-50 hover:border-brand-500 hover:bg-white'
        }`}
      >
        <div className="flex h-11 w-11 items-center justify-center rounded-control border border-ink-200 bg-white text-brand-700">
          <UploadIcon className="h-5 w-5" />
        </div>
        <p className="mt-4 text-sm font-semibold text-ink-900">Перетащите видеозапись кассы сюда</p>
        <p className="mt-1 text-sm text-ink-500">
          или <span className="font-medium text-brand-700 underline underline-offset-2">выберите файл</span> · формат
          .mov (также .mp4)
        </p>
        <input
          ref={inputRef}
          type="file"
          tabIndex={-1}
          aria-hidden
          accept={`${ACCEPTED.join(',')},video/quicktime,video/mp4`}
          className="hidden"
          onChange={(event) => {
            pick(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
      </div>

      {file && (
        <div className="flex flex-col gap-3 rounded-control border border-ink-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between sm:pl-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-ink-100 text-ink-700">
              <VideoIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink-900">{file.name}</p>
              <p className="num text-xs text-ink-500">{formatBytes(file.size)}</p>
            </div>
          </div>
          <div className="flex flex-col items-stretch gap-1 sm:items-end">
            <button type="button" className="btn-primary" onClick={onSubmit} disabled={disabled}>
              Запустить анализ
            </button>
            {disabled && <span className="text-xs text-ink-500">Сначала сохраните API-ключ</span>}
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="notice-danger">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}
