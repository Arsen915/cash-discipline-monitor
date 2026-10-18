// Клиент REST API сервиса. Все запросы к /api/v1 передают заголовок X-API-Key.

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function detailOf(body) {
  if (!body) return null;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join('; ');
  return null;
}

async function request(path, apiKey, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...(apiKey ? { 'X-API-Key': apiKey } : {}), ...(options.headers || {}) },
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('Сервис недоступен: проверьте подключение', 0);
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    // ответ без JSON
  }
  if (!response.ok) {
    throw new ApiError(detailOf(body) || `Ошибка сервиса (HTTP ${response.status})`, response.status);
  }
  return body;
}

// signal — AbortSignal для отмены загрузки пользователем
export function uploadVideo(file, apiKey, onProgress, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Загрузка отменена', 'AbortError'));
      return;
    }
    const xhr = new XMLHttpRequest();
    signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.onabort = () => reject(new DOMException('Загрузка отменена', 'AbortError'));
    xhr.open('POST', `${API_BASE}/api/v1/analyze`);
    xhr.setRequestHeader('X-API-Key', apiKey);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // ответ без JSON
      }
      if (xhr.status >= 200 && xhr.status < 300 && body?.job_id) {
        resolve(body);
      } else {
        reject(new ApiError(detailOf(body) || `Ошибка загрузки (HTTP ${xhr.status})`, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError('Сервис недоступен: проверьте подключение', 0));
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}

export const getJob = (jobId, apiKey, signal) =>
  request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, apiKey, { signal });

export const getViolationTypes = (apiKey) => request('/api/v1/violation-types', apiKey);

export const getHealth = () => request('/api/health');
