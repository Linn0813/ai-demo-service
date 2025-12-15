<template>
  <AiPageLayout
    title="AI 测试用例生成"
    description="基于本地大模型自动从需求文档提取功能点，并实时展示生成进度和结果。"
  >
    <template #actions>
      <el-space wrap>
        <el-button
          type="primary"
          :loading="isSubmitting || isTaskRunning"
          :disabled="isTaskRunning"
          @click="handleGenerate"
        >
          <el-icon class="icon-left"><MagicStick /></el-icon>
          生成测试用例
        </el-button>
        <el-button v-if="hasResult || taskId" :disabled="isTaskRunning" @click="handleReset">
          清空结果
        </el-button>
      </el-space>
    </template>

    <div class="ai-generator-page">
      <!-- 配置区域（可折叠） -->
      <el-card shadow="hover" class="section-card config-card">
            <template #header>
              <div class="card-header">
                <el-icon><Edit /></el-icon>
                <span>生成配置</span>
            <el-button 
              text 
              @click="configCollapsed = !configCollapsed"
              class="collapse-btn"
            >
              <el-icon>
                <component :is="configCollapsed ? 'ArrowDown' : 'ArrowUp'" />
              </el-icon>
            </el-button>
              </div>
            </template>
        <div v-show="!configCollapsed">

            <el-form
              ref="formRef"
              :model="form"
              label-position="top"
              class="config-form"
            >

              <el-form-item label="使用模型">
                <el-select
                  v-model="form.modelName"
                  placeholder="请选择模型"
                  filterable
                  :loading="modelsLoading"
                >
                  <el-option
                    v-for="model in modelList"
                    :key="model.name"
                    :label="`${model.name} (${model.model_id})`"
                    :value="model.model_id"
                  >
                    <div class="model-option">
                      <span class="model-name">{{ model.name }}</span>
                      <span class="model-desc">{{ model.description }}</span>
                      <el-tag v-if="model.recommended" type="success" size="small" effect="plain">
                        推荐
                      </el-tag>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>

              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="功能点上限">
                    <el-input-number
                      v-model="form.limit"
                      :min="1"
                      :max="50"
                      :controls="false"
                      placeholder="全部"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="最大并发">
                    <el-input-number
                      v-model="form.maxWorkers"
                      :min="1"
                      :max="8"
                      :controls="false"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-collapse v-model="advancedPanels">
                <el-collapse-item title="高级参数" name="advanced">
                  <el-row :gutter="12">
                    <el-col :span="12">
                      <el-form-item label="温度">
                        <el-input-number
                          v-model="form.temperature"
                          :step="0.1"
                          :min="0"
                          :max="1"
                          :precision="2"
                          :controls="false"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="最大 Token">
                        <el-input-number
                          v-model="form.maxTokens"
                          :min="512"
                          :max="8192"
                          :step="256"
                          :controls="false"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-form-item label="自定义服务地址">
                    <el-input
                      v-model="form.baseUrl"
                      placeholder="默认使用 http://localhost:11434"
                      clearable
                    />
                  </el-form-item>
                </el-collapse-item>
              </el-collapse>

              <el-form-item label="功能点确认">
                <el-switch
                  v-model="form.needConfirmFunctionPoints"
                  active-text="需要确认功能点与原文"
                  inactive-text="跳过确认，直接生成"
                  :active-value="true"
                  :inactive-value="false"
                />
                <div style="margin-top: 8px; font-size: 12px; color: var(--color-text-secondary);">
                  <el-icon><InfoFilled /></el-icon>
                  <span>开启后，提取功能模块后需要您确认和编辑功能点与原文匹配关系；关闭后将直接使用AI提取的结果生成测试用例</span>
                </div>
              </el-form-item>

              <el-form-item label="需求文档内容" class="requirement-item">
                <div style="margin-bottom: 8px;">
                  <el-upload
                    :auto-upload="false"
                    :show-file-list="false"
                    :on-change="handleWordFileChange"
                    accept=".docx"
                    :limit="1"
                  >
                    <template #trigger>
                      <el-button type="primary" size="small" :loading="wordUploading">
                        <el-icon><Upload /></el-icon>
                        上传Word文档
                      </el-button>
                    </template>
                  </el-upload>
                  <span v-if="wordFileName" style="margin-left: 12px; color: #606266; font-size: 12px;">
                    已选择: {{ wordFileName }}
                  </span>
                </div>
                <el-input
                  v-model="form.requirementDoc"
                  type="textarea"
                  :rows="18"
                  maxlength="50000"
                  show-word-limit
                  placeholder="请粘贴需求文档或功能描述，或上传Word文档（.docx格式），系统将自动识别功能点并生成测试用例。"
                />
              </el-form-item>
            </el-form>
        </div>
          </el-card>

      <!-- 任务进度区域（实时更新） -->
          <el-card
        v-if="taskId || extractTaskId"
            shadow="hover"
            class="section-card progress-card"
          >
            <template #header>
              <div class="card-header">
                <el-icon><Loading /></el-icon>
            <span>任务进度</span>
            <el-tag v-if="taskProgressInfo" type="info" size="small" style="margin-left: auto;">
              {{ taskProgressInfo.current || 0 }}/{{ taskProgressInfo.total || 0 }}
            </el-tag>
              </div>
            </template>

        <div class="task-progress-container">
          <!-- 总体进度条 -->
          <div class="overall-progress">
              <el-progress
              :percentage="progressPercentage"
                :status="progressStatus"
              :stroke-width="16"
              />
            <div class="progress-info">
              <span class="status-text">{{ taskStatusLabel }}</span>
              <span class="progress-text">{{ progressText }}</span>
            </div>
            </div>

          <!-- 执行阶段列表 -->
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
              <div class="stage-progress" v-if="stage.current !== undefined && stage.total !== undefined">
                {{ stage.current }}/{{ stage.total }}
              </div>
            </div>
          </div>

          <!-- 当前处理项 -->
          <div class="current-item" v-if="taskProgressInfo?.current_item">
            <el-icon class="loading-icon"><Loading /></el-icon>
            <span>正在处理: <strong>{{ taskProgressInfo.current_item }}</strong></span>
          </div>

          <!-- AI思考过程展示（类似对话界面） -->
          <div class="thinking-process" v-if="thinkingSteps.length > 0 || (extractTaskId && taskStatus === 'running')">
            <div class="thinking-header">
              <el-icon><ChatLineRound /></el-icon>
              <span>AI 思考过程</span>
              <el-tag v-if="thinkingSteps.length > 0" type="info" size="small" style="margin-left: 8px;">
                {{ thinkingSteps.length }} 个步骤
              </el-tag>
            </div>
            <div v-if="thinkingSteps.length === 0" class="thinking-empty">
              <el-icon><Loading /></el-icon>
              <span>正在分析文档，思考过程将实时显示...</span>
            </div>
            <div class="thinking-messages">
              <div
                v-for="(step, index) in thinkingSteps"
                :key="index"
                :class="['thinking-message', `step-${step.step}`]"
              >
                <div class="thinking-avatar">
                  <el-icon><Cpu /></el-icon>
                </div>
                <div class="thinking-content">
                  <div class="thinking-title">{{ step.content }}</div>
                  <div class="thinking-items">
                    <div
                      v-for="(item, itemIndex) in step.thinking"
                      :key="itemIndex"
                      class="thinking-item"
                    >
                      {{ item }}
                    </div>
                  </div>
                  <div v-if="step.result" class="thinking-result">
                    <el-collapse>
                      <el-collapse-item title="查看结果详情" :name="index">
                        <pre>{{ JSON.stringify(step.result, null, 2) }}</pre>
                      </el-collapse-item>
                    </el-collapse>
                  </div>
                </div>
                <div class="thinking-progress" v-if="step.progress !== undefined">
                  <el-progress
                    :percentage="step.progress"
                    :stroke-width="4"
                    :show-text="false"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 错误信息 -->
          <el-alert
            v-if="taskError"
            :title="taskError"
            type="error"
            :closable="false"
            show-icon
            class="error-alert"
          />
            </div>
          </el-card>

      <!-- 结果展示区域（动态加载） -->
      <el-card shadow="hover" class="section-card result-card">
            <template #header>
              <div class="card-header">
                <el-icon><Document /></el-icon>
                <span>生成结果</span>
            <el-tag v-if="resultMeta.total_function_points" type="info" size="small" style="margin-left: auto;">
              {{ resultMeta.processed_function_points }}/{{ resultMeta.total_function_points }} 功能点
            </el-tag>
              </div>
            </template>

            <div v-if="hasResult" class="result-summary">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="功能点总数">
                  {{ resultMeta.total_function_points }}
                </el-descriptions-item>
                <el-descriptions-item label="已处理功能点">
                  {{ resultMeta.processed_function_points }}
                </el-descriptions-item>
                <el-descriptions-item label="生成用例数">
                  {{ resultCases.length }}
                </el-descriptions-item>
                <el-descriptions-item label="自动修复或警告">
                  {{ resultMeta.total_warnings }}
                </el-descriptions-item>
                <el-descriptions-item label="平均质量评分">
                  <el-tag :type="getQualityTagType(averageQualityScore)" size="small">
                    {{ (averageQualityScore * 100).toFixed(1) }}%
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="有质量问题的用例">
                  <el-tag :type="problemCasesCount > 0 ? 'warning' : 'success'" size="small">
                    {{ problemCasesCount }} / {{ resultCases.length }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>

              <el-alert
                v-if="resultWarnings.length"
                title="自动检测到以下提示，请人工复核"
                type="warning"
                :closable="false"
                show-icon
                class="result-alert"
              >
                <template #default>
                  <ul class="warning-list">
                    <li v-for="(warning, index) in resultWarnings" :key="index">
                      {{ warning }}
                    </li>
                  </ul>
                </template>
              </el-alert>
            </div>

            <el-table
              v-if="resultCases.length"
              :data="resultCases"
              border
              stripe
              height="560"
              class="result-table"
            >
              <el-table-column type="index" label="序号" width="60" :index="(index) => index + 1" />
              <el-table-column prop="module_name" label="功能模块" min-width="150" :show-overflow-tooltip="true" />
              <el-table-column prop="sub_module" label="子功能点" min-width="120" :show-overflow-tooltip="true">
                <template #default="{ row }">
                  <span v-if="row.sub_module" class="sub-module-tag">{{ row.sub_module }}</span>
                  <span v-else class="sub-module-empty">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="case_name" label="用例名称" min-width="200" :show-overflow-tooltip="true" />
              <el-table-column label="前置条件" min-width="150" :show-overflow-tooltip="true">
                <template #default="{ row }">
                  <span class="precondition-text">{{ row.preconditions || '无' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="优先级" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="getPriorityTagType(row.priority)" size="small">
                    {{ getPriorityLabel(row.priority) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="步骤数" width="80" align="center">
                <template #default="{ row }">
                  <span>{{ Array.isArray(row.steps) ? row.steps.length : 0 }}</span>
                </template>
              </el-table-column>
              <el-table-column label="预期结果" min-width="260" :show-overflow-tooltip="true">
                <template #default="{ row }">
                  <span class="expected-text">{{ row.expected_result }}</span>
                </template>
              </el-table-column>
              <el-table-column type="expand" width="50">
                <template #default="{ row }">
                  <div class="expand-section">
                    <div class="expand-block" v-if="row.sub_module">
                      <h4>子功能点</h4>
                      <p>{{ row.sub_module }}</p>
                    </div>
                    <div class="expand-block">
                      <h4>前置条件</h4>
                      <p>{{ row.preconditions || '无' }}</p>
                    </div>
                    <div class="expand-block">
                      <h4>测试步骤</h4>
                      <ol>
                        <li v-for="(step, index) in row.steps" :key="index">
                          {{ step }}
                        </li>
                      </ol>
                    </div>
                    <div class="expand-block">
                      <h4>预期结果</h4>
                      <p>{{ row.expected_result }}</p>
                    </div>
                    <div class="expand-block" v-if="row.quality_score !== undefined">
                      <h4>质量评分</h4>
                      <el-progress :percentage="row.quality_score * 100" :format="(val) => `${val.toFixed(1)}%`" />
                      <p style="margin-top: 8px; font-size: 12px; color: var(--color-text-secondary);">
                        {{ row.quality_issues?.length ? `问题：${row.quality_issues.join('；')}` : '无质量问题' }}
                      </p>
                    </div>
                  </div>
                </template>
              </el-table-column>
            </el-table>

            <el-empty
              v-else
              :description="resultEmptyDescription"
            >
              <el-button type="primary" @click="handleGenerate">立即生成</el-button>
            </el-empty>
          </el-card>

      <!-- 功能模块确认区域（页面内显示，非弹窗） -->
      <el-card
        v-if="showFunctionPointsConfirm"
        shadow="hover"
        class="section-card function-points-card"
      >
        <template #header>
          <div class="card-header">
            <el-icon><List /></el-icon>
            <span>功能模块确认</span>
            <el-tag type="info" size="small" style="margin-left: 8px;">
              共 {{ extractedFunctionPoints.length }} 个功能模块
            </el-tag>
            <el-button
              text
              size="small"
              @click="handleFunctionPointsCancel"
              style="margin-left: auto;"
            >
              <el-icon><Close /></el-icon>
              关闭
            </el-button>
    </div>
        </template>

    <FunctionPointsConfirm
          :model-value="showFunctionPointsConfirm"
      :function-points="extractedFunctionPoints"
      :requirement-doc="requirementDocForConfirm"
          :inline-mode="true"
      @confirm="handleFunctionPointsConfirm"
      @cancel="handleFunctionPointsCancel"
    />
      </el-card>
    </div>
  </AiPageLayout>
</template>

<script setup>
import { aiApi } from '@/apis/ai'
import AiPageLayout from '@/components/ai/AiPageLayout.vue'
import FunctionPointsConfirm from '@/components/ai/FunctionPointsConfirm.vue'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  Document,
  Edit,
  Loading,
  MagicStick,
  Upload,
  WarningFilled,
  ArrowDown,
  ArrowUp,
  CircleCheck,
  CircleClose,
  Clock,
  List,
  Close,
  ChatLineRound,
  Cpu,
  InfoFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

const POLLING_INTERVAL = 2000

const route = useRoute()

const formRef = ref()
const form = reactive({
  requirementDoc: '',
  limit: undefined,
  maxWorkers: 4,
  modelName: '',
  temperature: 0.7,
  maxTokens: 2048,
  baseUrl: '',
  needConfirmFunctionPoints: true // 是否需要确认功能点与原文
})

const advancedPanels = ref([])
const isSubmitting = ref(false)
const modelsLoading = ref(false)
const modelList = ref([])
const configCollapsed = ref(false)

const taskId = ref(null)
const taskStatus = ref('idle')
const previousStatus = ref(null)
const taskProgress = ref(0)
const taskProgressInfo = ref(null) // 新增：详细的进度信息
const taskLogs = ref([])
const taskError = ref(null)
const taskMeta = ref({
  total_function_points: 0,
  processed_function_points: 0,
  total_warnings: 0,
  limit: 0
})
const pollingTimer = ref(null)

const result = ref(null)
const warnings = ref([])

// 功能点确认相关
const showFunctionPointsConfirm = ref(false)
const extractedFunctionPoints = ref([])
const requirementDocForConfirm = ref('')
const documentUnderstanding = ref(null) // 文档理解结果

// Word文档上传相关
const wordUploading = ref(false)
const wordFileName = ref('')
const extractPollingActive = ref(false)
const extractTaskId = ref(null) // 提取功能模块的任务ID
const thinkingSteps = ref([]) // AI思考过程步骤

const extractErrorMessage = (error, fallback = '请求失败，请稍后重试') => {
  if (error?.response?.data?.message) return error.response.data.message
  if (error?.response?.data?.detail) return error.response.data.detail
  return error?.message || fallback
}

const hasResult = computed(() => !!result.value && Array.isArray(result.value.test_cases) && result.value.test_cases.length > 0)
const resultCases = computed(() => {
  const cases = result.value?.test_cases ?? []
  // 为每个用例添加质量评估
  return cases.map((testCase, index) => {
    const quality = assessTestCaseQuality(testCase, index + 1)
    return {
      ...testCase,
      quality_score: quality.score,
      quality_issues: quality.issues,
      priority: testCase.priority || inferPriority(testCase) // 如果没有优先级，根据用例特征推断
    }
  })
})

// 用例质量评估函数
const assessTestCaseQuality = (testCase, index) => {
  const issues = []
  let score = 1.0
  
  // 检查必填字段
  if (!testCase.case_name || !testCase.case_name.trim()) {
    issues.push('用例名称为空')
    score -= 0.3
  }
  
  if (!testCase.module_name || !testCase.module_name.trim()) {
    issues.push('功能模块为空')
    score -= 0.2
  }
  
  // 检查步骤
  const steps = Array.isArray(testCase.steps) ? testCase.steps : []
  if (steps.length < 2) {
    issues.push(`步骤数不足（${steps.length}步，建议至少2步）`)
    score -= 0.2
  } else if (steps.length < 3) {
    issues.push(`步骤数较少（${steps.length}步，建议至少3步）`)
    score -= 0.1
  }
  
  // 检查预期结果
  if (!testCase.expected_result || !testCase.expected_result.trim()) {
    issues.push('预期结果为空')
    score -= 0.3
  } else {
    const expectedResult = testCase.expected_result.trim()
    // 检查是否使用了通用预期结果
    const genericPatterns = ['正确显示', '正常显示', '验证通过', '符合预期', '满足要求', '点击关闭直接消失']
    if (genericPatterns.some(pattern => expectedResult.includes(pattern))) {
      issues.push('使用了通用预期结果，建议使用具体描述')
      score -= 0.1
    }
    // 检查预期结果长度
    if (expectedResult.length < 5) {
      issues.push('预期结果过短，可能不够具体')
      score -= 0.1
    }
  }
  
  // 检查前置条件（可选，但如果有应该合理）
  if (testCase.preconditions && testCase.preconditions.trim()) {
    const preconditions = testCase.preconditions.trim()
    if (preconditions.length < 3) {
      issues.push('前置条件过短')
      score -= 0.05
    }
  }
  
  // 检查步骤质量
  steps.forEach((step, stepIndex) => {
    if (!step || typeof step !== 'string' || step.trim().length < 5) {
      issues.push(`步骤${stepIndex + 1}描述过短或不清晰`)
      score -= 0.05
    }
    // 检查是否包含禁止的操作
    const bannedActions = ['登录后台', '查看数据库', '手动投放', '后台操作']
    if (bannedActions.some(action => step.includes(action))) {
      issues.push(`步骤${stepIndex + 1}包含不可执行的操作`)
      score -= 0.1
    }
  })
  
  score = Math.max(0, Math.min(1, score)) // 限制在0-1之间
  
  return { score, issues }
}

// 根据用例特征推断优先级
const inferPriority = (testCase) => {
  const caseName = (testCase.case_name || '').toLowerCase()
  const expectedResult = (testCase.expected_result || '').toLowerCase()
  
  // 高优先级：核心功能、主要流程、关键操作
  if (caseName.includes('核心') || caseName.includes('主要') || caseName.includes('关键') ||
      caseName.includes('登录') || caseName.includes('注册') || caseName.includes('支付') ||
      expectedResult.includes('核心') || expectedResult.includes('主要')) {
    return 'high'
  }
  
  // 低优先级：边界测试、异常测试、兼容性测试
  if (caseName.includes('边界') || caseName.includes('异常') || caseName.includes('兼容') ||
      caseName.includes('极端') || caseName.includes('特殊') ||
      expectedResult.includes('边界') || expectedResult.includes('异常')) {
    return 'low'
  }
  
  // 默认中等优先级
  return 'medium'
}

// 优先级标签类型
const getPriorityTagType = (priority) => {
  const map = {
    'high': 'danger',
    'medium': 'warning',
    'low': 'info'
  }
  return map[priority] || 'info'
}

// 优先级标签文本
const getPriorityLabel = (priority) => {
  const map = {
    'high': '高',
    'medium': '中',
    'low': '低'
  }
  return map[priority] || '中'
}
const isTaskRunning = computed(() => ['pending', 'running'].includes(taskStatus.value))
const taskStatusLabel = computed(() => {
  switch (taskStatus.value) {
    case 'pending':
      return '任务已排队'
    case 'running':
      return '任务执行中'
    case 'success':
      return '生成完成'
    case 'failed':
      return '任务失败'
    case 'idle':
    default:
      return '等待开始'
  }
})
const progressStatus = computed(() => {
  if (taskStatus.value === 'success') return 'success'
  if (taskStatus.value === 'failed') return 'exception'
  if (isTaskRunning.value) return 'warning'
  return undefined
})
const statusIcon = computed(() => {
  if (taskStatus.value === 'success') return CircleCheckFilled
  if (taskStatus.value === 'failed') return CircleCloseFilled
  if (isTaskRunning.value) return Loading
  return WarningFilled
})

// 新增：进度相关计算属性
const progressPercentage = computed(() => {
  if (taskProgressInfo.value?.progress !== undefined) {
    return Math.min(100, Math.max(0, taskProgressInfo.value.progress))
  }
  return taskProgress.value
})

const progressText = computed(() => {
  if (taskProgressInfo.value?.current && taskProgressInfo.value?.total) {
    return `${taskProgressInfo.value.current}/${taskProgressInfo.value.total}`
  }
  return `${progressPercentage.value}%`
})

const stages = computed(() => {
  const stageMap = {
    'extracting_modules': { name: '提取功能模块', order: 1 },
    'generating_test_cases': { name: '生成测试用例', order: 2 },
    'validating': { name: '验证和修复', order: 3 }
  }
  
  const currentStage = taskProgressInfo.value?.stage
  const result = []
  
  for (const [key, info] of Object.entries(stageMap)) {
    let status = 'waiting'
    if (key === currentStage) {
      status = taskStatus.value === 'running' ? 'running' : 'completed'
    } else if (currentStage && stageMap[currentStage]?.order > info.order) {
      status = 'completed'
    }
    
    result.push({
      ...info,
      status,
      message: key === currentStage ? taskProgressInfo.value?.message : null,
      current: taskProgressInfo.value?.current,
      total: taskProgressInfo.value?.total
    })
  }
  
  return result
})

const getStageIcon = (status) => {
  if (status === 'completed') return CircleCheck
  if (status === 'failed') return CircleClose
  if (status === 'running') return Loading
  return Clock
}
const formatLogTime = (value) => {
  if (!value) return ''
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleTimeString()
  } catch (error) {
    return value
  }
}

const resultWarnings = computed(() => warnings.value)
const resultMeta = computed(() => result.value?.meta ?? {
  total_function_points: taskMeta.value.total_function_points,
  processed_function_points: taskMeta.value.processed_function_points,
  total_warnings: warnings.value.length
})

// 计算平均质量评分
const averageQualityScore = computed(() => {
  if (resultCases.value.length === 0) return 0
  const totalScore = resultCases.value.reduce((sum, testCase) => {
    return sum + (testCase.quality_score || 0)
  }, 0)
  return totalScore / resultCases.value.length
})

// 计算有质量问题的用例数
const problemCasesCount = computed(() => {
  return resultCases.value.filter(testCase => {
    return (testCase.quality_score || 0) < 0.8 || (testCase.quality_issues?.length || 0) > 0
  }).length
})

// 质量评分标签类型
const getQualityTagType = (score) => {
  if (score >= 0.9) return 'success'
  if (score >= 0.7) return 'warning'
  return 'danger'
}
const resultEmptyDescription = computed(() => {
  if (isTaskRunning.value) {
    return '任务执行中，生成结果将陆续展示，请稍候。'
  }
  return hasResult.value
    ? '未生成测试用例，请检查需求文档是否包含明确的功能点描述。'
    : '粘贴需求文档内容后点击“生成测试用例”即可获取结果。'
})

const deriveWarnings = (resultData, fallback = []) => {
  if (!resultData) {
    return fallback ?? []
  }
  const aggregated = []
  const perPoint = resultData.by_function_point ?? {}
  Object.entries(perPoint).forEach(([name, data]) => {
    (data?.warnings ?? []).forEach(warning => {
      aggregated.push(`[${name}] ${warning}`)
    })
  })
  return aggregated.length ? aggregated : (fallback ?? [])
}


const handleWordFileChange = async (file) => {
  if (!file.raw) {
    return
  }

  // 检查文件类型
  if (!file.name.endsWith('.docx')) {
    ElMessage.error('请上传.docx格式的Word文档')
    return
  }

  try {
    wordUploading.value = true
    wordFileName.value = file.name

    const response = await aiApi.uploadWordDocument(file.raw)

    if (response.data.code === 0) {
      const data = response.data.data
      // 将解析后的文本填充到需求文档输入框
      form.requirementDoc = data.text || ''
      ElMessage.success(`Word文档解析成功！共 ${data.total_paragraphs || 0} 个段落，${data.total_headings || 0} 个标题`)
    } else {
      // 如果是功能未实现的提示，显示警告而不是错误
      if (response.data.code === -1) {
        ElMessage.warning(response.data.message || 'Word文档上传功能暂未实现，请直接粘贴文档内容')
    } else {
      ElMessage.error(response.data.message || '解析Word文档失败')
      }
      wordFileName.value = ''
    }
  } catch (error) {
    console.error('上传Word文档失败:', error)
    ElMessage.error(extractErrorMessage(error, '上传Word文档失败，请稍后重试'))
    wordFileName.value = ''
  } finally {
    wordUploading.value = false
  }
}

const loadModels = async () => {
  try {
    modelsLoading.value = true
    const response = await aiApi.getAvailableModels()
    if (response.data.code === 0) {
      modelList.value = response.data.data ?? []
      if (!form.modelName && modelList.value.length) {
        const recommended = modelList.value.find(item => item.recommended)
        form.modelName = recommended?.model_id ?? modelList.value[0].model_id
      }
    } else {
      ElMessage.warning(response.data.message || '获取模型列表失败')
    }
  } catch (error) {
    console.error('加载模型失败:', error)
    ElMessage.error(extractErrorMessage(error, '获取模型列表失败，请检查后端服务是否可用'))
  } finally {
    modelsLoading.value = false
  }
}

const buildGeneratePayload = () => {
  if (!form.requirementDoc || !form.requirementDoc.trim()) {
    throw new Error('请先粘贴需求文档内容后再生成测试用例')
  }
  const payload = {
    requirement_doc: form.requirementDoc.trim(),
    enable_understanding: true // 默认启用文档理解
  }
  if (form.limit) payload.limit = form.limit
  if (form.maxWorkers) payload.max_workers = form.maxWorkers
  if (form.modelName) payload.model_name = form.modelName
  if (form.baseUrl) payload.base_url = form.baseUrl
  if (form.temperature !== undefined && form.temperature !== null) payload.temperature = form.temperature
  if (form.maxTokens) payload.max_tokens = form.maxTokens
  
  // 如果有理解结果，传递给后端
  if (documentUnderstanding.value) {
    payload.document_understanding = documentUnderstanding.value
  }
  
  return payload
}

const stopPolling = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

const applyTaskUpdate = (taskData) => {
  taskStatus.value = taskData.status || taskStatus.value || 'running'
  taskProgress.value = Math.min(100, Math.max(0, Number(taskData.progress ?? 0)))
  taskLogs.value = taskData.logs ?? []
  taskError.value = taskData.error || null
  
  // 更新详细的进度信息
  if (taskData.progress_info) {
    taskProgressInfo.value = taskData.progress_info
  }

  const meta = taskData.meta ?? {}
  taskMeta.value = {
    total_function_points: meta.total_function_points ?? taskMeta.value.total_function_points ?? 0,
    processed_function_points: meta.processed_function_points ?? taskMeta.value.processed_function_points ?? 0,
    total_warnings: meta.total_warnings ?? warnings.value.length,
    limit: meta.limit ?? taskMeta.value.limit ?? 0
  }

  const finalResult = taskData.result
  const partialResult = taskData.partial_result
  let effectiveResult = null

  if (finalResult) {
    effectiveResult = finalResult
  } else if (partialResult && (partialResult.test_cases?.length || Object.keys(partialResult.by_function_point ?? {}).length)) {
    effectiveResult = {
      test_cases: partialResult.test_cases ?? [],
      by_function_point: partialResult.by_function_point ?? {},
      meta: {
        total_function_points: taskMeta.value.total_function_points,
        processed_function_points: taskMeta.value.processed_function_points,
        total_warnings: partialResult.warnings?.length ?? taskMeta.value.total_warnings ?? 0
      }
    }
  }

  if (effectiveResult) {
    result.value = effectiveResult
    warnings.value = deriveWarnings(effectiveResult, partialResult?.warnings)
  } else {
    result.value = null
    warnings.value = partialResult?.warnings ?? []
  }
  
  // 更新思考过程（在生成任务中也可能有思考过程）
  if (partialResult?.type === 'thinking') {
    const stepsList = partialResult.thinking_steps_list || []
    if (stepsList.length > 0) {
      thinkingSteps.value = stepsList
    } else if (partialResult.thinking_steps) {
      const step = partialResult.thinking_steps
      const existingIndex = thinkingSteps.value.findIndex(s => s.step === step.step)
      if (existingIndex >= 0) {
        thinkingSteps.value[existingIndex] = step
      } else {
        thinkingSteps.value.push(step)
      }
    }
  }

  taskMeta.value = {
    ...taskMeta.value,
    total_warnings: warnings.value.length
  }

  if (previousStatus.value !== taskStatus.value) {
    if (taskStatus.value === 'success') {
      ElMessage.success('测试用例生成完成')
      stopPolling()
    } else if (taskStatus.value === 'failed') {
      ElMessage.error(taskError.value || '测试用例生成失败')
      stopPolling()
    }
    previousStatus.value = taskStatus.value
  }
}

const fetchTaskStatus = async () => {
  if (!taskId.value) return
  try {
    const response = await aiApi.getTaskStatus(taskId.value)
    if (response.data.code !== 0) {
      throw new Error(response.data.message || '获取任务状态失败')
    }
    const taskData = response.data.data ?? {}
    
    // 适配任务管理器返回的格式
    // 如果任务完成，将 result 字段映射到前端期望的格式
    if (taskData.status === 'completed' && taskData.result) {
      // 任务完成，应用结果
      applyTaskUpdate({
        status: 'success',
        result: taskData.result,
        progress: 100,
        progress_info: taskData.progress || { progress: 100 }
      })
      isSubmitting.value = false
    } else if (taskData.status === 'failed') {
      // 任务失败
      applyTaskUpdate({
        status: 'failed',
        error: taskData.error || '任务执行失败',
        progress: 0,
        progress_info: null
      })
      isSubmitting.value = false
    } else {
      // 任务进行中，更新进度信息
      applyTaskUpdate({
        status: 'running',
        progress: taskData.progress?.progress || 0,
        progress_info: taskData.progress, // 使用后端返回的详细进度信息
        partial_result: taskData.partial_result // 更新部分结果
      })
    }
  } catch (error) {
    console.error('获取任务状态失败:', error)
    ElMessage.error(extractErrorMessage(error, '获取任务状态失败，请稍后重试'))
    stopPolling()
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
    isSubmitting.value = false
  }
}

const startPolling = () => {
  stopPolling()
  fetchTaskStatus()
  pollingTimer.value = setInterval(fetchTaskStatus, POLLING_INTERVAL)
}

const handleGenerate = async () => {
  try {
    // 清除之前的思考过程
    thinkingSteps.value = []
    
    const payload = buildGeneratePayload()
    isSubmitting.value = true
    extractPollingActive.value = true

    // 第一步：异步提取功能模块
    ElMessage.info('正在提交提取功能模块任务...')
    
    // 提交异步任务
    const submitResponse = await aiApi.extractFunctionModulesAsync({
      requirement_doc: payload.requirement_doc,
      model_name: payload.model_name,
      base_url: payload.base_url,
      task_id: payload.task_id,
      enable_understanding: payload.enable_understanding || true // 启用文档理解
    })

    if (submitResponse.data.code !== 0) {
      throw new Error(submitResponse.data.message || '提交提取任务失败')
    }

    const submitData = submitResponse.data.data
    extractTaskId.value = submitData.task_id
    
    // 设置任务状态，显示进度卡片
    taskId.value = extractTaskId.value
    taskStatus.value = 'running'
    taskProgress.value = 0
    taskProgressInfo.value = {
      stage: 'extracting_modules',
      progress: 0,
      message: '正在提取功能模块...'
    }
    
    ElMessage.info('任务已提交，正在处理中...')
    
    // 开始轮询提取任务状态（使用统一的轮询机制）
    startExtractPolling()
    
  } catch (error) {
    extractPollingActive.value = false
    stopExtractPolling()
    console.error('生成测试用例失败:', error)
    ElMessage.error(extractErrorMessage(error, '生成测试用例失败，请稍后重试'))
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
    isSubmitting.value = false
  }
}

// 提取任务轮询相关
const extractPollingTimer = ref(null)

const startExtractPolling = () => {
  stopExtractPolling()
  extractPollingTimer.value = setInterval(() => {
    if (extractTaskId.value && extractPollingActive.value) {
      fetchExtractTaskStatus()
    }
  }, POLLING_INTERVAL)
}

const stopExtractPolling = () => {
  if (extractPollingTimer.value) {
    clearInterval(extractPollingTimer.value)
    extractPollingTimer.value = null
  }
}

const fetchExtractTaskStatus = async () => {
  if (!extractTaskId.value || !extractPollingActive.value) return
  
  try {
    const response = await aiApi.getTaskStatus(extractTaskId.value)
    if (response.data.code !== 0) {
      return
    }
    
    const taskData = response.data.data ?? {}
    const status = taskData.status
    
    // 更新进度信息
    if (taskData.progress) {
      taskProgressInfo.value = taskData.progress
      taskProgress.value = taskData.progress.progress || 0
    }
    
    // 更新思考过程
    if (taskData.partial_result?.type === 'thinking') {
      // 优先使用累积的步骤列表
      const stepsList = taskData.partial_result.thinking_steps_list || []
      if (stepsList.length > 0) {
        // 使用后端累积的步骤列表
        thinkingSteps.value = stepsList
      } else if (taskData.partial_result.thinking_steps) {
        // 兼容：如果只有单个步骤，累积到数组中
        const step = taskData.partial_result.thinking_steps
        const existingIndex = thinkingSteps.value.findIndex(s => s.step === step.step)
        if (existingIndex >= 0) {
          thinkingSteps.value[existingIndex] = step
        } else {
          thinkingSteps.value.push(step)
        }
      }
      console.log('思考过程更新:', thinkingSteps.value.length, '个步骤')
    }

        if (status === 'completed') {
          // 任务完成，获取结果
          extractPollingActive.value = false
      stopExtractPolling()
      
      // 更新进度
      taskProgressInfo.value = {
        stage: 'extracting_modules',
        progress: 100,
        message: '功能模块提取完成'
      }
      taskProgress.value = 100
      
      // 任务完成时，也要检查并保存思考过程（如果存在）
      if (taskData.partial_result?.type === 'thinking') {
        const stepsList = taskData.partial_result.thinking_steps_list || []
        if (stepsList.length > 0) {
          thinkingSteps.value = stepsList
          console.log('任务完成时保存思考过程:', thinkingSteps.value.length, '个步骤')
        } else if (taskData.partial_result.thinking_steps) {
          const step = taskData.partial_result.thinking_steps
          const existingIndex = thinkingSteps.value.findIndex(s => s.step === step.step)
          if (existingIndex >= 0) {
            thinkingSteps.value[existingIndex] = step
          } else {
            thinkingSteps.value.push(step)
          }
        }
      }
      
      const result = taskData.result
          if (!result) {
            throw new Error('任务完成但未返回结果')
          }

          extractedFunctionPoints.value = result.function_points || []
          requirementDocForConfirm.value = result.requirement_doc || form.requirementDoc
          
          // 保存理解结果
          if (result.document_understanding) {
            documentUnderstanding.value = result.document_understanding
            console.log('文档理解结果已保存:', documentUnderstanding.value)
          } else {
            documentUnderstanding.value = null
          }

          if (extractedFunctionPoints.value.length === 0) {
            ElMessage.warning('未能提取到功能模块，将直接生成测试用例')
            // 如果没有提取到功能模块，使用原来的流程
        const payload = buildGeneratePayload()
            await handleGenerateDirectly(payload)
            return
          }

          // 根据用户选择决定是否需要确认功能点
          if (form.needConfirmFunctionPoints) {
            // 需要确认：显示功能模块确认对话框
            showFunctionPointsConfirm.value = true
            ElMessage.success(`已提取到 ${extractedFunctionPoints.value.length} 个功能模块，请确认`)
            isSubmitting.value = false
          } else {
            // 不需要确认：直接使用提取到的功能点生成测试用例
            ElMessage.success(`已提取到 ${extractedFunctionPoints.value.length} 个功能模块，直接生成测试用例`)
            const payload = buildGeneratePayload()
            await handleGenerateDirectly(payload, extractedFunctionPoints.value)
          }
        } else if (status === 'failed') {
          extractPollingActive.value = false
      stopExtractPolling()
        taskStatus.value = 'failed'
      taskError.value = taskData.error || '提取功能模块失败'
      ElMessage.error(taskData.error || '提取功能模块失败')
        isSubmitting.value = false
      }
    // pending 或 running 状态继续轮询，由定时器控制
  } catch (error) {
    console.error('获取提取任务状态失败:', error)
    extractPollingActive.value = false
    stopExtractPolling()
    ElMessage.error(extractErrorMessage(error, '查询任务状态失败'))
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
    isSubmitting.value = false
  }
}

const handleFunctionPointsConfirm = async (confirmData) => {
  try {
    showFunctionPointsConfirm.value = false
    isSubmitting.value = true
    
    // 清除提取任务ID，准备生成任务
    extractTaskId.value = null
    stopExtractPolling()

    const payload = buildGeneratePayload()

    // 重置状态
    warnings.value = []
    result.value = null
    taskLogs.value = []
    taskError.value = null
    taskProgress.value = 0
    taskProgressInfo.value = {
      stage: 'generating_test_cases',
      progress: 0,
      message: '正在生成测试用例...'
    }
    taskStatus.value = 'running'
    previousStatus.value = null
    taskMeta.value = {
      total_function_points: 0,
      processed_function_points: 0,
      total_warnings: 0,
      limit: payload.limit ?? 0
    }

    // 创建任务并提交确认后的功能点
    const taskPayload = {
      ...payload,
      confirmed_function_points: confirmData.confirmedFunctionPoints,
      original_function_points: confirmData.originalFunctionPoints,
      operation_history: confirmData.operationHistory,
      enable_understanding: payload.enable_understanding || true, // 启用文档理解
      document_understanding: documentUnderstanding.value // 传递理解结果
    }

    // 使用异步生成接口
    ElMessage.info('正在提交生成任务...')
    const submitResponse = await aiApi.createGenerationTask(taskPayload)

    if (submitResponse.data.code !== 0) {
      throw new Error(submitResponse.data.message || '提交生成任务失败')
    }

    const submitData = submitResponse.data.data
    const newTaskId = submitData.task_id
    
    if (!newTaskId) {
      throw new Error('任务创建失败，未返回 task_id')
    }

    taskId.value = newTaskId
    ElMessage.success('任务已提交，正在生成测试用例')
    startPolling()
  } catch (error) {
    console.error('生成测试用例失败:', error)
    ElMessage.error(extractErrorMessage(error, '生成测试用例失败，请稍后重试'))
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
    isSubmitting.value = false
  }
}

const handleFunctionPointsCancel = () => {
  showFunctionPointsConfirm.value = false
  // 不显示提示信息，静默关闭对话框
}

const handleGenerateDirectly = async (payload, confirmedFunctionPoints = null) => {
  // 原有的直接生成流程（用于没有提取到功能点的情况，或用户选择跳过确认的情况）
  warnings.value = []
  result.value = null
  taskLogs.value = []
  taskError.value = null
  taskProgress.value = 0
  taskStatus.value = 'running'
  previousStatus.value = null
  taskMeta.value = {
    total_function_points: 0,
    processed_function_points: 0,
    total_warnings: 0,
    limit: payload.limit ?? 0
  }
  
  // 如果提供了确认的功能点，使用它们
  if (confirmedFunctionPoints && confirmedFunctionPoints.length > 0) {
    payload.confirmed_function_points = confirmedFunctionPoints
  }

  // 确保传递理解结果
  if (documentUnderstanding.value) {
    payload.document_understanding = documentUnderstanding.value
    payload.enable_understanding = true
  }

  const response = await aiApi.createGenerationTask(payload)
  if (response.data.code !== 0) {
    throw new Error(response.data.message || '创建任务失败')
  }
  const newTaskId = response.data.data?.task_id
  if (!newTaskId) {
    throw new Error('任务创建失败，未返回 task_id')
  }

  taskId.value = newTaskId
  ElMessage.success('任务创建成功，正在生成测试用例')
  startPolling()
}

const handleReset = () => {
  stopPolling()
  stopExtractPolling()
  taskId.value = null
  extractTaskId.value = null
  extractPollingActive.value = false
  taskStatus.value = 'idle'
  previousStatus.value = null
  taskProgress.value = 0
  taskProgressInfo.value = null
  taskLogs.value = []
  taskError.value = null
  result.value = null
  warnings.value = []
  documentUnderstanding.value = null // 清除理解结果
  extractedFunctionPoints.value = []
  requirementDocForConfirm.value = ''
  showFunctionPointsConfirm.value = false
  thinkingSteps.value = [] // 清除思考过程
  taskMeta.value = {
    total_function_points: 0,
    processed_function_points: 0,
    total_warnings: 0,
    limit: 0
  }
}

const initializeFromQuery = () => {
  const { model, limit } = route.query
  if (model) {
    form.modelName = String(model)
  }
  if (limit) {
    const limitNum = Number(limit)
    if (!Number.isNaN(limitNum)) {
      form.limit = limitNum
    }
  }
}

onMounted(async () => {
  await loadModels()
  initializeFromQuery()
})

onBeforeUnmount(() => {
  stopPolling()
  stopExtractPolling()
  extractPollingActive.value = false // 停止提取任务轮询
})
</script>

<style scoped>
/* ========== 基础变量 ========== */
:root {
  --color-primary: #3b82f6;
  --color-primary-hover: #2563eb;
  --color-primary-active: #1d4ed8;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  
  --color-text-primary: #111827;
  --color-text-secondary: #6b7280;
  --color-text-tertiary: #9ca3af;
  
  --color-border: #e5e7eb;
  --color-bg: #ffffff;
  --color-bg-secondary: #f9fafb;
  --color-bg-hover: #f3f4f6;
  
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

/* ========== 页面容器 ========== */
.ai-generator-page {
  min-height: 100vh;
  background: var(--color-bg-secondary);
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* ========== 卡片基础样式 ========== */
.section-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s ease;
}

.section-card:hover {
  box-shadow: var(--shadow-md);
}

.section-card .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  font-weight: 600;
  font-size: 16px;
  color: var(--color-text-primary);
}

.section-card .card-header .el-icon {
  margin-right: var(--spacing-sm);
  color: var(--color-primary);
}

.progress-card {
  margin-top: var(--spacing-md);
}

.task-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-status-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.status-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-icon {
  font-size: 16px;
}

.status-icon.success {
  color: var(--el-color-success);
}

.status-icon.exception {
  color: var(--el-color-error);
}

.status-icon.warning {
  color: var(--el-color-warning);
}

.status-text {
  font-weight: 500;
}

.status-error {
  color: var(--el-color-error);
  font-size: 13px;
}

.log-panel {
  margin-top: 8px;
}

.log-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.log-item {
  display: flex;
  gap: 10px;
  font-size: 13px;
  padding: 4px 0;
  color: var(--el-text-color-secondary);
}

.log-item.log-error {
  color: var(--el-color-error);
}

.log-item.log-warning {
  color: var(--el-color-warning);
}

.log-item.log-empty {
  justify-content: center;
  color: var(--el-text-color-disabled);
}

.log-time {
  min-width: 72px;
  color: var(--el-text-color-disabled);
}

.log-message {
  flex: 1;
  line-height: 1.4;
}

/* card-header 已在上面定义 */

.config-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.requirement-item :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  min-height: 320px;
}

.model-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-name {
  font-weight: 600;
}

.model-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.result-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.result-alert {
  margin: 0;
}

.warning-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.6;
}

/* ========== 结果表格（简化版） ========== */
.result-table {
  margin-top: var(--spacing-sm);
}

.result-table .el-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.result-table .el-table th {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-weight: 500;
  font-size: 13px;
}

.result-table .el-table td {
  font-size: 13px;
  color: var(--color-text-primary);
}

.result-table .el-table--striped .el-table__body tr.el-table__row--striped td {
  background: var(--color-bg-secondary);
}

.result-table .el-table__body tr:hover > td {
  background: var(--color-bg-hover) !important;
}

.expand-section {
  display: flex;
  gap: 24px;
  padding: 8px 12px;
  line-height: 1.6;
}

.expand-block {
  flex: 1;
}

.expand-block h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.expand-block ol {
  padding-left: 20px;
  margin: 0;
}

.expected-text {
  white-space: pre-wrap;
}

.icon-left {
  margin-right: 4px;
}

/* 配置卡片折叠按钮 */
.config-card .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.collapse-btn {
  margin-left: auto;
}

/* 任务进度容器 */
.task-progress-container {
  padding: 16px 0;
}

.overall-progress {
  margin-bottom: 24px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  font-size: 14px;
}

.status-text {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.progress-text {
  color: var(--el-text-color-secondary);
}

/* ========== 阶段列表（简化版） ========== */
.stage-list {
  margin-top: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.stage-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  transition: background 0.2s ease;
}

.stage-item:hover {
  background: var(--color-bg-hover);
}

.stage-item.stage-completed {
  background: #ecfdf5;
  border-left: 3px solid var(--color-success);
}

.stage-item.stage-running {
  background: #fef3c7;
  border-left: 3px solid var(--color-warning);
}

.stage-item.stage-waiting {
  background: var(--color-bg-secondary);
  border-left: 3px solid var(--color-border);
  opacity: 0.6;
}

.stage-icon {
  margin-right: var(--spacing-sm);
  font-size: 18px;
}

.stage-item.stage-completed .stage-icon {
  color: var(--color-success);
}

.stage-item.stage-running .stage-icon {
  color: var(--color-warning);
  animation: rotate 2s linear infinite;
}

.stage-content {
  flex: 1;
}

.stage-name {
  font-weight: 500;
  font-size: 14px;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}

.stage-message {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.stage-progress {
  font-size: 14px;
  color: var(--color-text-primary);
  font-weight: 500;
  margin-left: var(--spacing-sm);
}

/* ========== 当前处理项 ========== */
.current-item {
  margin-top: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: #eff6ff;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  border-left: 3px solid var(--color-primary);
  font-size: 14px;
}

.loading-icon {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.error-alert {
  margin-top: var(--spacing-md);
}

/* ========== 结果表格（简化版） ========== */
.result-table {
  margin-top: var(--spacing-sm);
}

.result-table .el-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.result-table .el-table th {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-weight: 500;
  font-size: 13px;
}

.result-table .el-table td {
  font-size: 13px;
  color: var(--color-text-primary);
}

.result-table .el-table--striped .el-table__body tr.el-table__row--striped td {
  background: var(--color-bg-secondary);
}

.result-table .el-table__body tr:hover > td {
  background: var(--color-bg-hover) !important;
}

/* ========== AI思考过程展示（优化版） ========== */
.thinking-process {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
  font-weight: 500;
  font-size: 14px;
  color: var(--color-text-primary);
  cursor: pointer;
  user-select: none;
}

.thinking-header:hover {
  color: var(--color-primary);
}

.thinking-messages {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.thinking-message {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-bg);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--color-primary);
  transition: all 0.2s ease;
}

.thinking-message:hover {
  box-shadow: var(--shadow-sm);
}

.thinking-message.step-complete {
  border-left-color: var(--color-success);
}

.thinking-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary) 0%, #6366f1 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  font-size: 16px;
}

.thinking-content {
  flex: 1;
  min-width: 0;
}

.thinking-title {
  font-weight: 500;
  font-size: 14px;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-sm);
}

.thinking-items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
}

.thinking-item {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  padding-left: var(--spacing-md);
  position: relative;
}

.thinking-item::before {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--color-primary);
  font-weight: bold;
}

.thinking-result {
  margin-top: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-border);
}

.thinking-result pre {
  margin: 0;
  padding: var(--spacing-sm);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  color: var(--color-text-secondary);
}

.thinking-progress {
  width: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.thinking-empty {
  padding: var(--spacing-md);
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
}

.thinking-empty .el-icon {
  animation: rotate 2s linear infinite;
}

/* 结果卡片 */
.result-card .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

@media screen and (max-width: 1024px) {
  .expand-section {
    flex-direction: column;
  }
  
  .stage-list {
    gap: 8px;
  }
  
  .stage-item {
    padding: 10px 12px;
  }
}
</style>
