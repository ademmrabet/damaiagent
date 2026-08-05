import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

// Multi-page build: three independent React apps (landing, chat,
// dashboard) instead of one SPA with client-side routing. Chosen
// deliberately - the backend already serves each page as its own
// static file at its own FastAPI route ("/", "/chat", "/dashboard"),
// so this keeps that same simple model (no history-API fallback
// route needed in FastAPI, no risk of a hard refresh 404ing on a
// client-side-only route) while still getting real React components
// and a real build step per Adem's request.
export default defineConfig({
  plugins: [react()],
  root: __dirname,
  build: {
    outDir: resolve(__dirname, '../static'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        landing: resolve(__dirname, 'landing.html'),
        chat: resolve(__dirname, 'chat.html'),
        dashboard: resolve(__dirname, 'dashboard.html'),
      },
    },
  },
});
