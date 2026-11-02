import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({mode})=>{
  const env=loadEnv(mode,process.cwd(),'');
  const target=(env.VITE_API_PROXY_TARGET||'http://127.0.0.1:8000').replace(/\/$/,'');
  return {
    plugins: [react(), tailwindcss()],
    server: { proxy: { '/api': target, '/ws': { target: target.replace(/^http/,'ws'), ws: true } } },
    build: { rollupOptions: { output: { manualChunks: { charts: ['recharts'], motion: ['framer-motion'] } } } },
  };
});
