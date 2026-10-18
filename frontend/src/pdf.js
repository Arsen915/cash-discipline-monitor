// PDF-документы по результату: протокол ручной проверки и отчёт анализа.
// pdfmake подгружается по требованию (тяжёлый модуль) и работает офлайн: шрифт Roboto
// с кириллицей встроен в сборку.

import { formatDuration, formatTimecode } from './format.js';
import { cleanRequirement, DECISIONS, requirementKind, splitDescription, typeLimit } from './review.js';

const INK = '#171C1A';
const MUTED = '#727A76';
const BORDER = '#E2E5E3';
const BRAND = '#147545';

const NOTICE =
  'Результат сервиса — подсказка для проверки человеком, а не юридическое или дисциплинарное заключение. ' +
  'Выводы о данных, которых нет на видео (проводки, сверки), сервисом не делаются.';

let loader = null;
function loadPdfMake() {
  if (!loader) {
    loader = Promise.all([import('pdfmake/build/pdfmake.js'), import('pdfmake/build/vfs_fonts.js')]).then(
      ([pdfMakeModule, fontsModule]) => {
        const pdfMake = pdfMakeModule.default || pdfMakeModule;
        const vfs = fontsModule.default || fontsModule;
        pdfMake.vfs = vfs.pdfMake?.vfs || vfs;
        return pdfMake;
      },
    );
  }
  return loader;
}

const dateTime = (date = new Date()) =>
  date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

const verdictLabel = (verdict) =>
  verdict === 'violation' ? 'Обнаружены признаки возможных нарушений' : 'Нарушение не обнаружено';

const decisionLabel = (value) => DECISIONS.find((option) => option.value === value)?.short || 'Не проверено';

const range = (violation) =>
  violation.end_sec > violation.timecode_sec
    ? `${formatTimecode(violation.timecode_sec)}–${formatTimecode(violation.end_sec)}`
    : formatTimecode(violation.timecode_sec);

// Таблица «параметр — значение» без внешних рамок
function keyValue(rows) {
  return {
    table: {
      widths: [150, '*'],
      body: rows.map(([label, value]) => [
        { text: label, color: MUTED },
        { text: value == null || value === '' ? '—' : String(value), color: INK },
      ]),
    },
    layout: {
      hLineWidth: (i, node) => (i === 0 || i === node.table.body.length ? 0 : 0.5),
      vLineWidth: () => 0,
      hLineColor: () => BORDER,
      paddingLeft: () => 0,
      paddingTop: () => 4,
      paddingBottom: () => 4,
    },
    margin: [0, 0, 0, 12],
  };
}

function header(title, subtitle) {
  return [
    {
      columns: [
        { text: [{ text: 'Fintruism', bold: true, color: INK }, { text: '  ·  Кассовый контроль', color: MUTED }], fontSize: 10 },
        { text: `Сформировано: ${dateTime()}`, alignment: 'right', fontSize: 8, color: MUTED },
      ],
    },
    { canvas: [{ type: 'line', x1: 0, y1: 6, x2: 515, y2: 6, lineWidth: 1.5, lineColor: BRAND }], margin: [0, 0, 0, 14] },
    { text: title, fontSize: 17, bold: true, color: INK },
    subtitle ? { text: subtitle, fontSize: 9, color: MUTED, margin: [0, 3, 0, 0] } : null,
    noticeBox(),
  ].filter(Boolean);
}

function noticeBox() {
  return {
    table: { widths: ['*'], body: [[{ text: NOTICE, fontSize: 8.5, color: '#3B423F', margin: [8, 6, 8, 6] }]] },
    layout: { hLineColor: () => BORDER, vLineColor: () => BORDER, hLineWidth: () => 0.5, vLineWidth: () => 0.5, fillColor: () => '#F6F7F6' },
    margin: [0, 12, 0, 16],
  };
}

