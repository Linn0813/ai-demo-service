<template>
  <el-dialog
    v-model="visible"
    title="功能模块确认"
    width="90%"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <div class="function-points-confirm">
      <el-row :gutter="16">
        <!-- 左侧：功能模块列表 -->
        <el-col :span="10">
          <div class="fp-list-header">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索功能模块..."
              clearable
              style="margin-bottom: 12px"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <div class="fp-stats">
              <span>共 {{ filteredFunctionPoints.length }} 个功能模块</span>
              <el-button
                type="primary"
                size="small"
                @click="handleAddFunctionPoint"
              >
                <el-icon><Plus /></el-icon>
                手动添加
              </el-button>
            </div>
          </div>

          <el-scrollbar height="500px">
            <div class="fp-list">
              <template v-for="fp in filteredFunctionPoints" :key="fp.id">
                <!-- 主模块：没有parent_module的模块 -->
                <div
                  v-if="!fp.parent_module"
                  :class="['fp-item', 'fp-item-main', { active: selectedFpId === fp.id }]"
                  @click="selectFunctionPoint(fp.id)"
                >
                  <div class="fp-item-header">
                    <el-input
                      v-if="fp.editing"
                      v-model="fp.editName"
                      size="small"
                      @blur="handleSaveEdit(fp)"
                      @keyup.enter="handleSaveEdit(fp)"
                      @keyup.esc="handleCancelEdit(fp)"
                      ref="editInputRef"
                    />
                    <span v-else class="fp-name">
                      <el-icon class="fp-icon-main"><Folder /></el-icon>
                      {{ fp.name }}
                    </span>
                    <div v-if="fp.description" class="fp-description">{{ fp.description }}</div>
                    <div class="fp-actions">
                      <el-button
                        v-if="!fp.editing"
                        type="text"
                        size="small"
                        @click.stop="handleEdit(fp)"
                      >
                        <el-icon><Edit /></el-icon>
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
                  <div class="fp-meta">
                    <el-tag
                      :type="getConfidenceTagType(fp.match_confidence)"
                      size="small"
                    >
                      {{ getConfidenceLabel(fp.match_confidence) }}
                    </el-tag>
                    <span class="fp-preview">
                      {{ getContentPreview(fp.matched_content) }}
                    </span>
                  </div>
                </div>
                <!-- 子模块：有parent_module的模块 -->
                <div
                  v-else
                  :class="['fp-item', 'fp-item-sub', { active: selectedFpId === fp.id }]"
                  @click="selectFunctionPoint(fp.id)"
                >
                  <div class="fp-item-header">
                    <el-input
                      v-if="fp.editing"
                      v-model="fp.editName"
                      size="small"
                      @blur="handleSaveEdit(fp)"
                      @keyup.enter="handleSaveEdit(fp)"
                      @keyup.esc="handleCancelEdit(fp)"
                      ref="editInputRef"
                    />
                    <span v-else class="fp-name">
                      <span class="fp-indent">└─</span>
                      <el-icon class="fp-icon-sub"><Document /></el-icon>
                      {{ fp.name }}
                    </span>
                    <div v-if="fp.description" class="fp-description">{{ fp.description }}</div>
                    <div class="fp-actions">
                      <el-button
                        v-if="!fp.editing"
                        type="text"
                        size="small"
                        @click.stop="handleEdit(fp)"
                      >
                        <el-icon><Edit /></el-icon>
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
                  <div class="fp-meta">
                    <el-tag
                      :type="getConfidenceTagType(fp.match_confidence)"
                      size="small"
                    >
                      {{ getConfidenceLabel(fp.match_confidence) }}
                    </el-tag>
                    <span class="fp-preview">
                      {{ getContentPreview(fp.matched_content) }}
                    </span>
                  </div>
                </div>
              </template>
            </div>
          </el-scrollbar>
        </el-col>

        <!-- 右侧：原文查看 -->
        <el-col :span="14">
          <div v-if="selectedFunctionPoint" class="content-viewer">
            <div class="viewer-header">
              <div>
                <h4>{{ selectedFunctionPoint.name }}</h4>
                <p v-if="selectedFunctionPoint.description" class="module-description">
                  {{ selectedFunctionPoint.description }}
                </p>
              </div>
              <div class="viewer-actions">
                <el-button-group size="small" style="margin-right: 12px">
                  <el-button
                    :type="viewMode === 'snippet' ? 'primary' : ''"
                    @click="viewMode = 'snippet'"
                  >
                    模块片段
                  </el-button>
                  <el-button
                    :type="viewMode === 'full' ? 'primary' : ''"
                    @click="viewMode = 'full'"
                  >
                    完整文档
                  </el-button>
                  <el-button
                    :type="viewMode === 'edit' ? 'primary' : ''"
                    @click="viewMode = 'edit'"
                  >
                    编辑模式
                  </el-button>
                </el-button-group>
                <el-button
                  v-if="viewMode !== 'edit'"
                  type="primary"
                  size="small"
                  :loading="rematching"
                  @click="handleRematch"
                >
                  重新匹配原文
                </el-button>
              </div>
            </div>
            <div class="viewer-content">
              <el-scrollbar height="450px" ref="scrollbarRef">
                <!-- 模块片段模式：直接编辑 -->
                <div v-if="viewMode === 'snippet'" class="snippet-mode">
                  <el-input
                    v-model="snippetContent"
                    type="textarea"
                    :rows="20"
                    placeholder="在此编辑模块片段..."
                    class="snippet-textarea"
                  />
                </div>
                <!-- 编辑模式：文本编辑器（保留用于高级编辑） -->
                <div v-else-if="viewMode === 'edit'" class="edit-mode">
                  <div class="edit-toolbar">
                    <el-row :gutter="12" style="margin-bottom: 8px">
                      <el-col :span="8">
                        <el-input-number
                          v-model="editStartLine"
                          :min="1"
                          :max="maxDocLines"
                          placeholder="起始行"
                          size="small"
                          style="width: 100%"
                        />
                      </el-col>
                      <el-col :span="8">
                        <el-input-number
                          v-model="editEndLine"
                          :min="1"
                          :max="maxDocLines"
                          placeholder="结束行"
                          size="small"
                          style="width: 100%"
                        />
                      </el-col>
                      <el-col :span="8">
                        <el-button size="small" @click="applyLineRange">应用行号范围</el-button>
                      </el-col>
                    </el-row>
                    <el-alert
                      type="info"
                      :closable="false"
                      show-icon
                      style="margin-bottom: 8px"
                    >
                      <template #default>
                        <span>提示：可以输入行号范围自动提取，或直接在下方编辑框中修改文本</span>
                      </template>
                    </el-alert>
                  </div>
                  <el-input
                    v-model="editingContent"
                    type="textarea"
                    :rows="18"
                    placeholder="在此编辑匹配的原文内容..."
                    class="edit-textarea"
                  />
                </div>
                <!-- 完整文档模式：显示内容 + 选择功能 -->
                <div v-else class="full-doc-mode">
                  <!-- 工具栏 -->
                  <div class="full-doc-toolbar">
                    <el-tooltip content="点击行号选择/取消选择行">
                      <el-button
                        size="small"
                        :type="lineSelectionMode ? 'primary' : ''"
                        @click="toggleLineSelectionMode"
                      >
                        {{ lineSelectionMode ? '取消行号选择' : '启用行号选择' }}
                      </el-button>
                    </el-tooltip>
                    <el-collapse v-model="showAdvancedOptions" style="display: inline-block; margin-left: 8px;">
                      <el-collapse-item name="advanced" title="高级选项（输入行号范围）">
                        <div style="display: flex; gap: 8px; align-items: center;">
                          <el-input
                            v-model="lineRangeInput"
                            placeholder="输入行号范围，如：1-3, 5-7, 10"
                            size="small"
                            style="width: 300px;"
                            @keyup.enter="applyLineRangeInput"
                          />
                          <el-button size="small" @click="applyLineRangeInput">应用</el-button>
                        </div>
                      </el-collapse-item>
                    </el-collapse>
                    <div v-if="hasSelectedLines" style="margin-left: auto;">
                      <el-tag type="info" size="small" style="margin-right: 8px;">
                        已选中 {{ selectedLinesCountFromCheckboxes }} 行
                      </el-tag>
                      <el-button
                        type="primary"
                        size="small"
                        @click="applySelectedLinesToSnippet"
                      >
                        使用选中的 {{ selectedLinesCountFromCheckboxes }} 行
                      </el-button>
                    </div>
                  </div>

                  <!-- 文档内容 -->
                  <div
                    class="requirement-doc"
                    style="position: relative;"
                    @mouseup="handleTextSelection"
                    @click="handleLineClick"
                    @change="handleCheckboxChange"
                  >
                    <pre
                      v-html="highlightedContent"
                      class="doc-content"
                      ref="docContentRef"
                    ></pre>
                  </div>
                  <!-- 文本选择浮动按钮 -->
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

                  <!-- 选中预览（即时反馈） -->
                  <transition name="slide-up">
                    <div v-if="showSelectionPreview" class="selection-preview">
                      <div class="preview-header">
                        <el-tag type="info" size="small">
                          已选中 {{ selectedLinesCount }} 行
                        </el-tag>
                        <el-button
                          type="text"
                          size="small"
                          @click="clearSelection"
                        >
                          清除
                        </el-button>
                      </div>
                      <div class="preview-content">
                        <pre>{{ selectedContentPreview }}</pre>
                      </div>
                      <div class="preview-actions">
                        <el-button
                          type="primary"
                          size="small"
                          @click="applyToSnippet"
                        >
                          应用到模块片段
                        </el-button>
                      </div>
                    </div>
                  </transition>
                </div>
              </el-scrollbar>
            </div>
            <div class="viewer-footer">
              <el-tag size="small">
                匹配位置: 第 {{ selectedFunctionPoint.matched_positions?.[0] || 0 }} - {{ selectedFunctionPoint.matched_positions?.[1] || 0 }} 行
              </el-tag>
              <!-- 模块片段模式：保存/取消按钮 -->
              <div v-if="viewMode === 'snippet'" class="snippet-actions" style="margin-left: auto">
                <el-button size="small" @click="handleCancelSnippetEdit">取消</el-button>
                <el-button type="primary" size="small" @click="handleSaveSnippetEdit">保存</el-button>
              </div>
              <!-- 编辑模式：保存/取消按钮 -->
              <div v-else-if="viewMode === 'edit'" class="edit-actions" style="margin-left: auto">
                <el-button size="small" @click="handleCancelEditContent">取消</el-button>
                <el-button type="primary" size="small" @click="handleSaveEditContent">保存</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="请选择一个功能模块查看原文" />
        </el-col>
      </el-row>
    </div>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="confirming">
        确认并生成测试用例
      </el-button>
    </template>

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
  </el-dialog>
