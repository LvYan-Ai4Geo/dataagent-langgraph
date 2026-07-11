<template>
  <div class="app-root">
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
// 根组件：仅承载路由出口与过渡动画
</script>

<style scoped>
.app-root {
  height: 100%;
  width: 100%;
}
</style>
