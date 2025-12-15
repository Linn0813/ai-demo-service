<template>
  <div class="function-points-content">
    <!-- 垂直布局：功能模块列表在上，详情在下 -->
    <div class="fp-vertical-layout">
      <!-- 功能模块列表区域 -->
      <div class="fp-list-section">
        <div class="fp-list-header">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索功能模块..."
            clearable
            style="width: 300px; margin-right: 12px;"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button
            type="primary"
            size="small"
            @click="handleAddFunctionPoint"
          >
            <el-icon><Plus /></el-icon>
            手动添加
          </el-button>
        </div>

          <!-- 功能模块折叠卡片列表 -->
        <div class="fp-cards-list">
          <el-collapse v-model="expandedFpIds" accordion @change="handleCollapseChange">
            <el-collapse-item
              v-for="fp in filteredFunctionPoints"
              :key="fp.id"
              :name="fp.id"
              class="fp-collapse-item"
            >
              <template #title>
                <div class="fp-card-header" @click="handleSelectFp(fp.id)">
                  <div class="fp-card-info">
                    <el-icon class="fp-icon" :class="fp.parent_module ? 'fp-icon-sub' : 'fp-icon-main'">
                      <component :is="fp.parent_module ? Document : Folder" />
                    </el-icon>
                    <span class="fp-name">{{ fp.name }}</span>
                    <el-tag
                      :type="getConfidenceTagType(fp.match_confidence)"
                      size="small"
                      style="margin-left: 8px;"
                    >
                      {{ getConfidenceLabel(fp.match_confidence) }}
                    </el-tag>
                  </div>
                  <div class="fp-card-actions" @click.stop>
                    <el-button
                      v-if="!fp.editing"
                      type="text"
                      size="small"
                      @click.stop="handleEdit(fp)"
                    >
                      <el-icon><Edit /></el-icon>
                    </el-button>
                    <el-button
                      v-if="fp.editing"
                      type="text"
                      size="small"
                      @click.stop="handleSaveFpName(fp)"
                    >
                      <el-icon><Check /></el-icon>
                    </el-button>
                    <el-button
                      v-if="fp.editing"
                      type="text"
                      size="small"
                      @click.stop="handleCancelFpNameEdit(fp)"
                    >
                      <el-icon><Close /></el-icon>
                    </el-button>
                    <el-button
                      type="text"
                      size="small"
                      @click.stop="handleDelete(fp.id)"
                    >
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                </div>
              </template>

              <div class="fp-card-content">
                <div v-if="fp.description" class="fp-description">
                  {{ fp.description }}
                </div>
                <div class="fp-preview">
                  {{ getContentPreview(fp.matched_content) }}
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 模块详情编辑区域（选中模块时显示） -->
      <div v-if="selectedFunctionPoint" class="fp-detail-section">
        <el-card shadow="never" class="detail-card">
          <template #header>
            <div class="detail-header">
              <div>
                <h4>{{ selectedFunctionPoint.name }}</h4>
                <p v-if="selectedFunctionPoint.description" class="module-description">
                  {{ selectedFunctionPoint.description }}
                </p>
              </div>
              <div class="detail-actions">
                <el-button
                  type="primary"
                  size="small"
                  :loading="rematching"
                  @click="handleRematch"
                >
                  重新匹配原文
                </el-button>
              </div>
            </div>
          </template>

          <div class="detail-content">
            <!-- 原文编辑区域 -->
            <div class="content-editor">
              <div class="editor-header">
                <span class="editor-label">匹配的原文内容</span>
                <el-button
                  text
                  size="small"
                  @click="showFullDoc = !showFullDoc"
                >
                  {{ showFullDoc ? '收起完整文档' : '查看完整文档' }}
                </el-button>
              </div>
              
              <el-input
                v-model="editingContent"
                type="textarea"
                :rows="showFullDoc ? 8 : 12"
                placeholder="在此编辑匹配的原文内容..."
                class="content-textarea"
              />

              <!-- 完整文档查看器（可折叠） -->
              <el-collapse-transition>
                <div v-if="showFullDoc" class="full-doc-viewer">
                  <div class="viewer-toolbar">
                    <el-tooltip content="在文档中选择文本，然后点击下方按钮应用">
                      <span class="tooltip-text">💡 提示：选择文本后点击"使用选中文本"按钮</span>
                    </el-tooltip>
                  </div>
                  <div
                    class="requirement-doc"
                    @mouseup="handleTextSelection"
                    ref="docContentRef"
                  >
                    <pre
                      v-html="highlightedContent"
                      class="doc-content"
                    ></pre>
                  </div>
                  <!-- 文本选择按钮 -->
                  <transition name="fade">
                    <div
                      v-if="showSelectionButton"
                      class="selection-button"
                      :style="selectionButtonStyle"
                    >
                      <el-button
                        type="primary"
                        size="small"
                        @click="handleUseSelectedText"
                      >
                        使用选中文本
                      </el-button>
                    </div>
                  </transition>
                </div>
              </el-collapse-transition>
            </div>

            <!-- 操作按钮 -->
            <div class="detail-footer">
              <el-tag size="small">
                匹配位置: 第 {{ selectedFunctionPoint.matched_positions?.[0] || 0 }} - {{ selectedFunctionPoint.matched_positions?.[1] || 0 }} 行
              </el-tag>
              <div class="footer-actions">
                <el-button size="small" @click="handleCancelEdit">取消</el-button>
                <el-button type="primary" size="small" @click="handleSaveEdit">保存</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 未选择模块时的提示 -->
      <div v-else class="fp-detail-empty">
        <el-empty description="请选择一个功能模块查看和编辑详情" />
      </div>
    </div>

    <!-- 底部操作按钮 -->
    <div class="fp-footer-actions">
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="confirming">
        确认并生成测试用例
      </el-button>
    </div>

    <!-- 添加功能模块对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="手动添加功能模块"
      width="600px"
      append-to-body
    >
      <el-form :model="newFunctionPoint" label-width="100px">
        <el-form-item label="功能模块名称" required>
          <el-input v-model="newFunctionPoint.name" placeholder="请输入功能模块名称" />
        </el-form-item>
        <el-form-item label="模块描述">
          <el-input
            v-model="newFunctionPoint.description"
            type="textarea"
            :rows="2"
            placeholder="请输入功能模块描述（可选）"
          />
        </el-form-item>
        <el-form-item label="匹配原文">
          <el-input
            v-model="newFunctionPoint.matched_content"
            type="textarea"
            :rows="6"
            placeholder="请从需求文档中选择或输入相关原文内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddConfirm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { aiApi } from '@/apis/ai'