</template>

<script setup>
import { aiApi } from '@/apis/ai'
import { Delete, Edit, Folder, Document, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  functionPoints: {
    type: Array,
    default: () => []
  },
  requirementDoc: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const searchKeyword = ref('')
const selectedFpId = ref(null)
const confirming = ref(false)
const rematching = ref(false) // 重新匹配加载状态
const showAddDialog = ref(false)
const viewMode = ref('snippet') // 视图模式：'snippet' | 'full' | 'edit'
const newFunctionPoint = ref({
  name: '',
  description: '',
  matched_content: ''
})
const operationHistory = ref([])
const scrollbarRef = ref(null)
const docContentRef = ref(null)

// 模块片段编辑相关
const snippetContent = ref('')
const originalSnippetContent = ref('')

// 编辑模式相关
const editingContent = ref('')
const editStartLine = ref(null)
const editEndLine = ref(null)
const maxDocLines = ref(0)

// 文本选择相关
const showSelectionButton = ref(false)
const selectionButtonStyle = ref({})
const selectedText = ref('')
const selectedRange = ref({ start: 0, end: 0 })

// 选中预览相关
const showSelectionPreview = ref(false)
const selectedContentPreview = ref('')
const selectedLinesCount = ref(0)

// 行号选择相关
const lineSelectionMode = ref(false) // 是否启用行号点击选择模式
const selectedLines = ref({}) // 选中的行号 { 1: true, 3: true, 5: true }

// 行号范围输入相关
const showAdvancedOptions = ref([]) // 是否显示高级选项（el-collapse需要数组）
const lineRangeInput = ref('') // 行号范围输入

// 深拷贝功能点列表，避免直接修改props
const functionPointsList = ref([])

watch(() => props.functionPoints, (newVal) => {
  functionPointsList.value = newVal.map(fp => ({
    ...fp,
    editing: false,
    editName: fp.name
  }))
  if (functionPointsList.value.length > 0 && !selectedFpId.value) {
    selectedFpId.value = functionPointsList.value[0].id
  }
}, { immediate: true })

// 当切换到不同模式或切换功能模块时，初始化相应状态
watch([viewMode, selectedFpId], () => {
  if (viewMode.value === 'snippet' && selectedFunctionPoint.value) {
    // 进入模块片段模式时，初始化编辑内容
    snippetContent.value = selectedFunctionPoint.value.matched_content || ''
    originalSnippetContent.value = snippetContent.value
  } else if (viewMode.value === 'full' && selectedFunctionPoint.value) {
    // 进入完整文档模式时，自动滚动到高亮区域
    nextTick(() => {
      scrollToHighlightedArea()
    })
  } else if (viewMode.value === 'edit') {
    // 进入编辑模式时，初始化编辑内容
    if (selectedFunctionPoint.value) {
      editingContent.value = selectedFunctionPoint.value.matched_content || ''
      const positions = selectedFunctionPoint.value.matched_positions || []
      editStartLine.value = positions[0] || null
      editEndLine.value = positions[1] || null
      // 计算最大行数
      if (props.requirementDoc) {
        maxDocLines.value = props.requirementDoc.split('\n').length
      }
    }
  } else {
    // 退出其他模式时，隐藏选择按钮和预览
    showSelectionButton.value = false
    showSelectionPreview.value = false
  }

  // 当切换模块时，重置选择状态
  if (selectedFpId.value) {
    showSelectionButton.value = false
    showSelectionPreview.value = false
    selectedLines.value = {}
  }
})

// 监听点击事件，点击外部区域时隐藏选择按钮
watch(() => visible.value, (newVal) => {
  if (!newVal) {
    showSelectionButton.value = false
  }
})

// 滚动到高亮区域
const scrollToHighlightedArea = () => {
  if (!docContentRef.value || !selectedFunctionPoint.value) return

  const fp = selectedFunctionPoint.value
  const startLine = fp.matched_positions?.[0] || 0

  // 查找第一个高亮的行元素
  const highlightedLine = docContentRef.value.querySelector('.highlighted-line')
  if (highlightedLine && scrollbarRef.value) {
    // 获取滚动容器
    const scrollContainer = scrollbarRef.value.$el?.querySelector('.el-scrollbar__wrap')
    if (scrollContainer) {
      // 计算目标位置（高亮行的位置减去一些偏移，使其显示在视口上方）
      const targetOffset = highlightedLine.offsetTop - 100
      scrollContainer.scrollTo({
        top: Math.max(0, targetOffset),
        behavior: 'smooth'
      })
    }
  }
}

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
  if (!selectedFunctionPoint.value) {
    return ''
  }
  const fp = selectedFunctionPoint.value
  const matchedContent = fp.matched_content

  // 如果没有匹配内容，显示提示
  if (!matchedContent || !matchedContent.trim()) {
    return '<p style="color: #909399;">该模块暂无匹配的原文内容</p>'
  }

  // 转义HTML特殊字符的工具函数
  const escapeHtml = (text) => {
    return text.replace(/[<>&"']/g, (char) => {
      const map = { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }
      return map[char]
    })
  }

  if (viewMode.value === 'full') {
    // 完整文档模式：显示整个需求文档，根据行号范围高亮显示匹配的内容
    if (!props.requirementDoc) {
      return '<p style="color: #909399;">完整文档不可用</p>'
    }

    const docLines = props.requirementDoc.split('\n')
    const startLine = fp.matched_positions?.[0] || 0
    const endLine = fp.matched_positions?.[1] || docLines.length - 1

    // 确保行号在有效范围内（行号从1开始，数组索引从0开始）
    const startIdx = Math.max(0, Math.min(startLine - 1, docLines.length - 1))
    const endIdx = Math.max(startIdx, Math.min(endLine - 1, docLines.length - 1))

    // 构建高亮后的文档（添加行号，便于选择）
    const highlightedLines = docLines.map((line, index) => {
      const escapedLine = escapeHtml(line)
      const lineNumber = index + 1
      const isSelected = selectedLines.value[lineNumber] || false
      const isHighlighted = index >= startIdx && index <= endIdx

      // 构建行号部分（支持点击选择）
      let lineNumberPart = ''
      if (lineSelectionMode.value) {
        // 行号选择模式：显示复选框
        const checkboxChecked = isSelected ? 'checked' : ''
        lineNumberPart = `<input type="checkbox" class="line-checkbox" data-line="${lineNumber}" ${checkboxChecked} style="margin-right: 8px; cursor: pointer;" />`
      } else {
        // 普通模式：显示行号
        lineNumberPart = `<span class="line-number" style="color: #909399; margin-right: 8px; user-select: none; display: inline-block; min-width: 50px; text-align: right;">${lineNumber}</span>`
      }

      // 如果当前行在匹配范围内或被选中，添加高亮样式
      if (isHighlighted || isSelected) {
        const bgColor = isSelected ? '#e6f7ff' : '#fff3cd'
        const borderColor = isSelected ? '#1890ff' : '#409eff'
        return `<span class="doc-line ${isHighlighted ? 'highlighted-line' : ''} ${isSelected ? 'line-selected' : ''}" data-line="${lineNumber}" style="background-color: ${bgColor}; display: block; padding: 2px 4px; border-left: 3px solid ${borderColor}; margin: 1px 0; cursor: ${lineSelectionMode.value ? 'pointer' : 'text'};" data-selected="${isSelected}">${lineNumberPart}<span class="line-content">${escapedLine || ' '}</span></span>`
      }
      return `<span class="doc-line" data-line="${lineNumber}" style="display: block; padding: 2px 4px; cursor: ${lineSelectionMode.value ? 'pointer' : 'text'};" data-selected="false">${lineNumberPart}<span class="line-content">${escapedLine || ' '}</span></span>`
    })

    return highlightedLines.join('')
  } else {
    // 模块片段模式：只显示该模块对应的原文片段
    const highlighted = escapeHtml(matchedContent)
    return highlighted.replace(/\n/g, '<br>')
  }
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
  return content.length > 80 ? content.substring(0, 80) + '...' : content
}

