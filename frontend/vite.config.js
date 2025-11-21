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
        // 可选：重写路径，如果后端不需要 /api 前缀
        // rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