import { Delete, Edit, Folder, Document, Plus, Search, Check, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  functionPoints: {
    type: Array,
    default: () => []
  },
  requirementDoc: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['confirm', 'cancel'])

const searchKeyword = ref('')
const expandedFpIds = ref([])
const selectedFpId = ref(null)
const confirming = ref(false)
const rematching = ref(false)
const showAddDialog = ref(false)
const showFullDoc = ref(false)
const editingContent = ref('')
const originalEditingContent = ref('')

// 文本选择相关
const showSelectionButton = ref(false)
const selectionButtonStyle = ref({})
const selectedText = ref('')
const selectedRange = ref({ start: 0, end: 0 })
const docContentRef = ref(null)

const newFunctionPoint = ref({
  name: '',
  description: '',
  matched_content: ''
})

const operationHistory = ref([])

// 深拷贝功能点列表
const functionPointsList = ref([])

watch(() => props.functionPoints, (newVal) => {
  functionPointsList.value = newVal.map(fp => ({
    ...fp,
    editing: false,
    editName: fp.name
  }))
  if (functionPointsList.value.length > 0 && !selectedFpId.value) {
    selectedFpId.value = functionPointsList.value[0].id
    expandedFpIds.value = [selectedFpId.value]
  }
}, { immediate: true })

