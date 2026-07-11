<template>
  <div class="result-table-wrap">
    <div v-if="sql" class="sql-block">
      <div class="sql-label">生成的 SQL</div>
      <pre class="sql-code">{{ sql }}</pre>
    </div>
    <div v-if="rows && rows.length" class="table-scroll">
      <table class="result-table">
        <thead>
          <tr>
            <th v-for="col in columns" :key="col">{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="i">
            <td v-for="col in columns" :key="col">{{ row[col] }}</td>
          </tr>
        </tbody>
      </table>
      <div class="row-count">共 {{ rows.length }} 行</div>
    </div>
    <div v-else-if="rows && !rows.length" class="empty-result">查询结果为空</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sql: { type: String, default: '' },
  rows: { type: Array, default: () => null }
})

// 从首行提取列名，保证顺序
const columns = computed(() => {
  if (!props.rows || !props.rows.length) return []
  return Object.keys(props.rows[0])
})
</script>

<style scoped>
.result-table-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sql-block {
  background: rgba(8, 16, 36, 0.7);
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  overflow: hidden;
}

.sql-label {
  padding: 8px 14px;
  font-size: 12px;
  color: var(--primary-soft);
  background: rgba(76, 201, 240, 0.08);
  border-bottom: 1px solid var(--panel-border);
}

.sql-code {
  padding: 14px;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 13px;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.table-scroll {
  overflow: auto;
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  background: rgba(8, 16, 36, 0.5);
}

.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.result-table th,
.result-table td {
  padding: 9px 14px;
  text-align: left;
  border-bottom: 1px solid rgba(124, 224, 255, 0.08);
  white-space: nowrap;
}

.result-table th {
  position: sticky;
  top: 0;
  color: var(--primary-soft);
  background: rgba(15, 28, 60, 0.9);
  font-weight: 600;
}

.result-table tbody tr:hover {
  background: rgba(76, 201, 240, 0.06);
}

.result-table td {
  color: var(--text);
}

.row-count {
  padding: 8px 14px;
  font-size: 12px;
  color: var(--text-dim);
  text-align: right;
}

.empty-result {
  color: var(--text-dim);
  font-size: 13px;
  padding: 12px;
}
</style>
