// Границы вывода и ручная проверка.
//
// Два принципа ТЗ (раздел 7), которые интерфейс обязан соблюдать:
// 1. Сервис не утверждает, что обнаружил нарушение, если для вывода нужны данные, которых
//    нет на видео (корректность проводки, системная сверка и т. п.).
// 2. Результат — подсказка для проверки человеком, а не юридическое/дисциплинарное заключение.

// Что по видео установить нельзя — показывается рядом с каждым результатом
export const OUT_OF_SCOPE = [
  'корректность проводок и записей в учётной системе (АБИС)',
  'результаты системной сверки и остатки по кассе',
  'суммы, номиналы и подлинность банкнот',
  'содержание документов, подписи и препроводительные ведомости',
  'личность и полномочия людей в кадре (лица не распознаются)',
];

// Что именно по видео не устанавливается для каждого типа — проверяющий решает сам.
// Формулировки соответствуют ограничениям, описанным в README проекта.
const TYPE_LIMITS = {
  WORKPLACE_ABANDONED:
    'Завершена ли операция в системе до ухода кассира, по видео не устанавливается — вывод сделан по присутствию клиента у стойки.',
  WORKPLACE_LEFT:
    'Был ли это согласованный перерыв, замена кассира или закрытие кассы, по видео не устанавливается — сверьте с графиком смены.',
  CASH_UNATTENDED:
    'Сервис видит только изменение вида стола; что это за предметы и являются ли они ценностями, определяет проверяющий.',
  UNAUTHORIZED_PERSON:
    'Полномочия человека (кассовый или контролирующий работник) по видео не устанавливаются; лица не распознаются.',
  MOBILE_PHONE:
    'Есть ли у устройства функция фото- и видеофиксации, по кадру может быть не видно; похожие предметы иногда принимаются за телефон.',
  PERSONAL_BELONGINGS:
    'Чья это сумка — личная или инкассаторская, принятая по документу, — по видео не устанавливается.',
  CAMERA_OBSTRUCTION:
    'Причину потери изображения (перекрытие объектива или технический сбой) по видео можно не различить.',
};

export function typeLimit(code) {
  return TYPE_LIMITS[code] || null;
}

// Признаки того, что вывод опирается на данные, которых нет в кадре.
// Такой пункт интерфейс не выдаёт за обнаруженное нарушение.
const INVISIBLE_DATA = /проводк|сверк|АБИС|учётн\w* систем|учетн\w* систем|бухгалтер|остат\w* по (касс|систем)|журнал\w* (операций|учёта|учета)/i;

export function requiresInvisibleData(violation) {
  const text = `${violation?.type || ''} ${violation?.description || ''}`;
  return INVISIBLE_DATA.test(text);
}

// Описание от сервиса: наблюдение + просьбы проверить вручную + «Основание: …».
// Разделяем, чтобы проверяющий отдельно видел, что ему нужно подтвердить.
const CHECK_SENTENCE = /(провер(ьте|ить)|подтверд(ите|ить)|убедитесь|уточните)/i;

export function splitDescription(text = '') {
  const marker = text.lastIndexOf(' Основание:');
  const body = (marker > 0 ? text.slice(0, marker) : text).trim();
  // делим по точке + пробел + заглавная буква, чтобы не резать «00:06.0» и «0.80»
  const sentences = body.split(/(?<=[.!?])\s+(?=[А-ЯЁA-Z«])/u).filter(Boolean);
  const observed = [];
  const checks = [];
  sentences.forEach((sentence) => {
    const separator = sentence.search(/;\s/);
    if (CHECK_SENTENCE.test(sentence) && separator > 0 && !CHECK_SENTENCE.test(sentence.slice(0, separator))) {
      // «правило…; проверьте…» → первая часть — наблюдение, вторая — проверка
      observed.push(`${sentence.slice(0, separator)}.`);
      const rest = sentence.slice(separator + 1).trim();
      checks.push(rest.charAt(0).toUpperCase() + rest.slice(1));
    } else if (CHECK_SENTENCE.test(sentence)) {
      checks.push(sentence);
    } else {
      observed.push(sentence);
    }
  });
  return { observed: observed.join(' '), checks };
}

// Требование из каталога: дословная цитата («…») или пересказ пункта
export function requirementKind(requirement = '') {
  const trimmed = requirement.trim();
  if (/\(пересказ[^)]*\)\.?$/i.test(trimmed)) return 'paraphrase';
  if (trimmed.startsWith('«')) return 'quote';
  return 'paraphrase';
}

export function cleanRequirement(requirement = '') {
  return requirement.replace(/\s*\(пересказ[^)]*\)\.?\s*$/i, '.').replace(/\.\.$/, '.');
}

// ---- Решения проверяющего: хранятся только в этом браузере ----

export const DECISIONS = [
  { value: 'confirmed', label: 'Подтверждаю по видео', short: 'Подтверждено' },
  { value: 'rejected', label: 'Не подтверждаю', short: 'Отклонено' },
  { value: 'needs_info', label: 'Нужны данные вне видео', short: 'Нужна доп. проверка' },
];

const REVIEW_PREFIX = 'cash-control.review.';

export function loadReview(jobId) {
  try {
    const raw = localStorage.getItem(REVIEW_PREFIX + jobId);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export function saveReview(jobId, review) {
  try {
    localStorage.setItem(REVIEW_PREFIX + jobId, JSON.stringify(review));
    return true;
  } catch {
    return false;
  }
}

// Ключ решения — индекс + код + таймкод: стабилен для одного результата задачи
export function violationKey(violation, index) {
  return `${index}:${violation.code || 'event'}:${violation.timecode_sec}`;
}

// ---- Нормализация ответа API: интерфейс не должен падать на неожиданных данных ----

const toNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

export function normalizeJob(job) {
  if (!job || typeof job !== 'object') return job;
  const violations = Array.isArray(job.violations) ? job.violations : [];
  return {
    ...job,
    violations: violations
      .filter((item) => item && typeof item === 'object')
      .map((item) => {
        const timecode = toNumber(item.timecode_sec);
        return {
          ...item,
          type: typeof item.type === 'string' && item.type ? item.type : 'Тип не указан',
          description: typeof item.description === 'string' ? item.description : '',
          timecode_sec: timecode,
          start_sec: item.start_sec == null ? undefined : toNumber(item.start_sec, timecode),
          end_sec: item.end_sec == null ? undefined : toNumber(item.end_sec, timecode),
          confidence: item.confidence == null ? undefined : toNumber(item.confidence),
          rule: item.rule && typeof item.rule === 'object' ? item.rule : null,
          evidence_frames: (Array.isArray(item.evidence_frames) ? item.evidence_frames : [])
            .filter((frame) => frame && typeof frame.image_base64 === 'string' && frame.image_base64)
            .map((frame) => ({ ...frame, timestamp_sec: toNumber(frame.timestamp_sec, timecode) })),
        };
      }),
  };
}