// 处理折叠面板变化
const handleCollapseChange = (activeNames) => {
  if (activeNames && activeNames.length > 0) {
    const fpId = Array.isArray(activeNames) ? activeNames[0] : activeNames
    handleSelectFp(fpId)
  }
}

// 选中功能点
const handleSelectFp = (fpId) => {
  selectedFpId.value = fpId
  // 初始化编辑内容
  const fp = functionPointsList.value.find(f => f.id === fpId)
  if (fp) {
    editingContent.value = fp.matched_content || ''
    originalEditingContent.value = editingContent.value
    console.log('✅ 选中功能点:', fp.name, '原文内容长度:', editingContent.value.length)
  }
}

// 监听折叠面板展开，自动选中（保留作为备用）
watch(expandedFpIds, (newVal) => {
  if (newVal && newVal.length > 0) {
    const fpId = Array.isArray(newVal) ? newVal[0] : newVal
    if (selectedFpId.value !== fpId) {
      handleSelectFp(fpId)
    }
  }
})

const filteredFunctionPoints = computed(() => {
  if (!searchKeyword.value) {
    return functionPointsList.value
  }
  const keyword = searchKeyword.value.toLowerCase()
  return functionPointsList.value.filter(fp =>
    fp.name.toLowerCase().includes(keyword) ||
    fp.matched_content.toLowerCase().includes(keyword)
  )
})

const selectedFunctionPoint = computed(() => {
  return functionPointsList.value.find(fp => fp.id === selectedFpId.value)
})

const highlightedContent = computed(() => {
  if (!selectedFunctionPoint.value || !props.requirementDoc) {
    return ''
  }

  const fp = selectedFunctionPoint.value
  const docLines = props.requirementDoc.split('\n')
  const startLine = fp.matched_positions?.[0] || 0
  const endLine = fp.matched_positions?.[1] || docLines.length - 1

  const startIdx = Math.max(0, Math.min(startLine - 1, docLines.length - 1))
  const endIdx = Math.max(startIdx, Math.min(endLine - 1, docLines.length - 1))

  const escapeHtml = (text) => {
    return text.replace(/[<>&"']/g, (char) => {
      const map = { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }
      return map[char]
    })
  }

  const highlightedLines = docLines.map((line, index) => {
    const escapedLine = escapeHtml(line)
    const lineNumber = index + 1
    const isHighlighted = index >= startIdx && index <= endIdx

    const lineNumberPart = `<span class="line-number" style="color: #909399; margin-right: 8px; user-select: none; display: inline-block; min-width: 50px; text-align: right;">${lineNumber}</span>`

    if (isHighlighted) {
      return `<span class="doc-line highlighted-line" data-line="${lineNumber}" style="background-color: #fff3cd; display: block; padding: 2px 4px; border-left: 3px solid #409eff; margin: 1px 0; cursor: text;">${lineNumberPart}<span class="line-content">${escapedLine || ' '}</span></span>`
    }
    return `<span class="doc-line" data-line="${lineNumber}" style="display: block; padding: 2px 4px; cursor: text;">${lineNumberPart}<span class="line-content">${escapedLine || ' '}</span></span>`
  })

  return highlightedLines.join('')
})

const getConfidenceTagType = (confidence) => {
  const map = {
    high: 'success',
    medium: 'warning',
    low: 'danger'
  }
  return map[confidence] || 'info'
}

const getConfidenceLabel = (confidence) => {
  const map = {
    high: '高置信度',
    medium: '中置信度',
    low: '低置信度'
  }
  return map[confidence] || '未知'
}

const getContentPreview = (content) => {
  if (!content) return '无匹配内容'
  return content.length > 100 ? content.substring(0, 100) + '...' : content
}

const editInputRef = ref(null)

