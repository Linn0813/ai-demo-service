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
      <el-row :gutter="16">
        <el-col :lg="10" :md="24">
          <el-card shadow="hover" class="section-card">
            <template #header>
              <div class="card-header">
                <el-icon><Edit /></el-icon>
                <span>生成配置</span>
              </div>
            </template>

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
          </el-card>

          <el-card
            v-if="taskId"
            shadow="hover"
            class="section-card progress-card"
          >
            <template #header>
              <div class="card-header">
                <el-icon><Loading /></el-icon>
                <span>执行进度</span>
              </div>
            </template>

            <div class="task-summary">
              <div class="task-status-line">
                <div class="status-left">
                  <el-icon :class="['status-icon', progressStatus]">
                    <component :is="statusIcon" />
                  </el-icon>
                  <span class="status-text">{{ taskStatusLabel }}</span>
                </div>
                <span v-if="taskError" class="status-error">{{ taskError }}</span>
              </div>
              <el-progress
                :percentage="taskProgress"
                :status="progressStatus"
                :stroke-width="12"
              />
            </div>

            <div class="log-panel">
              <el-scrollbar height="160px">
                <ul class="log-list">
                  <li
                    v-for="(log, index) in taskLogs"
                    :key="`${log.time}-${index}`"
                    :class="['log-item', `log-${log.level || 'info'}`]"
                  >
                    <span class="log-time">{{ formatLogTime(log.time) }}</span>
                    <span class="log-message">{{ log.message }}</span>
                  </li>
                  <li v-if="taskLogs.length === 0" class="log-item log-empty">
                    暂无日志
                  </li>
                </ul>
              </el-scrollbar>
            </div>
          </el-card>
        </el-col>

        <el-col :lg="14" :md="24">
          <el-card shadow="hover" class="section-card">
            <template #header>
              <div class="card-header">
                <el-icon><Document /></el-icon>
                <span>生成结果</span>
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
        </el-col>
      </el-row>
    </div>

    <!-- 功能点确认对话框 -->
    <FunctionPointsConfirm
      v-model="showFunctionPointsConfirm"
      :function-points="extractedFunctionPoints"
      :requirement-doc="requirementDocForConfirm"
      @confirm="handleFunctionPointsConfirm"
      @cancel="handleFunctionPointsCancel"
    />
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
  WarningFilled
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

const taskId = ref(null)
const taskStatus = ref('idle')
const previousStatus = ref(null)
const taskProgress = ref(0)
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
    applyTaskUpdate(taskData)
  } catch (error) {
    console.error('获取任务状态失败:', error)
    ElMessage.error(extractErrorMessage(error, '获取任务状态失败，请稍后重试'))
    stopPolling()
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
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

    // 第一步：提取功能模块
    ElMessage.info('正在提取功能模块...')
    const extractResponse = await aiApi.extractFunctionModules({
      requirement_doc: payload.requirement_doc,
      model_name: payload.model_name,
      base_url: payload.base_url
    })

    if (extractResponse.data.code !== 0) {
      throw new Error(extractResponse.data.message || '提取功能模块失败')
    }

    const extractData = extractResponse.data.data
    extractedFunctionPoints.value = extractData.function_points || []
    requirementDocForConfirm.value = extractData.requirement_doc || form.requirementDoc

    if (extractedFunctionPoints.value.length === 0) {
      ElMessage.warning('未能提取到功能模块，将直接生成测试用例')
      // 如果没有提取到功能模块，使用原来的流程
      await handleGenerateDirectly(payload)
      return
    }

    // 显示功能模块确认对话框
    showFunctionPointsConfirm.value = true
    ElMessage.success(`已提取到 ${extractedFunctionPoints.value.length} 个功能模块，请确认`)
  } catch (error) {
    console.error('生成测试用例失败:', error)
    ElMessage.error(extractErrorMessage(error, '生成测试用例失败，请稍后重试'))
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
  } finally {
    isSubmitting.value = false
  }
}

const handleFunctionPointsConfirm = async (confirmData) => {
  try {
    showFunctionPointsConfirm.value = false
    isSubmitting.value = true

    const payload = buildGeneratePayload()

    // 重置状态
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

    // 创建任务并提交确认后的功能点
    const taskPayload = {
      ...payload,
      confirmed_function_points: confirmData.confirmedFunctionPoints,
      original_function_points: confirmData.originalFunctionPoints,
      operation_history: confirmData.operationHistory
    }

    // 使用确认生成接口
    const response = await aiApi.confirmAndGenerate(taskPayload)

    if (response.data.code !== 0) {
      throw new Error(response.data.message || '生成测试用例失败')
    }

    const resultData = response.data.data
    result.value = resultData
    warnings.value = deriveWarnings(resultData)

    ElMessage.success('测试用例生成完成')
    taskStatus.value = 'success'
    taskProgress.value = 100
  } catch (error) {
    console.error('生成测试用例失败:', error)
    ElMessage.error(extractErrorMessage(error, '生成测试用例失败，请稍后重试'))
    taskStatus.value = 'failed'
    taskError.value = extractErrorMessage(error)
  } finally {
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
  taskId.value = null
  taskStatus.value = 'idle'
  previousStatus.value = null
  taskProgress.value = 0
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

@media screen and (max-width: 1024px) {
  .expand-section {
    flex-direction: column;
  }
}
</style>
