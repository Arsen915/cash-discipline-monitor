// Небольшой набор SVG-иконок (без внешних зависимостей — UI работает офлайн)

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
  'aria-hidden': true,
};

export const ShieldIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);

export const UploadIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
  </svg>
);

export const VideoIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="3" y="6" width="13" height="12" rx="2" />
    <path d="M16 10l5-3v10l-5-3" />
  </svg>
);

export const KeyIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="8" cy="15" r="4" />
    <path d="M11 12l9-9M17 6l3 3M15 8l2 2" />
  </svg>
);

export const AlertIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 3l9.5 17h-19L12 3z" />
    <path d="M12 10v4M12 17.5v.01" />
  </svg>
);

export const CheckCircleIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8 12.5l2.5 2.5L16 9.5" />
  </svg>
);

export const PlayIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M7 5l12 7-12 7V5z" />
  </svg>
);

export const DocIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </svg>
);

export const ExternalIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M14 4h6v6M20 4l-9 9" />
    <path d="M18 14v4a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2h4" />
  </svg>
);

export const DownloadIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 4v12M7 11l5 5 5-5M4 20h16" />
  </svg>
);

export const CloseIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

export const ChevronIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M9 6l6 6-6 6" />
  </svg>
);

export const RefreshIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7" />
  </svg>
);

export const Spinner = ({ className = 'h-5 w-5' }) => (
  <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" aria-hidden>
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" fill="none" opacity="0.2" />
    <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
  </svg>
);

export const EyeIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
    <circle cx="12" cy="12" r="2.8" />
  </svg>
);

export const UserCheckIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5M15.5 11l2 2 4-4" />
  </svg>
);

export const ScopeIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4.5M12 16h.01" />
  </svg>
);

export const PrintIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M7 9V3h10v6M7 17H5a2 2 0 01-2-2v-4a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2h-2" />
    <rect x="7" y="14" width="10" height="7" rx="1" />
  </svg>
);

export const LinkIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" />
  </svg>
);

export const CheckIcon = (props) => (
  <svg {...base} strokeWidth={2.6} {...props}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);