const handleEdit = (fp) => {
  fp.editing = true
  fp.editName = fp.name
  nextTick(() => {
    // 聚焦到编辑输入框
    const editInput = document.querySelector(`.fp-card-content input`)
    if (editInput) {
      editInput.focus()
      editInput.select()
    }
  })
}

const handleCancelFpNameEdit = (fp) => {
  fp.editing = false
  fp.editName = fp.name
}

const handleSaveFpName = (fp) => {
  if (!fp.editName || !fp.editName.trim()) {
    ElMessage.warning('功能模块名称不能为空')
    return
  }

  const oldName = fp.name
  fp.name = fp.editName.trim()
  fp.editing = false

  if (oldName !== fp.name) {
    operationHistory.value.push({
      type: 'RENAME_FP',
      original: { ...fp, name: oldName },
      adjusted: { ...fp },
      timestamp: Date.now()
    })
  }
}

const handleDelete = (fpId) => {
  const fp = functionPointsList.value.find(f => f.id === fpId)
  if (!fp) return

  operationHistory.value.push({
    type: 'DELETE_FP',
    original: { ...fp },
    timestamp: Date.now()
  })

  const index = functionPointsList.value.findIndex(f => f.id === fpId)
  if (index !== -1) {
    functionPointsList.value.splice(index, 1)
  }

  if (selectedFpId.value === fpId) {
    if (functionPointsList.value.length > 0) {
      selectedFpId.value = functionPointsList.value[0].id
      expandedFpIds.value = [selectedFpId.value]
    } else {
      selectedFpId.value = null
      expandedFpIds.value = []
    }
  }

  ElMessage.success('已删除功能模块')
}

const handleAddFunctionPoint = () => {
  newFunctionPoint.value = {
    name: '',
    description: '',
    matched_content: ''
  }
  showAddDialog.value = true
}

const handleAddConfirm = () => {
  if (!newFunctionPoint.value.name || !newFunctionPoint.value.name.trim()) {
    ElMessage.warning('请输入功能模块名称')
    return
  }

  const newFp = {
    id: `module_manual_${Date.now()}`,
    name: newFunctionPoint.value.name.trim(),
    description: newFunctionPoint.value.description?.trim() || '',
    keywords: [],
    exact_phrases: [],
    section_hint: '',
    matched_content: newFunctionPoint.value.matched_content || '',
    matched_positions: [0, 0],
    match_confidence: 'low',
    editing: false,
    editName: newFunctionPoint.value.name.trim()
  }

  functionPointsList.value.push(newFp)

  operationHistory.value.push({
    type: 'ADD_FP',
    adjusted: { ...newFp },
    timestamp: Date.now()
  })

  showAddDialog.value = false
  selectedFpId.value = newFp.id
  expandedFpIds.value = [newFp.id]
  ElMessage.success('已添加功能模块')
}

const handleRematch = async () => {
  if (!selectedFunctionPoint.value) {
    ElMessage.warning('请先选择一个功能模块')
    return
  }

  if (!props.requirementDoc || !props.requirementDoc.trim()) {
    ElMessage.warning('需求文档不可用，无法重新匹配')
    return
  }

  const fp = selectedFunctionPoint.value
  rematching.value = true

  try {
    const moduleData = {
      name: fp.name,
      description: fp.description || '',
      keywords: fp.keywords || [],
      exact_phrases: fp.exact_phrases || [],
      section_hint: fp.section_hint || ''
    }

    const allModules = functionPointsList.value.map(item => ({
      name: item.name,
      description: item.description || '',
      keywords: item.keywords || [],
      exact_phrases: item.exact_phrases || [],
      section_hint: item.section_hint || ''
    }))

    const response = await aiApi.rematchModuleContent({
      requirement_doc: props.requirementDoc,
      module_data: moduleData,
      all_modules: allModules
    })

    if (response.data.code !== 0) {
      throw new Error(response.data.message || '重新匹配失败')
    }

    const result = response.data.data

    const oldMatchedContent = fp.matched_content
    const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

    fp.matched_content = result.matched_content || fp.matched_content
    fp.matched_positions = result.matched_positions || fp.matched_positions
    fp.match_confidence = result.match_confidence || fp.match_confidence

    // 更新编辑内容
    editingContent.value = fp.matched_content
    originalEditingContent.value = editingContent.value

    operationHistory.value.push({
      type: 'REMATCH_CONTENT',
      original: {
        name: fp.name,
        matched_content: oldMatchedContent,
        matched_positions: oldMatchedPositions
      },
      adjusted: {
        name: fp.name,
        matched_content: result.matched_content,
        matched_positions: result.matched_positions
      },
      timestamp: Date.now()
    })

    ElMessage.success('重新匹配原文成功')
  } catch (error) {
    console.error('重新匹配原文失败:', error)
    ElMessage.error(error?.response?.data?.message || error?.message || '重新匹配原文失败，请稍后重试')
  } finally {
    rematching.value = false
  }
}

