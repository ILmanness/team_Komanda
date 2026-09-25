import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    watch: { usePolling: true, interval: 1000 },
    proxy: {
      '/api/v1': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000', ws: true },
      '/openapi.json': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000' },
      '/api': {
        target: process.env.API_PROXY_TARGET || 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: { environment: 'jsdom' },
});
