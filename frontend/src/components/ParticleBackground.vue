<template>
  <canvas ref="canvasRef" class="particle-bg"></canvas>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'

const props = defineProps({
  // 粒子数量（会按屏幕宽度自适应）
  count: { type: Number, default: 90 },
  // 粒子颜色
  color: { type: String, default: '120, 220, 255' },
  // 连线最大距离
  linkDistance: { type: Number, default: 130 },
  // 鼠标吸附半径
  mouseRadius: { type: Number, default: 150 },
  // 粒子大小范围
  minSize: { type: Number, default: 1 },
  maxSize: { type: Number, default: 2.6 },
  // 速度
  speed: { type: Number, default: 0.35 },
  // 是否启用鼠标交互
  interactive: { type: Boolean, default: true }
})

const canvasRef = ref(null)
let ctx = null
let rafId = null
let width = 0
let height = 0
let particles = []
const mouse = { x: null, y: null }

function resize() {
  const dpr = window.devicePixelRatio || 1
  width = canvasRef.value.clientWidth
  height = canvasRef.value.clientHeight
  canvasRef.value.width = width * dpr
  canvasRef.value.height = height * dpr
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.scale(dpr, dpr)
}

function makeParticles() {
  // 按屏幕宽度自适应粒子数量，保证不同尺寸下的视觉密度
  const n = Math.round(props.count * Math.min(1, width / 1400))
  particles = []
  for (let i = 0; i < n; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * props.speed,
      vy: (Math.random() - 0.5) * props.speed,
      r: props.minSize + Math.random() * (props.maxSize - props.minSize)
    })
  }
}

function draw() {
  ctx.clearRect(0, 0, width, height)

  // 更新位置 + 鼠标吸附
  for (const p of particles) {
    if (props.interactive && mouse.x !== null) {
      const dx = p.x - mouse.x
      const dy = p.y - mouse.y
      const dist = Math.hypot(dx, dy)
      if (dist < props.mouseRadius && dist > 0) {
        // 在吸附范围内，向鼠标方向产生轻微拉力
        const force = (props.mouseRadius - dist) / props.mouseRadius
        p.vx += (dx / dist) * force * 0.08
        p.vy += (dy / dist) * force * 0.08
      }
    }
    // 阻尼，避免速度无限增大
    p.vx *= 0.99
    p.vy *= 0.99
    p.x += p.vx
    p.y += p.vy

    // 边界回弹
    if (p.x < 0 || p.x > width) p.vx *= -1
    if (p.y < 0 || p.y > height) p.vy *= -1
    p.x = Math.max(0, Math.min(width, p.x))
    p.y = Math.max(0, Math.min(height, p.y))
  }

  // 连线
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const a = particles[i]
      const b = particles[j]
      const dist = Math.hypot(a.x - b.x, a.y - b.y)
      if (dist < props.linkDistance) {
        const alpha = (1 - dist / props.linkDistance) * 0.5
        ctx.strokeStyle = `rgba(${props.color}, ${alpha})`
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.stroke()
      }
    }
  }

  // 粒子点
  for (const p of particles) {
    ctx.fillStyle = `rgba(${props.color}, 0.85)`
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fill()
  }

  rafId = requestAnimationFrame(draw)
}

function onMouseMove(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  mouse.x = e.clientX - rect.left
  mouse.y = e.clientY - rect.top
}

function onMouseLeave() {
  mouse.x = null
  mouse.y = null
}

function onResize() {
  resize()
  makeParticles()
}

onMounted(() => {
  ctx = canvasRef.value.getContext('2d')
  resize()
  makeParticles()
  if (props.interactive) {
    window.addEventListener('mousemove', onMouseMove)
    canvasRef.value.addEventListener('mouseleave', onMouseLeave)
  }
  window.addEventListener('resize', onResize)
  draw()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(rafId)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.particle-bg {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  z-index: 0;
}
</style>