// 文本选择处理
const handleTextSelection = () => {
  if (!showFullDoc.value) {
    showSelectionButton.value = false
    return
  }

  setTimeout(() => {
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) {
      showSelectionButton.value = false
      return
    }

    const selectedTextValue = selection.toString().trim()
    if (!selectedTextValue || selectedTextValue.length < 3) {
      showSelectionButton.value = false
      return
    }

    const range = selection.getRangeAt(0)
    if (!docContentRef.value || !docContentRef.value.contains(range.commonAncestorContainer)) {
      showSelectionButton.value = false
      return
    }

    selectedText.value = selectedTextValue

    const rect = range.getBoundingClientRect()
    const containerRect = docContentRef.value?.getBoundingClientRect()

    if (containerRect) {
      selectionButtonStyle.value = {
        position: 'absolute',
        top: `${rect.top - containerRect.top + rect.height + 5}px`,
        left: `${rect.left - containerRect.left}px`,
        zIndex: 1000
      }
    }

    const startLine = getLineNumberFromNode(range.startContainer)
    const endLine = getLineNumberFromNode(range.endContainer)

    if (startLine > 0 && endLine > 0) {
      selectedRange.value = {
        start: Math.min(startLine, endLine),
        end: Math.max(startLine, endLine)
      }
      showSelectionButton.value = true
    } else {
      showSelectionButton.value = false
    }
  }, 10)
}

const getLineNumberFromNode = (node) => {
  if (!node || !docContentRef.value) {
    return 0
  }

  let element = node.nodeType === Node.TEXT_NODE ? node.parentElement : node

  while (element && element !== docContentRef.value) {
    if (element.nodeType === Node.ELEMENT_NODE) {
      const lineNumber = element.getAttribute('data-line')
      if (lineNumber) {
        const lineNum = parseInt(lineNumber, 10)
        if (!isNaN(lineNum) && lineNum > 0) {
          return lineNum
        }
      }
    }
    element = element.parentElement
  }

  return 0
}

