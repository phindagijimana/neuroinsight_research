import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: false, // If 3000 is taken, try 3001, 3002, etc.
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:3001',
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
});
