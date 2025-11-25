<template>
  <div class="ai-module-layout">
    <!-- 侧边栏 -->
    <el-aside width="240px" class="sidebar">
      <div class="sidebar-header">
        <h3>
          <el-icon><Cpu /></el-icon>
          AI 智能测试
        </h3>
        <p class="sidebar-subtitle">AI 驱动的智能测试助手</p>
      </div>

      <el-menu
        :default-active="activeMenuIndex"
        class="sidebar-menu"
        router
      >
        <el-menu-item index="/ai/test-case-generator">
          <el-icon><MagicStick /></el-icon>
          <span>测试用例生成</span>
        </el-menu-item>
        <el-menu-item index="/ai/knowledge-base">
          <el-icon><Reading /></el-icon>
          <span>知识库问答</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-main class="main-content">
      <el-breadcrumb class="breadcrumb" separator="/">
        <el-breadcrumb-item to="/ai">AI 智能测试</el-breadcrumb-item>
        <template v-if="route.name === 'AITestCaseGenerate'">
          <el-breadcrumb-item>AI 测试用例生成</el-breadcrumb-item>
        </template>
        <template v-else-if="route.name === 'KnowledgeBase'">
          <el-breadcrumb-item>知识库问答</el-breadcrumb-item>
        </template>
      </el-breadcrumb>
      <router-view />
    </el-main>
  </div>
</template>

<script setup>
import { Cpu, MagicStick, Reading } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenuIndex = computed(() => route.path)
</script>

<style scoped>
.ai-module-layout {
  display: flex;
  height: calc(100vh - 56px);
  background-color: #f5f6fa;
}

.sidebar {
  background-color: #ffffff;
  border-right: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
  width: 240px;
}

.sidebar-header {
  padding: 20px 18px 16px;
  border-bottom: 1px solid #e6e6e6;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #2c3e50;
}

.sidebar-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: #909399;
}

.sidebar-menu {
  border-right: none;
  flex: 1;
}

.sidebar-menu .el-menu-item {
  height: 48px;
  line-height: 48px;
}

.main-content {
  flex: 1;
  padding: 24px 28px;
  background: linear-gradient(135deg, #f8fbff 0%, #f5f6fa 100%);
  overflow-y: auto;
}

.breadcrumb {
  margin-bottom: 16px;
}

@media screen and (max-width: 1024px) {
  .ai-module-layout {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    flex-direction: row;
    border-right: none;
    border-bottom: 1px solid #e6e6e6;
  }
  .sidebar-header {
    padding: 12px 16px;
    border-bottom: none;
    border-right: 1px solid #e6e6e6;
  }
  .sidebar-menu {
    flex: 1;
  }
  .main-content {
    padding: 16px;
  }
}
</style>
