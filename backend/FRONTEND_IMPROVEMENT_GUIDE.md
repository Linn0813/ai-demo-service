# 🎨 前端改进实施指南

## 📋 改进目标

1. **改进布局**：从左右分栏改为垂直流程式布局
2. **增强进度展示**：显示详细的执行阶段和进度
3. **实时结果展示**：测试用例逐步显示，不用等待全部完成
4. **任务关联**：与后端任务系统完美结合

---

## 🔧 后端已完成的改进

### 1. 任务管理器增强

✅ 已添加 `update_progress()` 方法
- 支持更新任务进度信息
- 包含阶段、百分比、当前项等信息

✅ 已添加 `update_partial_result()` 方法
- 支持返回部分结果
- 前端可以实时展示已生成的测试用例

✅ 已更新 `TaskStatusResponse` Schema
- 新增 `partial_result` 字段
- 支持返回部分结果

---

## 🎯 前端需要实现的改进

### 1. 新的布局结构

```vue
<template>
  <div class="test-case-generate-page">
    <!-- 配置区域（可折叠） -->
    <el-card class="config-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>生成配置</span>
          <el-button 
            text 
            @click="configCollapsed = !configCollapsed"
          >
            <el-icon>
              <component :is="configCollapsed ? 'ArrowDown' : 'ArrowUp'" />
            </el-icon>
          </el-button>
        </div>
      </template>
      <div v-show="!configCollapsed">
        <!-- 原有的配置表单 -->
      </div>
    </el-card>

    <!-- 任务进度区域 -->
    <el-card class="progress-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Loading /></el-icon>
          <span>任务进度</span>
        </div>
      </template>
      
      <!-- 进度展示组件 -->
      <TaskProgress 
        :task-id="taskId"
        :status="taskStatus"
        :progress="taskProgress"
      />
    </el-card>

    <!-- 结果展示区域 -->
    <el-card class="result-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>生成结果</span>
          <el-tag v-if="resultMeta">
            {{ resultMeta.processed_function_points }}/{{ resultMeta.total_function_points }} 功能点
          </el-tag>
        </div>
      </template>
      
      <!-- 实时结果展示 -->
      <ResultDisplay 
        :result="result"
        :partial-result="partialResult"
        :loading="isTaskRunning"
      />
    </el-card>
  </div>
</template>
```

### 2. 任务进度组件

创建 `components/TaskProgress.vue`:

