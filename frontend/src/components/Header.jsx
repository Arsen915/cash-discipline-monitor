// Фирменный знак Fintruism: литера F и зелёный квадрат-«точка»
export function LogoMark({ className = 'h-8 w-8' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="7" fill="#0E1211" />
      <path d="M10 8h13v4H14v3h7v4h-7v5h-4z" fill="#fff" />
      <rect x="19" y="20" width="4" height="4" fill="#1F8A52" />
    </svg>
  );
}

export default function Header({ health }) {
  // health: undefined — проверка идёт, null — сервис не ответил, объект — ответ /api/health
  const online = health?.status === 'ok';
  const offline = health !== undefined && !online;
  return (
    <header className="app-chrome sticky top-0 z-30 border-b border-ink-200 bg-white">
      <div className="mx-auto flex h-16 max-w-content items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <div className="flex shrink-0 items-center gap-2.5">
            <LogoMark />
            <span className="text-[17px] font-bold tracking-tight text-ink-950">Fintruism</span>
          </div>
          <span aria-hidden className="hidden h-6 w-px bg-ink-200 sm:block" />
          <div className="sr-only min-w-0 sm:not-sr-only">
            <h1 className="truncate text-sm font-semibold leading-tight text-ink-900">Кассовый контроль</h1>
            <p className="truncate text-xs text-ink-500">Визуальные признаки возможных нарушений кассовой дисциплины</p>
          </div>
        </div>
        <div
          role="status"
          className="flex shrink-0 items-center gap-2 rounded-control border border-ink-200 bg-ink-50 px-2.5 py-1.5 text-xs font-medium text-ink-700"
          title={health?.detector || ''}
        >
          <span
            aria-hidden
            className={`h-2 w-2 rounded-full ${online ? 'bg-success-500' : offline ? 'bg-danger-500' : 'bg-ink-400'}`}
          />
          <span className="sr-only sm:not-sr-only">
            {health === undefined
              ? 'Проверка связи…'
              : online
                ? 'Сервис доступен · анализ локально'
                : 'Сервис недоступен'}
          </span>
        </div>
      </div>
    </header>
  );
}
