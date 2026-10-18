// Готовые результаты сохраняются в IndexedDB этого браузера: ссылка #job=<id> открывает результат,
// даже если сервис его уже не хранит (истёк срок хранения, перезапуск без постоянного диска).
// Кадры-доказательства весят сотни КБ, поэтому IndexedDB, а не localStorage.

const DB_NAME = 'fintruism-results';
const STORE = 'jobs';
const MAX_ITEMS = 20;

function open() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB недоступен'));
      return;
    }
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE, { keyPath: 'job_id' });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function run(mode, action) {
  return open().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const result = action(tx.objectStore(STORE));
        tx.oncomplete = () => {
          db.close();
          resolve(result?.result);
        };
        tx.onerror = () => {
          db.close();
          reject(tx.error);
        };
      }),
  );
}

export async function loadCachedResult(jobId) {
  try {
    const entry = await run('readonly', (store) => store.get(jobId));
    return entry?.job || null;
  } catch {
    return null;
  }
}

export async function cacheResult(job) {
  if (!job?.job_id || job.status !== 'done') return;
  try {
    await run('readwrite', (store) => store.put({ job_id: job.job_id, saved_at: Date.now(), job }));
    // Храним только последние результаты
    const all = (await run('readonly', (store) => store.getAll())) || [];
    if (all.length > MAX_ITEMS) {
      const stale = all.sort((a, b) => b.saved_at - a.saved_at).slice(MAX_ITEMS);
      await run('readwrite', (store) => stale.forEach((entry) => store.delete(entry.job_id)));
    }
  } catch {
    // нет места или приватный режим — результат останется доступен только на сервере
  }
}
