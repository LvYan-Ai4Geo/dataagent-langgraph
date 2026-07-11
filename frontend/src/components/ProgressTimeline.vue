<template>
  <div class="timeline">
    <div v-if="!steps.length" class="empty">
      <span class="thinking-dot"></span>
      <span>正在分析问题…</span>
    </div>
    <transition-group name="step" tag="div" class="step-list">
      <div v-for="(s, i) in steps" :key="s.step" class="step" :class="s.status">
        <span class="dot"></span>
        <span class="label">{{ s.step }}</span>
        <span class="status-tag">{{ statusText(s.status) }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
defineProps({
  steps: { type: Array, default: () => [] } // [{ step, status }]
})

function statusText(status) {
  return { running: '执行中', success: '完成', error: '失败' }[status] || status
}
</script>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.empty {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-dim);
  font-size: 13px;
  opacity: 0.8;
}

.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 8px var(--primary);
  animation: blink 1s ease-in-out infinite;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(10, 20, 44, 0.4);
}

/* transition-group 进入/离开动画 */
.step-enter-active {
  transition: all 0.3s ease;
}
.step-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.step.running .dot {
  background: var(--running);
  box-shadow: 0 0 8px var(--running);
  animation: blink 1s ease-in-out infinite;
}

.step.success .dot {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
}

.step.error .dot {
  background: var(--error);
  box-shadow: 0 0 6px var(--error);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.label {
  flex: 1;
  color: var(--text);
}

.status-tag {
  font-size: 11px;
  color: var(--text-dim);
}

.step.success .status-tag { color: var(--success); }
.step.error .status-tag { color: var(--error); }
.step.running .status-tag { color: var(--running); }
</style>
