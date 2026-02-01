import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Ensure headers are forwarded correctly
        headers: {
          'Connection': 'keep-alive',
        },
        // Configure proxy to preserve response headers
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // Forward all headers from backend response
            Object.keys(proxyRes.headers).forEach((key) => {
              res.setHeader(key, proxyRes.headers[key]);
            });
          });
        },
      },
    },
  },
});