function baseDoc(content, title) {
  return {
    pageSize: 'A4',
    pageMargins: [40, 40, 40, 48],
    info: { title, author: 'Fintruism', subject: 'Кассовый контроль' },
    defaultStyle: { font: 'Roboto', fontSize: 9.5, lineHeight: 1.25, color: INK },
    styles: {
      h2: { fontSize: 12, bold: true, color: INK, margin: [0, 10, 0, 6] },
      h3: { fontSize: 10.5, bold: true, color: INK, margin: [0, 0, 0, 2] },
      label: { fontSize: 7.5, bold: true, color: MUTED, characterSpacing: 0.4, margin: [0, 6, 0, 2] },
      th: { fontSize: 8, bold: true, color: MUTED },
    },
    footer: (page, pages) => ({
      columns: [
        { text: 'Fintruism · подсказка для проверяющего, не заключение', fontSize: 7.5, color: MUTED },
        { text: `${page} / ${pages}`, alignment: 'right', fontSize: 7.5, color: MUTED },
      ],
      margin: [40, 16, 40, 0],
    }),
    content,
  };
}

function jobRows(job) {
  return [
    ['Идентификатор задачи', job.job_id],
    ['Файл', job.filename],
    ['Вердикт сервиса', verdictLabel(job.verdict)],
    ['Длительность записи', job.video?.duration_sec ? formatDuration(job.video.duration_sec) : null],
    ['Время обработки', job.processing_time_sec ? formatDuration(job.processing_time_sec) : null],
  ];
}

const tableLayout = {
  hLineWidth: (i, node) => (i === 0 || i === node.table.body.length ? 0.8 : 0.5),
  vLineWidth: () => 0,
  hLineColor: () => BORDER,
  fillColor: (row) => (row === 0 ? '#F6F7F6' : null),
  paddingTop: () => 5,
  paddingBottom: () => 5,
};

async function save(doc, filename) {
  const pdfMake = await loadPdfMake();
  pdfMake.createPdf(doc).download(filename);
}

// ---- Протокол ручной проверки ----
export function downloadProtocolPdf({ job, review, keys, outside }) {
  const rows = job.violations.map((violation, index) => {
    const entry = review[keys[index]] || {};
    return [
      { text: String(index + 1) },
      {
        stack: [
          { text: violation.type, bold: true },
          violation.code ? { text: violation.code, fontSize: 7.5, color: MUTED } : null,
          outside[index] ? { text: 'Требует данных вне видео', fontSize: 7.5, color: MUTED } : null,
        ].filter(Boolean),
      },
      { text: range(violation) },
      { text: violation.rule ? violation.rule.clause : '—' },
      { text: decisionLabel(entry.decision), bold: Boolean(entry.decision) },
      { text: entry.comment || '—', color: entry.comment ? INK : MUTED },
    ];
  });

  const content = [
    ...header('Протокол ручной проверки видеозаписи кассы'),
    keyValue(jobRows(job)),
    { text: 'Решения проверяющего', style: 'h2' },
    {
      table: {
        headerRows: 1,
        widths: [16, '*', 62, 50, 70, 110],
        body: [
          ['№', 'Признак', 'Таймкод', 'Норматив', 'Решение', 'Комментарий'].map((text) => ({ text, style: 'th' })),
          ...rows,
        ],
      },
      layout: tableLayout,
      fontSize: 8.5,
    },
    {
      text: 'Итоговое решение принимает проверяющий. Решения в протоколе внесены вручную в интерфейсе сервиса.',
      fontSize: 8,
      color: MUTED,
      margin: [0, 8, 0, 28],
    },
    {
      columns: ['Проверяющий (ФИО)', 'Подпись', 'Дата'].map((label) => ({
        stack: [
          { canvas: [{ type: 'line', x1: 0, y1: 0, x2: 150, y2: 0, lineWidth: 0.5, lineColor: MUTED }] },
          { text: label, fontSize: 7.5, color: MUTED, margin: [0, 3, 0, 0] },
        ],
      })),
      columnGap: 22,
      unbreakable: true,
    },
  ];

  return save(baseDoc(content, 'Протокол проверки'), `protocol_${job.job_id}.pdf`);
}

