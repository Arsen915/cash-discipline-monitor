import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// В dev-режиме запросы /api проксируются на бэкенд (по умолчанию localhost:8000)
const backend = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
