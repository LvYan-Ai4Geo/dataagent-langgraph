<template>
  <div class="chat-input">
    <input
      v-model="text"
      class="input"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      @keydown.enter="send"
    />
    <button class="send-btn" :disabled="disabled || !text.trim()" @click="send">
      {{ disabled ? '执行中…' : '发送' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '输入你的自然语言问题，例如：统计华北地区中男生的销售总额' }
})

const emit = defineEmits(['send'])
const text = ref('')

function send() {
  const q = text.value.trim()
  if (!q || props.disabled) return
  emit('send', q)
  text.value = ''
}
</script>

<style scoped>
.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  backdrop-filter: blur(10px);
}

.input {
  flex: 1;
  padding: 12px 16px;
  font-size: 14px;
  color: var(--text);
  background: rgba(10, 20, 44, 0.6);
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(76, 201, 240, 0.15);
}

.input::placeholder {
  color: var(--text-dim);
}

.send-btn {
  padding: 0 26px;
  font-size: 14px;
  font-weight: 600;
  color: var(--bg-deep);
  background: linear-gradient(120deg, var(--primary-soft), var(--primary));
  border: none;
  border-radius: 10px;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
