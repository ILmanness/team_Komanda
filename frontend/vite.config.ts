import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/openapi.json': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000' },
      '/api': {
        target: process.env.API_PROXY_TARGET || 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: { environment: 'jsdom' },
});