```vue
<template>
  <div class="task-progress">
    <!-- 总体进度条 -->
    <div class="overall-progress">
      <el-progress 
        :percentage="progressPercentage" 
        :status="progressStatus"
        :stroke-width="16"
        :format="formatProgress"
      />
      <div class="progress-info">
        <span class="status-text">{{ statusText }}</span>
        <span class="progress-text">{{ progressText }}</span>
      </div>
    </div>

    <!-- 阶段列表 -->
    <div class="stage-list" v-if="stages.length > 0">
      <div 
        v-for="(stage, index) in stages" 
        :key="index"
        :class="['stage-item', `stage-${stage.status}`]"
      >
        <el-icon class="stage-icon">
          <component :is="getStageIcon(stage.status)" />
        </el-icon>
        <div class="stage-content">
          <div class="stage-name">{{ stage.name }}</div>
          <div class="stage-message" v-if="stage.message">
            {{ stage.message }}
          </div>
        </div>
        <div class="stage-progress" v-if="stage.progress !== undefined">
          {{ stage.current }}/{{ stage.total }}
        </div>
      </div>
    </div>

    <!-- 当前处理项 -->
    <div class="current-item" v-if="currentItem">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <span>正在处理: <strong>{{ currentItem }}</strong></span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, CircleCheck, CircleClose, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  taskId: String,
  status: String,
  progress: Object
})

const progressPercentage = computed(() => {
  return props.progress?.progress || 0
})

const progressStatus = computed(() => {
  if (props.status === 'completed') return 'success'
  if (props.status === 'failed') return 'exception'
  if (props.status === 'running') return 'warning'
  return undefined
})

const statusText = computed(() => {
  const map = {
    'pending': '任务已排队',
    'running': '任务执行中',
    'completed': '任务完成',
    'failed': '任务失败'
  }
  return map[props.status] || '未知状态'
})

const progressText = computed(() => {
  if (props.progress?.current && props.progress?.total) {
    return `${props.progress.current}/${props.progress.total}`
  }
  return `${progressPercentage.value}%`
})

const formatProgress = (percentage) => {
  return `${percentage}%`
}

const stages = computed(() => {
  const stageMap = {
    'extracting_modules': { name: '提取功能模块', order: 1 },
    'generating_test_cases': { name: '生成测试用例', order: 2 },
    'validating': { name: '验证和修复', order: 3 }
  }
  
  const currentStage = props.progress?.stage
  const result = []
  
  for (const [key, info] of Object.entries(stageMap)) {
    let status = 'waiting'
    if (key === currentStage) {
      status = props.status === 'running' ? 'running' : 'completed'
    } else if (stageMap[key].order < stageMap[currentStage]?.order) {
      status = 'completed'
    }
    
    result.push({
      ...info,
      status,
      message: key === currentStage ? props.progress?.message : null,
      current: props.progress?.current,
      total: props.progress?.total
    })
  }
  
  return result
})

const currentItem = computed(() => {
  return props.progress?.current_item
})

const getStageIcon = (status) => {
  if (status === 'completed') return CircleCheck
  if (status === 'failed') return CircleClose
  if (status === 'running') return Loading
  return Clock
}
</script>

<style scoped>
.task-progress {
  padding: 16px;
}

.overall-progress {
  margin-bottom: 24px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 14px;
}

.status-text {
  font-weight: 500;
}

.stage-list {
  margin-top: 16px;
}

.stage-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  background: #f5f7fa;
}

.stage-item.stage-completed {
  background: #f0f9ff;
  color: #67c23a;
}

.stage-item.stage-running {
  background: #fef0e6;
  color: #e6a23c;
}

.stage-icon {
  margin-right: 12px;
  font-size: 20px;
}

.stage-content {
  flex: 1;
}

.stage-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.stage-message {
  font-size: 12px;
  color: #909399;
}

.stage-progress {
  font-size: 14px;
  color: #606266;
}

.current-item {
  margin-top: 16px;
  padding: 12px;
  background: #ecf5ff;
  border-radius: 4px;
  display: flex;
  align-items: center;
}

.loading-icon {
  margin-right: 8px;
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
```

### 3. 实时结果展示组件

创建 `components/ResultDisplay.vue`:

