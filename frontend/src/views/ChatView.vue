<template>
  <div class="chat">
    <ParticleBackground :count="55" :interactive="false" color="90, 170, 230" :link-distance="110" />

    <header class="header">
      <div class="brand">
        <span class="brand-icon">✦</span>
        <span class="brand-text">Data Agent · 自然语言2SQL</span>
      </div>
      <div class="session">
        <span class="session-label">会话</span>
        <span class="session-id">{{ shortId }}</span>
        <button class="reset-btn" @click="resetSession">重置</button>
      </div>
    </header>

    <main class="main">
      <div class="messages" ref="messagesRef">
        <div v-if="!rounds.length" class="welcome">
          <div class="welcome-icon">✦</div>
          <h2>开始你的第一次数据查询</h2>
          <p>用自然语言提问，Agent 会自动生成并执行 SQL。支持多轮追问（如“再按性别细分”）。</p>
          <div class="examples">
            <button class="example" @click="useExample('统计华北地区中男生的销售总额')">
              统计华北地区中男生的销售总额
            </button>
            <button class="example" @click="useExample('各会员等级的客户数量是多少')">
              各会员等级的客户数量是多少
            </button>
            <button class="example" @click="useExample('2025年1月每个大区的订单总额')">
              2025年1月每个大区的订单总额
            </button>
          </div>
        </div>

        <div v-for="(round, i) in rounds" :key="i" class="round">
          <div class="query-line">
            <span class="role-tag user">你</span>
            <span class="query-text">{{ round.query }}</span>
          </div>

          <div class="progress-line">
            <ProgressTimeline :steps="round.steps" />
          </div>

          <div v-if="round.error" class="error-line">
            <span class="role-tag err">错误</span>
            <span>{{ round.error }}</span>
          </div>

          <div v-if="round.result || round.done" class="result-line">
            <ResultTable :sql="round.sql" :rows="round.result" />
          </div>
        </div>
      </div>

      <div class="input-bar">
        <ChatInput :disabled="loading" @send="onSend" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import ParticleBackground from '../components/ParticleBackground.vue'
import ChatInput from '../components/ChatInput.vue'
import ProgressTimeline from '../components/ProgressTimeline.vue'
import ResultTable from '../components/ResultTable.vue'
import { useSSE } from '../composables/useSSE'

const router = useRouter()
const { streamQuery, abort } = useSSE()

const threadId = localStorage.getItem('thread_id') || ''
if (!threadId) {
  // 未登录直接访问，回登录页
  router.replace('/')
}

const rounds = ref([])        // [{ query, steps, result, sql, error, done }]
const loading = ref(false)
const messagesRef = ref(null)

const shortId = computed(() => threadId ? threadId.slice(0, 8) : '--------')

function resetSession() {
  abort()
  localStorage.removeItem('thread_id')
  router.replace('/')
}

function useExample(q) {
  onSend(q)
}

async function onSend(query) {
  const round = { query, steps: [], result: null, sql: '', error: '', done: false }
  rounds.value.push(round)
  // 通过响应式代理访问本轮数据：Vue3 必须经代理读取/写入才会触发重渲染，
  // 直接修改上面 push 的原始对象不会更新视图。
  const idx = rounds.value.length - 1
  const getRound = () => rounds.value[idx]
  loading.value = true
  await scrollToBottom()

  streamQuery(
    { query, threadId },
    {
      onProgress(step, status) {
        const cur = getRound()
        if (!cur) return
        // 更新对应步骤：running 时新增，success/error 时更新同名记录
        const existing = cur.steps.find(s => s.step === step)
        if (existing) {
          existing.status = status
        } else {
          cur.steps.push({ step, status })
        }
        scrollToBottom()
      },
      onResult(sql, data) {
        const cur = getRound()
        if (!cur) return
        cur.sql = sql
        cur.result = data
        scrollToBottom()
      },
      onError(message) {
        const cur = getRound()
        if (cur) cur.error = message
      },
      onDone() {
        const cur = getRound()
        if (cur) cur.done = true
        loading.value = false
        scrollToBottom()
      }
    }
  )
}

async function scrollToBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}
</script>

<style scoped>
.chat {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  background: var(--panel);
  border-bottom: 1px solid var(--panel-border);
  backdrop-filter: blur(10px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  color: var(--primary);
  font-size: 20px;
  text-shadow: 0 0 12px rgba(124, 224, 255, 0.6);
}

.brand-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}

.session {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-dim);
}

.session-label {
  opacity: 0.7;
}

.session-id {
  font-family: "JetBrains Mono", Consolas, monospace;
  color: var(--primary-soft);
  background: rgba(76, 201, 240, 0.08);
  padding: 2px 8px;
  border-radius: 6px;
}

.reset-btn {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-dim);
  background: transparent;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.reset-btn:hover {
  color: var(--error);
  border-color: var(--error);
}

.main {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 20px 28px 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

.welcome {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-dim);
}

.welcome-icon {
  font-size: 40px;
  color: var(--primary);
  margin-bottom: 16px;
  text-shadow: 0 0 20px rgba(124, 224, 255, 0.6);
  animation: pulse 3s ease-in-out infinite;
}

.welcome h2 {
  color: var(--text);
  font-size: 20px;
  margin-bottom: 10px;
}

.welcome p {
  font-size: 13px;
  line-height: 1.7;
  max-width: 480px;
  margin: 0 auto 28px;
}

.examples {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.example {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--primary-soft);
  background: rgba(76, 201, 240, 0.06);
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  transition: all 0.2s ease;
}

.example:hover {
  background: rgba(76, 201, 240, 0.15);
  border-color: var(--primary);
  transform: translateY(-1px);
}

.round {
  margin-bottom: 26px;
  padding: 18px 20px;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  backdrop-filter: blur(8px);
  animation: floatIn 0.4s ease both;
}

.query-line {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.role-tag {
  flex-shrink: 0;
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 6px;
  font-weight: 600;
}

.role-tag.user {
  color: var(--primary-soft);
  background: rgba(76, 201, 240, 0.12);
}

.role-tag.err {
  color: var(--error);
  background: rgba(255, 107, 138, 0.12);
}

.query-text {
  font-size: 14px;
  color: var(--text);
  line-height: 1.6;
}

.progress-line {
  margin: 12px 0;
}

.error-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 0;
  padding: 10px 14px;
  background: rgba(255, 107, 138, 0.08);
  border: 1px solid rgba(255, 107, 138, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--error);
}

.result-line {
  margin-top: 12px;
}

.input-bar {
  padding: 16px 0 18px;
}
</style>