const handleUseSelectedText = () => {
  if (!selectedFunctionPoint.value || !selectedText.value) {
    ElMessage.warning('请先选择文本')
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content || ''
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  if (!selectedRange.value.start || !selectedRange.value.end) {
    ElMessage.warning('无法确定选中文本的行号范围')
    return
  }

  fp.matched_content = selectedText.value
  fp.matched_positions = [selectedRange.value.start, selectedRange.value.end]

  editingContent.value = selectedText.value
  originalEditingContent.value = editingContent.value

  operationHistory.value.push({
    type: 'EDIT_MATCHED_CONTENT',
    original: {
      name: fp.name,
      matched_content: oldMatchedContent,
      matched_positions: oldMatchedPositions
    },
    adjusted: {
      name: fp.name,
      matched_content: selectedText.value,
      matched_positions: [selectedRange.value.start, selectedRange.value.end]
    },
    timestamp: Date.now()
  })

  showSelectionButton.value = false
  const selection = window.getSelection()
  if (selection) {
    selection.removeAllRanges()
  }

  ElMessage.success(`已使用选中文本更新匹配内容（第 ${selectedRange.value.start}-${selectedRange.value.end} 行）`)
}

const handleSaveEdit = () => {
  if (!selectedFunctionPoint.value) {
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content || ''
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  fp.matched_content = editingContent.value.trim()
  originalEditingContent.value = editingContent.value.trim()

  operationHistory.value.push({
    type: 'EDIT_MATCHED_CONTENT',
    original: {
      name: fp.name,
      matched_content: oldMatchedContent,
      matched_positions: oldMatchedPositions
    },
    adjusted: {
      name: fp.name,
      matched_content: editingContent.value.trim(),
      matched_positions: fp.matched_positions
    },
    timestamp: Date.now()
  })

  ElMessage.success('已保存编辑内容')
}

const handleCancelEdit = () => {
  if (selectedFunctionPoint.value) {
    editingContent.value = originalEditingContent.value
  }
  ElMessage.info('已取消编辑')
}

const handleConfirm = async () => {
  if (functionPointsList.value.length === 0) {
    ElMessage.warning('请至少保留一个功能模块')
    return
  }

  confirming.value = true
  try {
    emit('confirm', {
      confirmedFunctionPoints: functionPointsList.value.map(fp => ({
        id: fp.id,
        name: fp.name,
        description: fp.description || '',
        keywords: fp.keywords,
        exact_phrases: fp.exact_phrases,
        section_hint: fp.section_hint,
        matched_content: fp.matched_content,
        matched_positions: fp.matched_positions
      })),
      originalFunctionPoints: props.functionPoints,
      operationHistory: operationHistory.value
    })
  } finally {
    confirming.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.function-points-content {
  width: 100%;
}

.fp-vertical-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 功能模块列表区域 */
.fp-list-section {
  flex: 0 0 auto;
}

.fp-list-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.fp-cards-list {
  max-height: 400px;
  overflow-y: auto;
}

.fp-collapse-item {
  margin-bottom: 8px;
}

.fp-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 8px;
}

.fp-card-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.fp-icon {
  margin-right: 8px;
  font-size: 16px;
}

.fp-icon-main {
  color: var(--el-color-primary);
}

.fp-icon-sub {
  color: var(--el-color-info);
}

.fp-name {
  font-weight: 500;
  font-size: 14px;
}

.fp-card-actions {
  display: flex;
  gap: 4px;
}

.fp-card-content {
  padding: 8px 0;
}

.fp-description {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
  line-height: 1.5;
}

.fp-preview {
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.4;
}

/* 模块详情区域 */
.fp-detail-section {
  flex: 1;
  min-height: 400px;
}

.detail-card {
  border: 1px solid var(--el-border-color);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.detail-header h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.module-description {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-label {
  font-weight: 500;
  font-size: 14px;
}

.content-textarea {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.full-doc-viewer {
  position: relative;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}

.viewer-toolbar {
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color);
}

.tooltip-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.requirement-doc {
  padding: 16px;
  background-color: var(--el-bg-color-page);
  max-height: 400px;
  overflow-y: auto;
  position: relative;
}

.doc-content {
  margin: 0;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.highlighted-line {
  transition: background-color 0.2s;
}

.highlighted-line:hover {
  background-color: #ffe69c !important;
}

.selection-button {
  position: absolute;
  background: white;
  padding: 4px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.detail-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color);
}

.footer-actions {
  display: flex;
  gap: 8px;
}

.fp-detail-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.fp-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color);
  margin-top: 16px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media screen and (max-width: 768px) {
  .fp-vertical-layout {
    gap: 12px;
  }

  .detail-header {
    flex-direction: column;
    gap: 12px;
  }

  .detail-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .requirement-doc {
    max-height: 300px;
  }
}
</style>