const selectFunctionPoint = (fpId) => {
  selectedFpId.value = fpId
}

const handleEdit = (fp) => {
  fp.editing = true
  fp.editName = fp.name
  nextTick(() => {
    // 聚焦输入框
    const input = document.querySelector(`input[value="${fp.name}"]`)
    if (input) input.focus()
  })
}

const handleSaveEdit = (fp) => {
  if (!fp.editName || !fp.editName.trim()) {
    ElMessage.warning('功能模块名称不能为空')
    return
  }

  const oldName = fp.name
  fp.name = fp.editName.trim()
  fp.editing = false

  // 记录操作历史
  if (oldName !== fp.name) {
    operationHistory.value.push({
      type: 'RENAME_FP',
      original: { ...fp, name: oldName },
      adjusted: { ...fp },
      timestamp: Date.now()
    })
  }
}

const handleCancelEdit = (fp) => {
  fp.editing = false
  fp.editName = fp.name
}

const handleDelete = (fpId) => {
  const fp = functionPointsList.value.find(f => f.id === fpId)
  if (!fp) return

  // 记录操作历史
  operationHistory.value.push({
    type: 'DELETE_FP',
    original: { ...fp },
    timestamp: Date.now()
  })

  // 删除功能点
  const index = functionPointsList.value.findIndex(f => f.id === fpId)
  if (index !== -1) {
    functionPointsList.value.splice(index, 1)
  }

  // 如果删除的是当前选中的，选择下一个
  if (selectedFpId.value === fpId) {
    if (functionPointsList.value.length > 0) {
      selectedFpId.value = functionPointsList.value[0].id
    } else {
      selectedFpId.value = null
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

  // 记录操作历史
  operationHistory.value.push({
    type: 'ADD_FP',
    adjusted: { ...newFp },
    timestamp: Date.now()
  })

  showAddDialog.value = false
  selectedFpId.value = newFp.id
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
    // 准备请求数据
    const moduleData = {
      name: fp.name,
      description: fp.description || '',
      keywords: fp.keywords || [],
      exact_phrases: fp.exact_phrases || [],
      section_hint: fp.section_hint || ''
    }

    // 准备所有模块数据（用于边界检测）
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

    // 保存旧的匹配内容（用于操作历史）
    const oldMatchedContent = fp.matched_content
    const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

    // 更新模块的匹配内容
    fp.matched_content = result.matched_content || fp.matched_content
    fp.matched_positions = result.matched_positions || fp.matched_positions
    fp.match_confidence = result.match_confidence || fp.match_confidence

    // 记录操作历史
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

// ========== 文本选择相关功能 ==========

// 处理文本选择
const handleTextSelection = () => {
  if (viewMode.value !== 'full') {
    showSelectionButton.value = false
    return
  }

  // 延迟执行，确保选择已完成
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

    // 检查选择是否在文档容器内
    const range = selection.getRangeAt(0)
    if (!docContentRef.value || !docContentRef.value.contains(range.commonAncestorContainer)) {
      showSelectionButton.value = false
      return
    }

    selectedText.value = selectedTextValue

    // 计算选中文本的位置（用于显示浮动按钮）
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

    // 计算选中的行号范围
    const startLine = getLineNumberFromNode(range.startContainer)
    const endLine = getLineNumberFromNode(range.endContainer)

    if (startLine > 0 && endLine > 0) {
      selectedRange.value = {
        start: Math.min(startLine, endLine),
        end: Math.max(startLine, endLine)
      }
      showSelectionButton.value = true

      // 立即显示预览（即时反馈）
      selectedContentPreview.value = selectedTextValue
      selectedLinesCount.value = selectedRange.value.end - selectedRange.value.start + 1
      showSelectionPreview.value = true

      // 如果启用了行号选择模式，自动勾选对应的行号
      if (lineSelectionMode.value && selectedRange.value.start && selectedRange.value.end) {
        for (let i = selectedRange.value.start; i <= selectedRange.value.end; i++) {
          selectedLines.value[i] = true
        }
      }
    } else {
      showSelectionButton.value = false
      showSelectionPreview.value = false
    }
  }, 10)
}

// 从DOM节点获取行号
const getLineNumberFromNode = (node) => {
  if (!node || !docContentRef.value) {
    return 0
  }

  let element = node.nodeType === Node.TEXT_NODE ? node.parentElement : node

  // 向上查找包含 data-line 属性的元素
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

  // 如果找不到，尝试从文本内容中查找行号（作为备选方案）
  if (node.nodeType === Node.TEXT_NODE && node.textContent) {
    const text = node.textContent.trim()
    // 检查是否是行号（通常在行首）
    const lineNumMatch = text.match(/^(\d+)\s/)
    if (lineNumMatch) {
      const lineNum = parseInt(lineNumMatch[1], 10)
      if (!isNaN(lineNum) && lineNum > 0) {
        return lineNum
      }
    }
  }

  return 0
}

// 使用选中的文本（快速应用，自动切换）
const handleUseSelectedText = () => {
  if (!selectedFunctionPoint.value || !selectedText.value) {
    ElMessage.warning('请先选择文本')
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content || ''
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  // 验证行号范围
  if (!selectedRange.value.start || !selectedRange.value.end) {
    ElMessage.warning('无法确定选中文本的行号范围')
    return
  }

  // 更新匹配内容
  fp.matched_content = selectedText.value
  fp.matched_positions = [selectedRange.value.start, selectedRange.value.end]

  // 记录操作历史
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

  // 隐藏选择按钮和预览，清除选择
  showSelectionButton.value = false
  showSelectionPreview.value = false
  const selection = window.getSelection()
  if (selection) {
    selection.removeAllRanges()
  }

  // 切换到模块片段模式显示结果
  viewMode.value = 'snippet'
  ElMessage.success(`已使用选中文本更新匹配内容（第 ${selectedRange.value.start}-${selectedRange.value.end} 行）`)
}

// 应用到模块片段（从预览应用，不自动切换）
const applyToSnippet = () => {
  if (!selectedFunctionPoint.value || !selectedContentPreview.value) {
    ElMessage.warning('没有选中的内容')
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content || ''
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  // 更新匹配内容
  fp.matched_content = selectedContentPreview.value
  if (selectedRange.value.start && selectedRange.value.end) {
    fp.matched_positions = [selectedRange.value.start, selectedRange.value.end]
  }

  // 记录操作历史
  operationHistory.value.push({
    type: 'EDIT_MATCHED_CONTENT',
    original: {
      name: fp.name,
      matched_content: oldMatchedContent,
      matched_positions: oldMatchedPositions
    },
    adjusted: {
      name: fp.name,
      matched_content: selectedContentPreview.value,
      matched_positions: fp.matched_positions
    },
    timestamp: Date.now()
  })

  // 清除预览和选择
  showSelectionPreview.value = false
  const selection = window.getSelection()
  if (selection) {
    selection.removeAllRanges()
  }

  // 切换到模块片段模式显示结果
  viewMode.value = 'snippet'
  ElMessage.success('已应用到模块片段')
}

// 清除选择
const clearSelection = () => {
  showSelectionPreview.value = false
  selectedContentPreview.value = ''
  selectedLinesCount.value = 0
  selectedRange.value = { start: 0, end: 0 }
  selectedLines.value = {}
  const selection = window.getSelection()
  if (selection) {
    selection.removeAllRanges()
  }

  // 强制更新视图
  if (viewMode.value === 'full') {
    const currentMode = viewMode.value
    viewMode.value = ''
    nextTick(() => {
      viewMode.value = currentMode
    })
  }
}

// ========== 编辑模式相关功能 ==========

// 应用行号范围
const applyLineRange = () => {
  if (!editStartLine.value || !editEndLine.value) {
    ElMessage.warning('请输入起始行和结束行')
    return
  }

  if (editStartLine.value > editEndLine.value) {
    ElMessage.warning('起始行不能大于结束行')
    return
  }

  if (!props.requirementDoc) {
    ElMessage.warning('需求文档不可用')
    return
  }

  const docLines = props.requirementDoc.split('\n')
  const startIdx = Math.max(0, editStartLine.value - 1)
  const endIdx = Math.min(editEndLine.value - 1, docLines.length - 1)

  // 提取对应行的内容
  const extractedLines = docLines.slice(startIdx, endIdx + 1)
  editingContent.value = extractedLines.join('\n')

  ElMessage.success(`已提取第 ${editStartLine.value} 到 ${editEndLine.value} 行的内容`)
}

// 保存编辑内容
const handleSaveEditContent = () => {
  if (!selectedFunctionPoint.value) {
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  // 更新匹配内容
  fp.matched_content = editingContent.value.trim()

  // 如果用户输入了行号范围，使用该范围；否则清空位置信息（因为手动编辑后位置可能不准确）
  if (editStartLine.value && editEndLine.value) {
    fp.matched_positions = [editStartLine.value, editEndLine.value]
  } else {
    // 手动编辑后，尝试从文档中查找匹配位置
    if (props.requirementDoc && editingContent.value.trim()) {
      const docLines = props.requirementDoc.split('\n')
      const contentLines = editingContent.value.trim().split('\n')
      if (contentLines.length > 0) {
        // 查找第一行在文档中的位置
        const firstLine = contentLines[0].trim()
        let foundStart = -1
        for (let i = 0; i < docLines.length; i++) {
          if (docLines[i].trim() === firstLine) {
            foundStart = i + 1
            break
          }
        }
        if (foundStart > 0) {
          fp.matched_positions = [foundStart, foundStart + contentLines.length - 1]
        } else {
          fp.matched_positions = [0, 0] // 无法定位，标记为0
        }
      }
    } else {
      fp.matched_positions = [0, 0]
    }
  }

  // 记录操作历史
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

  // 退出编辑模式
  viewMode.value = 'snippet'
  ElMessage.success('已保存编辑内容')
}

// 取消编辑内容
const handleCancelEditContent = () => {
  // 恢复原始内容
  if (selectedFunctionPoint.value) {
    editingContent.value = selectedFunctionPoint.value.matched_content || ''
    const positions = selectedFunctionPoint.value.matched_positions || []
    editStartLine.value = positions[0] || null
    editEndLine.value = positions[1] || null
  }
  // 退出编辑模式
  viewMode.value = 'snippet'
  ElMessage.info('已取消编辑')
}

// ========== 模块片段编辑相关功能 ==========

// 保存模块片段编辑
const handleSaveSnippetEdit = () => {
  if (!selectedFunctionPoint.value) {
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content || ''
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  // 更新匹配内容
  fp.matched_content = snippetContent.value.trim()

  // 记录操作历史
  if (oldMatchedContent !== snippetContent.value.trim()) {
    operationHistory.value.push({
      type: 'EDIT_MATCHED_CONTENT',
      original: {
        name: fp.name,
        matched_content: oldMatchedContent,
        matched_positions: oldMatchedPositions
      },
      adjusted: {
        name: fp.name,
        matched_content: snippetContent.value.trim(),
        matched_positions: fp.matched_positions
      },
      timestamp: Date.now()
    })
  }

  // 更新原始内容
  originalSnippetContent.value = snippetContent.value.trim()
  ElMessage.success('已保存模块片段')
}

// 取消模块片段编辑
const handleCancelSnippetEdit = () => {
  // 恢复原始内容
  snippetContent.value = originalSnippetContent.value
  ElMessage.info('已取消编辑')
}

// ========== 行号选择相关功能 ==========

// 切换行号选择模式
const toggleLineSelectionMode = () => {
  lineSelectionMode.value = !lineSelectionMode.value
  if (!lineSelectionMode.value) {
    // 退出行号选择模式时，清除选择
    selectedLines.value = {}
    updateSelectionPreview()
  }
}

// 处理行号点击（通过事件委托）
const handleLineClick = (event) => {
  // 如果点击的是复选框，不处理（由handleCheckboxChange处理）
  if (event.target.type === 'checkbox') {
    return
  }

  // 如果点击的是按钮或其他交互元素，不处理
  if (event.target.tagName === 'BUTTON' || event.target.closest('button')) {
    return
  }

  if (!lineSelectionMode.value) {
    // 如果不是行号选择模式，不处理（文本选择由handleTextSelection在mouseup时处理）
    return
  }

  const target = event.target
  const lineElement = target.closest('.doc-line')
  if (!lineElement) return

  const lineNumber = parseInt(lineElement.getAttribute('data-line'), 10)
  if (isNaN(lineNumber) || lineNumber <= 0) return

  // 切换选中状态
  if (selectedLines.value[lineNumber]) {
    delete selectedLines.value[lineNumber]
  } else {
    selectedLines.value[lineNumber] = true
  }

  // 更新预览
  updateSelectionPreview()

  // 强制更新视图（通过重新设置viewMode触发重新渲染）
  const currentMode = viewMode.value
  viewMode.value = ''
  nextTick(() => {
    viewMode.value = currentMode
  })
}

// 处理复选框点击（使用事件委托，因为复选框是动态生成的）
const handleCheckboxChange = (event) => {
  const checkbox = event.target
  if (checkbox.type !== 'checkbox' || !checkbox.classList.contains('line-checkbox')) {
    return
  }

  if (!lineSelectionMode.value) {
    // 如果不在行号选择模式，恢复复选框状态
    checkbox.checked = false
    return
  }

  const lineNumber = parseInt(checkbox.getAttribute('data-line'), 10)
  if (isNaN(lineNumber) || lineNumber <= 0) return

  // 更新选中状态
  if (checkbox.checked) {
    selectedLines.value[lineNumber] = true
  } else {
    delete selectedLines.value[lineNumber]
  }

  // 更新预览
  updateSelectionPreview()

  // 强制更新视图
  const currentMode = viewMode.value
  viewMode.value = ''
  nextTick(() => {
    viewMode.value = currentMode
  })
}

// 计算从复选框选中的行数
const selectedLinesCountFromCheckboxes = computed(() => {
  return Object.keys(selectedLines.value).filter(key => selectedLines.value[key]).length
})

// 是否有选中的行
const hasSelectedLines = computed(() => {
  return selectedLinesCountFromCheckboxes.value > 0 || showSelectionPreview.value
})

// 更新选中预览（基于选中的行号）
const updateSelectionPreview = () => {
  const selectedLineNumbers = Object.keys(selectedLines.value)
    .filter(key => selectedLines.value[key])
    .map(Number)
    .sort((a, b) => a - b)

  if (selectedLineNumbers.length === 0) {
    showSelectionPreview.value = false
    selectedContentPreview.value = ''
    selectedLinesCount.value = 0
    return
  }

  // 从文档中提取选中的行
  if (!props.requirementDoc) {
    return
  }

  const docLines = props.requirementDoc.split('\n')
  const extractedLines = selectedLineNumbers.map(lineNum => {
    const index = lineNum - 1
    return index >= 0 && index < docLines.length ? docLines[index] : ''
  }).filter(line => line)

  selectedContentPreview.value = extractedLines.join('\n')
  selectedLinesCount.value = selectedLineNumbers.length

  // 更新选中范围
  if (selectedLineNumbers.length > 0) {
    selectedRange.value = {
      start: selectedLineNumbers[0],
      end: selectedLineNumbers[selectedLineNumbers.length - 1]
    }
  }

  showSelectionPreview.value = true
}

// 应用选中的行到模块片段
const applySelectedLinesToSnippet = () => {
  if (selectedLinesCountFromCheckboxes.value === 0) {
    ElMessage.warning('请先选择行')
    return
  }

  const selectedLineNumbers = Object.keys(selectedLines.value)
    .filter(key => selectedLines.value[key])
    .map(Number)
    .sort((a, b) => a - b)

  if (!props.requirementDoc) {
    ElMessage.warning('需求文档不可用')
    return
  }

  const docLines = props.requirementDoc.split('\n')
  const extractedLines = selectedLineNumbers.map(lineNum => {
    const index = lineNum - 1
    return index >= 0 && index < docLines.length ? docLines[index] : ''
  }).filter(line => line)

  const extractedContent = extractedLines.join('\n')

  if (!selectedFunctionPoint.value) {
    return
  }

  const fp = selectedFunctionPoint.value
  const oldMatchedContent = fp.matched_content || ''
  const oldMatchedPositions = fp.matched_positions ? [...fp.matched_positions] : null

  // 更新匹配内容
  fp.matched_content = extractedContent
  if (selectedLineNumbers.length > 0) {
    fp.matched_positions = [
      selectedLineNumbers[0],
      selectedLineNumbers[selectedLineNumbers.length - 1]
    ]
  }

  // 记录操作历史
  operationHistory.value.push({
    type: 'EDIT_MATCHED_CONTENT',
    original: {
      name: fp.name,
      matched_content: oldMatchedContent,
      matched_positions: oldMatchedPositions
    },
    adjusted: {
      name: fp.name,
      matched_content: extractedContent,
      matched_positions: fp.matched_positions
    },
    timestamp: Date.now()
  })

  // 清除选择
  selectedLines.value = {}
  showSelectionPreview.value = false
  lineSelectionMode.value = false

  // 切换到模块片段模式
  viewMode.value = 'snippet'
  ElMessage.success(`已应用选中的 ${selectedLineNumbers.length} 行到模块片段`)
}

// ========== 行号范围输入相关功能 ==========

// 解析行号范围输入
const parseLineRanges = (input) => {
  if (!input || !input.trim()) {
    return []
  }

  const ranges = input.split(',').map(s => s.trim())
  const lineNumbers = new Set()

  for (const range of ranges) {
    if (range.includes('-')) {
      // 范围：1-3
      const parts = range.split('-').map(n => parseInt(n.trim()))
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        const start = Math.min(parts[0], parts[1])
        const end = Math.max(parts[0], parts[1])
        for (let i = start; i <= end; i++) {
          if (i > 0) {
            lineNumbers.add(i)
          }
        }
      }
    } else {
      // 单个行号：10
      const lineNum = parseInt(range)
      if (!isNaN(lineNum) && lineNum > 0) {
        lineNumbers.add(lineNum)
      }
    }
  }

  return Array.from(lineNumbers).sort((a, b) => a - b)
}

// 应用行号范围输入
const applyLineRangeInput = () => {
  if (!lineRangeInput.value || !lineRangeInput.value.trim()) {
    ElMessage.warning('请输入行号范围')
    return
  }

  const lineNumbers = parseLineRanges(lineRangeInput.value)
  if (lineNumbers.length === 0) {
    ElMessage.warning('无法解析行号范围，请检查格式')
    return
  }

  // 验证行号是否在有效范围内
  if (props.requirementDoc) {
    const docLines = props.requirementDoc.split('\n')
    const maxLine = docLines.length
    const invalidLines = lineNumbers.filter(lineNum => lineNum > maxLine)
    if (invalidLines.length > 0) {
      ElMessage.warning(`行号 ${invalidLines.join(', ')} 超出文档范围（最大 ${maxLine} 行）`)
      return
    }
  }

  // 更新选中的行
  lineNumbers.forEach(lineNum => {
    selectedLines.value[lineNum] = true
  })

  // 更新预览
  updateSelectionPreview()

  // 启用行号选择模式（如果还没有启用）
  if (!lineSelectionMode.value) {
    lineSelectionMode.value = true
  }

  ElMessage.success(`已选中 ${lineNumbers.length} 行`)
}
</script>

<style scoped>
.function-points-confirm {
  padding: 8px 0;
}

.fp-list-header {
  margin-bottom: 12px;
}

.fp-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.fp-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fp-item {
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.fp-item-main {
  border-left: 3px solid var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.fp-item-sub {
  margin-left: 24px;
  border-left: 2px solid var(--el-color-info-light-5);
  background-color: var(--el-bg-color);
}

.fp-icon-main {
  color: var(--el-color-primary);
  margin-right: 6px;
  vertical-align: middle;
}

.fp-icon-sub {
  color: var(--el-color-info);
  margin-right: 6px;
  vertical-align: middle;
}

.fp-indent {
  color: var(--el-text-color-placeholder);
  margin-right: 8px;
  font-family: monospace;
}

.fp-item:hover {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.fp-item.active {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.fp-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.fp-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
  flex: 1;
}

.fp-description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

.fp-actions {
  display: flex;
  gap: 4px;
}

.fp-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.fp-preview {
  color: var(--el-text-color-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color);
}

.viewer-header h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.viewer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.module-description {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.viewer-content {
  flex: 1;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}

.requirement-doc {
  padding: 16px;
  background-color: var(--el-bg-color-page);
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

.viewer-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.edit-actions {
  display: flex;
  gap: 8px;
}

.edit-mode {
  padding: 8px;
}

.edit-toolbar {
  margin-bottom: 12px;
}

.edit-textarea {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.selection-button {
  position: absolute;
  background: white;
  padding: 4px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.requirement-doc {
  position: relative;
}

.doc-line {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

.highlighted-line {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 模块片段模式样式 */
.snippet-mode {
  padding: 12px;
}

.snippet-textarea {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.snippet-actions {
  display: flex;
  gap: 8px;
}

/* 选中预览样式 */
.selection-preview {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color);
  padding: 12px;
  max-height: 200px;
  overflow-y: auto;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.preview-content {
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
  max-height: 120px;
  overflow-y: auto;
}

.preview-content pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.preview-actions {
  display: flex;
  justify-content: flex-end;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from {
  transform: translateY(100%);
  opacity: 0;
}

.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
