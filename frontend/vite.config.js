import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置：
//   - 开发时通过 proxy 将 /api 请求转发到 FastAPI 后端（默认 http://127.0.0.1:8000），
//     避免 CORS 问题；
//   - 构建产物输出到 dist/，可由 FastAPI 静态托管或 nginx 部署。
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false
  }
})