// ---- Отчёт анализа (ответ API в читаемом виде) ----
export function downloadReportPdf(job) {
  const video = job.video || {};
  const analysis = job.analysis || {};
  const content = [
    ...header('Отчёт анализа видеозаписи', 'Содержимое ответа API сервиса в читаемом виде'),
    { text: 'Сводка', style: 'h2' },
    keyValue([
      ...jobRows(job),
      ['Найдено признаков', String(job.violations.length)],
    ]),
    { text: 'Параметры записи и анализа', style: 'h2' },
    keyValue([
      ['Разрешение', video.width && video.height ? `${video.width} × ${video.height}` : null],
      ['Частота кадров', video.fps ? `${video.fps} кадр/с` : null],
      ['Кодек', video.codec],
      ['Кадров в записи', video.frames_total],
      ['Проанализировано кадров', video.frames_analyzed],
      ['Шаг выборки', video.sampling_step_sec ? `${video.sampling_step_sec} с` : null],
      ['Модель детекции', analysis.detector],
      ['Отброшено событий ниже порога', analysis.events_below_threshold],
    ]),
  ];

  if (!job.violations.length) {
    content.push({
      text: 'Визуально наблюдаемых признаков из перечня сервиса на записи не найдено. Это не подтверждает отсутствие нарушений, которые по видео установить нельзя (проводки, сверки, документы).',
      color: '#3B423F',
    });
  }

  job.violations.forEach((violation, index) => {
    const { observed, checks } = splitDescription(violation.description);
    const limit = typeLimit(violation.code);
    const rule = violation.rule;
    const block = [
      { text: `${index + 1}. ${violation.type}`, style: 'h3', margin: [0, 14, 0, 2] },
      {
        text: [
          violation.code ? `${violation.code}  ·  ` : '',
          `Таймкод ${range(violation)}`,
          violation.confidence != null ? `  ·  Уверенность модели ${Math.round(violation.confidence * 100)}%` : '',
        ].join(''),
        fontSize: 8,
        color: MUTED,
      },
      { text: 'ЧТО ВИДНО НА ЗАПИСИ', style: 'label' },
      { text: observed || 'Описание не передано сервисом.' },
    ];
    if (checks.length || limit) {
      block.push(
        { text: 'ЧТО ПОДТВЕРДИТЬ ЧЕЛОВЕКУ', style: 'label' },
        { ul: [...checks, ...(limit ? [limit] : [])], margin: [0, 0, 0, 2] },
      );
    }
    if (rule) {
      block.push(
        { text: `ВОЗМОЖНОЕ НОРМАТИВНОЕ ОСНОВАНИЕ · ${rule.clause}`, style: 'label' },
        { text: rule.document, bold: true },
        { text: rule.act, fontSize: 8, color: MUTED },
        {
          text: requirementKind(rule.requirement) === 'quote' ? rule.requirement : cleanRequirement(rule.requirement),
          italics: true,
          margin: [8, 3, 0, 0],
        },
        rule.url ? { text: rule.url, link: rule.url, color: BRAND, fontSize: 8, margin: [0, 2, 0, 0] } : null,
      );
    }
    if (violation.evidence_frames.length) {
      block.push(
        { text: 'КАДРЫ-ДОКАЗАТЕЛЬСТВА', style: 'label' },
        {
          columns: violation.evidence_frames.slice(0, 3).map((frame) => ({
            width: 165,
            stack: [
              { image: `data:image/jpeg;base64,${frame.image_base64}`, fit: [165, 100] },
              { text: formatTimecode(frame.timestamp_sec), fontSize: 7.5, color: MUTED, margin: [0, 2, 0, 0] },
            ],
          })),
          columnGap: 10,
        },
      );
    }
    content.push({ stack: block.filter(Boolean), unbreakable: false });
  });

  return save(baseDoc(content, 'Отчёт анализа'), `report_${job.job_id}.pdf`);
}