```vue
<template>
  <div class="result-display">
    <!-- 功能点列表 -->
    <div 
      v-for="fp in functionPoints" 
      :key="fp.id"
      class="function-point-card"
    >
      <div class="fp-header">
        <el-icon class="fp-icon">
          <component :is="getFpIcon(fp.status)" />
        </el-icon>
        <span class="fp-name">{{ fp.name }}</span>
        <el-tag :type="getStatusType(fp.status)" size="small">
          {{ fp.statusText }}
        </el-tag>
        <span class="fp-count" v-if="fp.testCases.length > 0">
          {{ fp.testCases.length }} 个用例
        </span>
      </div>
      
      <!-- 测试用例列表 -->
      <div class="test-cases-list">
        <div 
          v-for="tc in fp.testCases" 
          :key="tc.id || tc.case_name"
          class="test-case-item"
        >
          <el-icon class="tc-icon"><Document /></el-icon>
          <span class="tc-name">{{ tc.case_name }}</span>
        </div>
        <div v-if="fp.status === 'generating'" class="loading-item">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <span>生成中...</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <el-empty 
      v-if="functionPoints.length === 0 && !loading"
      description="暂无结果"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, CircleCheck, CircleClose, Document } from '@element-plus/icons-vue'

const props = defineProps({
  result: Object,
  partialResult: Object,
  loading: Boolean
})

const functionPoints = computed(() => {
  // 合并完整结果和部分结果
  const result = props.result || {}
  const partial = props.partialResult || {}
  
  const byFunctionPoint = partial.by_function_point || result.by_function_point || {}
  const testCases = partial.test_cases || result.test_cases || []
  
  // 按功能点分组
  const fpMap = {}
  
  for (const [fpName, cases] of Object.entries(byFunctionPoint)) {
    fpMap[fpName] = {
      name: fpName,
      testCases: cases || [],
      status: 'completed',
      statusText: '已完成'
    }
  }
  
  // 如果有部分结果，标记正在处理的功能点
  if (partial.meta?.current_function_point) {
    const currentFp = partial.meta.current_function_point
    if (!fpMap[currentFp]) {
      fpMap[currentFp] = {
        name: currentFp,
        testCases: [],
        status: 'generating',
        statusText: '生成中'
      }
    } else {
      fpMap[currentFp].status = 'generating'
      fpMap[currentFp].statusText = '生成中'
    }
  }
  
  return Object.values(fpMap)
})

const getFpIcon = (status) => {
  if (status === 'completed') return CircleCheck
  if (status === 'generating') return Loading
  return CircleClose
}

const getStatusType = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'generating') return 'warning'
  return 'danger'
}
</script>

<style scoped>
.result-display {
  padding: 16px;
}

.function-point-card {
  margin-bottom: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.fp-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.fp-icon {
  margin-right: 8px;
  font-size: 18px;
}

.fp-name {
  flex: 1;
  font-weight: 500;
}

.fp-count {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}

.test-cases-list {
  padding: 12px 16px;
}

.test-case-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f5f7fa;
}

.test-case-item:last-child {
  border-bottom: none;
}

.tc-icon {
  margin-right: 8px;
  color: #909399;
}

.tc-name {
  flex: 1;
}

.loading-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  color: #e6a23c;
}

.loading-icon {
  margin-right: 8px;
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
```

### 4. 更新轮询逻辑

在 `AITestCaseGenerate.vue` 中更新 `fetchTaskStatus`:

```javascript
const fetchTaskStatus = async () => {
  if (!taskId.value) return
  
  try {
    const response = await aiApi.getTaskStatus(taskId.value)
    const taskData = response.data.data
    
    // 更新任务状态
    taskStatus.value = taskData.status
    
    // 更新进度信息
    if (taskData.progress) {
      taskProgress.value = taskData.progress
    }
    
    // 更新部分结果（实时展示）
    if (taskData.partial_result) {
      partialResult.value = taskData.partial_result
    }
    
    // 如果完成，应用最终结果
    if (taskData.status === 'completed') {
      if (taskData.result) {
        result.value = taskData.result
      }
      stopPolling()
      ElMessage.success('测试用例生成完成')
    } else if (taskData.status === 'failed') {
      stopPolling()
      ElMessage.error(taskData.error || '任务执行失败')
    }
  } catch (error) {
    console.error('获取任务状态失败:', error)
    ElMessage.error('获取任务状态失败')
    stopPolling()
  }
}
```

---

## 📝 实施检查清单

- [ ] 创建 `TaskProgress.vue` 组件
- [ ] 创建 `ResultDisplay.vue` 组件
- [ ] 更新 `AITestCaseGenerate.vue` 布局
- [ ] 更新轮询逻辑，支持部分结果
- [ ] 测试进度展示功能
- [ ] 测试实时结果展示功能
- [ ] 优化样式和动画

---

## 🎯 预期效果

1. **用户体验提升**：
   - 可以看到任务的具体执行阶段
   - 测试用例逐步显示，不用等待全部完成
   - 清晰的进度反馈

2. **任务关联**：
   - 与后端任务系统完美结合
   - 支持查看任务详情和进度

3. **布局优化**：
   - 垂直流程式布局，更符合用户操作习惯
   - 配置可折叠，节省空间
   - 结果实时展示，提升体验

