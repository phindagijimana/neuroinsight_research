import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendPort = env.BACKEND_PORT || env.API_PORT || '3051';
  const backendTarget = `http://localhost:${backendPort}`;

  return {
    plugins: [react()],
    server: {
      port: 3000,
      strictPort: false,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: {
            // Split heavy neuroimaging libraries into their own chunk
            // Only downloaded when user opens the Viewer page
            'niivue-vendor': ['@niivue/niivue'],
            // Split React + ReactDOM into a shared vendor chunk
            'react-vendor': ['react', 'react-dom'],
          },
        },
      },
    },
  };
});
