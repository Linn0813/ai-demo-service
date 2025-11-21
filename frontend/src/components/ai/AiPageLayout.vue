<template>
  <div class="ai-layout">
    <el-card shadow="never" class="ai-card">
      <div class="ai-header">
        <div class="ai-title-block">
          <h2 class="ai-title">
            <slot name="title">{{ title }}</slot>
          </h2>
          <p v-if="description" class="ai-description">{{ description }}</p>
        </div>
        <div class="ai-actions">
          <slot name="actions" />
        </div>
      </div>
      <div class="ai-content">
        <slot />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'

defineProps({
  title: {
    type: String,
    default: 'AI工具'
  },
  description: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.ai-layout {
  width: 100%;
  padding: 24px;
  box-sizing: border-box;
}

.ai-card {
  width: 100%;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.ai-title-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.ai-description {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.ai-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ai-content {
  width: 100%;
}

@media screen and (max-width: 768px) {
  .ai-layout {
    padding: 12px;
  }
  .ai-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .ai-actions {
    width: 100%;
  }
}
</style>
