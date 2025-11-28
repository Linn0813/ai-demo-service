import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        // 开发环境代理目标，可通过 VITE_BACKEND_URL 环境变量覆盖
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8113',
        changeOrigin: true,
        secure: false,
        ws: true,
        // 配置超时和重试
        timeout: 30000,
        // 可选：重写路径，如果后端不需要 /api 前缀
        // rewrite: (path) => path.replace(/^\/api/, '')
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('代理错误:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('发送请求到后端:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('收到后端响应:', proxyRes.statusCode, req.url);
          });
        }
      }
    }
  }
})
