<template>
  <div class="login">
    <ParticleBackground :count="110" :interactive="true" />
    <div class="login-card">
      <div class="logo">✦</div>
      <h1 class="title">Data Agent</h1>
      <p class="subtitle">自然语言 · 数据 · 洞察</p>
      <p class="desc">用一句话查询你的数据，Agent 自动完成关键词抽取、多路召回、SQL 生成与执行。</p>
      <button class="enter-btn" @click="enter">
        <span>进入系统</span>
        <span class="arrow">→</span>
      </button>
      <p class="hint">点击进入将开启一个新的会话（多轮记忆）</p>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import ParticleBackground from '../components/ParticleBackground.vue'

const router = useRouter()

function enter() {
  // 生成随机 UUID 作为会话标识，启用后端短期会话记忆
  const threadId = crypto.randomUUID()
  localStorage.setItem('thread_id', threadId)
  router.push('/chat')
}
</script>

<style scoped>
.login {
  position: relative;
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 56px 64px;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  backdrop-filter: blur(14px);
  box-shadow: 0 10px 60px rgba(76, 201, 240, 0.15);
  animation: floatIn 0.9s ease both;
}

@keyframes floatIn {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}

.logo {
  font-size: 52px;
  color: var(--primary);
  text-shadow: 0 0 24px rgba(124, 224, 255, 0.7);
  margin-bottom: 12px;
  animation: pulse 3s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.12); opacity: 1; }
}

.title {
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 2px;
  background: linear-gradient(120deg, var(--primary-soft), var(--accent));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  margin-top: 10px;
  color: var(--text-dim);
  letter-spacing: 6px;
  font-size: 14px;
}

.desc {
  margin-top: 22px;
  color: var(--text-dim);
  font-size: 13px;
  line-height: 1.7;
  max-width: 360px;
}

.enter-btn {
  margin-top: 32px;
  padding: 13px 38px;
  font-size: 15px;
  color: var(--bg-deep);
  font-weight: 600;
  background: linear-gradient(120deg, var(--primary-soft), var(--primary));
  border: none;
  border-radius: 30px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  box-shadow: 0 6px 24px rgba(76, 201, 240, 0.35);
}

.enter-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 32px rgba(76, 201, 240, 0.5);
}

.enter-btn .arrow {
  transition: transform 0.25s ease;
}

.enter-btn:hover .arrow {
  transform: translateX(4px);
}

.hint {
  margin-top: 18px;
  font-size: 12px;
  color: var(--text-dim);
  opacity: 0.7;
}
</style>
