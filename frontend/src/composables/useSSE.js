// 基于 fetch + ReadableStream 的 SSE 客户端封装。
//
// 后端 /api/query 返回 text/event-stream，每帧形如 "data: {...}\n\n"。
// 这里用 fetch 流式读取并按 \n\n 分帧解析，逐帧回调。
//
// 回调约定：
//   onProgress(step, status) —— 节点进度（running/success/error）
//   onResult(sql, data)      —— SQL 执行结果
//   onError(message)         —— 异常
//   onDone()                 —— 流结束
export function useSSE() {
  let controller = null

  /**
   * 发起一次查询请求。
   * @param {Object} payload { query, threadId }
   * @param {Object} handlers { onProgress, onResult, onError, onDone }
   */
  async function streamQuery(payload, handlers) {
    const { onProgress, onResult, onError, onDone } = handlers
    controller = new AbortController()

    try {
      const resp = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: payload.query, thread_id: payload.threadId }),
        signal: controller.signal
      })

      if (!resp.ok) {
        onError && onError(`HTTP ${resp.status}`)
        onDone && onDone()
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // 按 SSE 帧分隔符 \n\n 切分
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          handleFrame(frame, { onProgress, onResult, onError })
        }
      }
      // 处理尾部残余
      if (buffer.trim()) {
        handleFrame(buffer, { onProgress, onResult, onError })
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        onError && onError(e.message || String(e))
      }
    } finally {
      onDone && onDone()
    }
  }

  function handleFrame(frame, { onProgress, onResult, onError }) {
    // 解析 "data: {...}" 行
    const lines = frame.split('\n')
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const jsonStr = trimmed.slice(5).trim()
      if (!jsonStr) continue
      let data
      try {
        data = JSON.parse(jsonStr)
      } catch {
        continue
      }
      if (data.type === 'progress') {
        onProgress && onProgress(data.step, data.status)
      } else if (data.type === 'result') {
        onResult && onResult(data.sql, data.data)
      } else if (data.type === 'error') {
        onError && onError(data.message)
      }
    }
  }

  function abort() {
    controller && controller.abort()
  }

  return { streamQuery, abort }
}
