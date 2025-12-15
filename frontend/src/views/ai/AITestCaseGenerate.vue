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
              <el-table-column type="expand">
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
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="module_name" label="所属模块" min-width="150" />
              <el-table-column prop="sub_module" label="子功能点" min-width="120" :show-overflow-tooltip="true">
                <template #default="{ row }">
                  <span v-if="row.sub_module" class="sub-module-tag">{{ row.sub_module }}</span>
                  <span v-else class="sub-module-empty">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="case_name" label="用例名称" min-width="200" />
              <el-table-column label="预期结果" min-width="260">
                <template #default="{ row }">
                  <span class="expected-text">{{ row.expected_result }}</span>
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
  Close
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
  baseUrl: ''
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

// Word文档上传相关
const wordUploading = ref(false)
const wordFileName = ref('')
const extractPollingActive = ref(false)
const extractTaskId = ref(null) // 提取功能模块的任务ID

const extractErrorMessage = (error, fallback = '请求失败，请稍后重试') => {
  if (error?.response?.data?.message) return error.response.data.message
  if (error?.response?.data?.detail) return error.response.data.detail
  return error?.message || fallback
}

const hasResult = computed(() => !!result.value && Array.isArray(result.value.test_cases) && result.value.test_cases.length > 0)
const resultCases = computed(() => result.value?.test_cases ?? [])
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
    requirement_doc: form.requirementDoc.trim()
  }
  if (form.limit) payload.limit = form.limit
  if (form.maxWorkers) payload.max_workers = form.maxWorkers
  if (form.modelName) payload.model_name = form.modelName
  if (form.baseUrl) payload.base_url = form.baseUrl
  if (form.temperature !== undefined && form.temperature !== null) payload.temperature = form.temperature
  if (form.maxTokens) payload.max_tokens = form.maxTokens
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
      task_id: payload.task_id
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
      
      const result = taskData.result
      if (!result) {
        throw new Error('任务完成但未返回结果')
      }

      extractedFunctionPoints.value = result.function_points || []
      requirementDocForConfirm.value = result.requirement_doc || form.requirementDoc

      if (extractedFunctionPoints.value.length === 0) {
        ElMessage.warning('未能提取到功能模块，将直接生成测试用例')
        // 如果没有提取到功能模块，使用原来的流程
        const payload = buildGeneratePayload()
        await handleGenerateDirectly(payload)
        return
      }

      // 显示功能模块确认对话框
      showFunctionPointsConfirm.value = true
      ElMessage.success(`已提取到 ${extractedFunctionPoints.value.length} 个功能模块，请确认`)
      isSubmitting.value = false
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
      operation_history: confirmData.operationHistory
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

const handleGenerateDirectly = async (payload) => {
  // 原有的直接生成流程（用于没有提取到功能点的情况）
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
.ai-generator-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  border-radius: 16px;
}

.progress-card {
  margin-top: 16px;
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

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

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

.result-table {
  margin-top: 8px;
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

/* 阶段列表 */
.stage-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stage-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f7fa;
  transition: all 0.3s;
}

.stage-item.stage-completed {
  background: #f0f9ff;
  border-left: 3px solid var(--el-color-success);
}

.stage-item.stage-running {
  background: #fef0e6;
  border-left: 3px solid var(--el-color-warning);
  animation: pulse 2s ease-in-out infinite;
}

.stage-item.stage-waiting {
  background: #f5f7fa;
  border-left: 3px solid #e4e7ed;
  opacity: 0.6;
}

.stage-icon {
  margin-right: 12px;
  font-size: 20px;
}

.stage-item.stage-completed .stage-icon {
  color: var(--el-color-success);
}

.stage-item.stage-running .stage-icon {
  color: var(--el-color-warning);
  animation: rotate 2s linear infinite;
}

.stage-content {
  flex: 1;
}

.stage-name {
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--el-text-color-primary);
}

.stage-message {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stage-progress {
  font-size: 14px;
  color: var(--el-text-color-regular);
  font-weight: 500;
  margin-left: 12px;
}

/* 当前处理项 */
.current-item {
  margin-top: 16px;
  padding: 12px 16px;
  background: #ecf5ff;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-left: 3px solid var(--el-color-primary);
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
  margin-top: 16px;
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
