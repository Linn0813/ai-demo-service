<template>
  <div class="knowledge-base-container">
    <div class="header">
      <h1>知识库问答</h1>
      <p class="subtitle">基于飞书文档库的智能问答系统</p>
    </div>

    <div class="content">
      <!-- 飞书授权区域（如果需要授权） -->
      <!-- 临时：添加测试按钮，用于调试 -->
      <el-card v-if="needsAuth || showAuthCard" class="auth-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>🔐 飞书授权</span>
          </div>
        </template>
        <div class="auth-info">
          <p class="auth-tip">
            <strong>需要飞书授权才能使用知识库功能</strong>
          </p>
          <p class="auth-desc">
            当前缺少必要的权限，请选择以下方式之一：
          </p>
          <div class="auth-options">
            <div class="auth-option">
              <h4>方式一：使用用户身份权限（推荐）</h4>
              <p>点击下方按钮登录飞书并授权，授权后即可使用</p>
              <el-button
                type="primary"
                :loading="authing"
                @click="handleFeishuAuth"
                size="default"
              >
                {{ authing ? '跳转中...' : '登录飞书并授权' }}
              </el-button>
            </div>
            <div class="auth-divider">或</div>
            <div class="auth-option">
              <h4>方式二：申请应用身份权限</h4>
              <p>访问飞书开放平台申请应用身份权限</p>
              <el-button
                type="default"
                @click="openFeishuAuthPage"
                size="default"
              >
                打开权限申请页面
              </el-button>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 同步文档区域 -->
      <el-card class="sync-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>文档同步</span>
            <div style="display: flex; gap: 10px;">
              <!-- 临时测试按钮 -->
              <el-button
                v-if="!needsAuth && !showAuthCard"
                type="info"
                size="small"
                @click="showAuthCard = true"
                title="测试：显示授权卡片"
              >
                测试授权
              </el-button>
              <el-button
                type="primary"
                :loading="syncing"
                @click="handleSync"
                size="small"
                :disabled="needsAuth"
              >
                {{ syncing ? '同步中...' : '同步所有知识库' }}
              </el-button>
            </div>
          </div>
        </template>
        <div class="sync-info">
          <!-- 同步说明和提醒 -->
          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="sync-alert"
          >
            <template #title>
              <div class="alert-content">
                <div class="alert-title">💡 关于文档同步</div>
                <div class="alert-body">
                  <p><strong>当前模式：</strong>系统支持两种搜索模式，无需同步即可使用</p>
                  <ul class="alert-list">
                    <li><strong>实时搜索模式（默认）</strong>：无需同步，直接使用飞书API搜索，始终获取最新内容</li>
                    <li><strong>向量搜索模式</strong>：需要先同步文档，使用语义搜索，搜索质量更高</li>
                  </ul>
                </div>
              </div>
            </template>
          </el-alert>

          <!-- 同步的优势和注意事项 -->
          <el-collapse v-model="activeSyncInfo" class="sync-collapse">
            <el-collapse-item name="sync-tips" title="📋 同步的优势和注意事项">
              <div class="sync-tips-content">
                <div class="tips-section">
                  <h4>✅ 同步的优势：</h4>
                  <ul>
                    <li><strong>搜索质量更高</strong>：使用语义搜索，可以找到语义相关但关键词不匹配的文档</li>
                    <li><strong>响应速度更快</strong>：本地查询，无需每次调用飞书API</li>
                    <li><strong>减少API调用</strong>：同步后查询不消耗飞书API配额</li>
                  </ul>
                </div>
                <div class="tips-section">
                  <h4>⚠️ 需要注意的问题：</h4>
                  <ul>
                    <li><strong>数据一致性</strong>：飞书文档更新后，本地数据不会自动更新，需要重新同步</li>
                    <li><strong>同步时间</strong>：首次同步可能需要较长时间（取决于文档数量）</li>
                    <li><strong>存储空间</strong>：会占用本地存储空间（通常几十MB，取决于文档数量）</li>
                    <li><strong>维护成本</strong>：如果文档更新频繁，建议定期重新同步</li>
                  </ul>
                </div>
                <div class="tips-section">
                  <h4>💡 建议：</h4>
                  <ul>
                    <li>首次使用建议<strong>先不同步</strong>，直接使用实时搜索模式测试效果</li>
                    <li>如果搜索效果不理想，再考虑同步常用知识库</li>
                    <li>如果文档更新不频繁，同步后可以获得更好的搜索体验</li>
                    <li>如果文档更新频繁，建议使用实时搜索模式，始终获取最新内容</li>
                  </ul>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>

          <!-- 同步结果 -->
          <div v-if="syncResult" class="sync-result">
            <p>
            <span v-if="syncResult.success" class="success-text">
              ✅ {{ syncResult.message }}
            </span>
            <span v-else class="error-text">
              ❌ {{ syncResult.message }}
            </span>
          </p>
          <p v-if="syncResult && syncResult.success">
            已同步 {{ syncResult.document_count || 0 }} 个文档
            <span v-if="syncResult.total_spaces">
              （{{ syncResult.success_count }}/{{ syncResult.total_spaces }} 个知识库）
            </span>
          </p>
            <el-alert
              v-if="syncResult && syncResult.success"
              type="warning"
              :closable="false"
              show-icon
              class="sync-warning"
            >
              <template #title>
                <span>⚠️ 提醒：同步的数据是快照，如果飞书文档有更新，请重新同步以获取最新内容</span>
              </template>
            </el-alert>
          </div>
        </div>
      </el-card>

      <!-- 问答区域 -->
      <el-card class="qa-card" shadow="hover">
        <template #header>
          <div class="card-header">
          <span>智能问答</span>
            <el-tag v-if="searchMode" :type="searchMode === 'realtime' ? 'info' : 'success'" size="small">
              {{ searchMode === 'realtime' ? '实时搜索模式' : '向量搜索模式' }}
            </el-tag>
          </div>
        </template>
        <div class="qa-content">
          <!-- 搜索模式提示 -->
          <el-alert
            v-if="searchMode === 'realtime'"
            type="info"
            :closable="false"
            show-icon
            class="mode-alert"
          >
            <template #title>
              <span>当前使用实时搜索模式：无需同步即可使用，始终获取最新内容。如需更好的语义搜索效果，可以先同步文档。</span>
            </template>
          </el-alert>
          
          <!-- 知识库选择 -->
          <div class="space-selector" style="margin-bottom: 15px;">
            <el-select
              v-model="selectedSpaceId"
              placeholder="选择知识库（不选择则搜索所有知识库）"
              clearable
              style="width: 100%"
              :loading="loadingSpaces"
            >
              <el-option
                v-for="space in wikiSpaces"
                :key="space.space_id"
                :label="space.name"
                :value="space.space_id"
              >
                <span>{{ space.name }}</span>
                <span v-if="space.description" style="color: #8492a6; font-size: 12px; margin-left: 10px;">
                  {{ space.description }}
                </span>
              </el-option>
            </el-select>
          </div>

          <!-- 问题输入 -->
          <div class="question-input">
            <el-input
              v-model="question"
              type="textarea"
              :rows="3"
              placeholder="请输入您的问题..."
              @keydown.ctrl.enter="handleAsk"
              @keydown.meta.enter="handleAsk"
            />
            <div class="input-actions">
              <el-button
                type="primary"
                :loading="asking"
                @click="handleAsk"
                :disabled="!question.trim()"
              >
                {{ asking ? '回答中...' : '提问' }}
              </el-button>
              <el-button @click="clearHistory">清空历史</el-button>
            </div>
          </div>

          <!-- 答案展示 -->
          <div v-if="currentAnswer" class="answer-section">
            <h3>答案</h3>
            <div class="answer-content" v-html="formatAnswer(currentAnswer.answer)"></div>

            <!-- 引用来源 -->
            <div v-if="currentAnswer.sources && currentAnswer.sources.length > 0" class="sources-section">
              <h4>引用来源</h4>
              <ul class="sources-list">
                <li v-for="(source, index) in currentAnswer.sources" :key="index" class="source-item">
                  <a
                    :href="source.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="source-link"
                  >
                    {{ source.title }}
                  </a>
                  <span class="similarity">相似度: {{ (source.similarity * 100).toFixed(1) }}%</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- 历史记录 -->
          <div v-if="history.length > 0" class="history-section">
            <h3>历史记录</h3>
            <div
              v-for="(item, index) in history"
              :key="index"
              class="history-item"
            >
              <div class="history-question">
                <strong>Q:</strong> {{ item.question }}
              </div>
              <div class="history-answer">
                <strong>A:</strong> {{ item.answer }}
              </div>
              <div v-if="item.sources && item.sources.length > 0" class="history-sources">
                <strong>来源:</strong>
                <span
                  v-for="(source, idx) in item.sources"
                  :key="idx"
                  class="source-tag"
                >
                  <a :href="source.url" target="_blank">{{ source.title }}</a>
                </span>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/apis/ai'

const route = useRoute()

const question = ref('')
const asking = ref(false)
const syncing = ref(false)
const authing = ref(false)
const needsAuth = ref(false) // 是否需要授权（根据错误判断）
const showAuthCard = ref(false) // 临时：用于测试显示授权卡片
const currentAnswer = ref(null)
const syncResult = ref(null)
const history = ref([])
const activeSyncInfo = ref([]) // 控制同步说明的展开/折叠
const searchMode = ref(null) // 当前搜索模式：'realtime' 或 'vector'
const wikiSpaces = ref([]) // 知识库空间列表
const selectedSpaceId = ref(null) // 选中的知识库空间ID
const loadingSpaces = ref(false) // 加载知识库列表状态

const handleFeishuAuth = async () => {
  authing.value = true
  try {
    const response = await aiApi.getFeishuOAuthUrl()
    if (response.data && response.data.code === 0) {
      const oauthUrl = response.data.data.oauth_url
      if (oauthUrl) {
        // 跳转到飞书授权页面
        window.location.href = oauthUrl
      } else {
        ElMessage.error('获取授权URL失败')
      }
    } else {
      ElMessage.error(response.data?.message || '获取授权URL失败')
    }
  } catch (error) {
    console.error('获取授权URL失败:', error)
    ElMessage.error('获取授权URL失败: ' + (error.message || '未知错误'))
  } finally {
    authing.value = false
  }
}

const openFeishuAuthPage = () => {
  // 打开飞书权限申请页面
  const authUrl = 'https://open.feishu.cn/app/cli_a9abdadad7785cc5/auth?q=wiki:wiki:readonly&op_from=openapi&token_type=tenant'
  window.open(authUrl, '_blank')
}

const handleSync = async () => {
  syncing.value = true
  needsAuth.value = false // 重置授权状态
  try {
    const response = await aiApi.syncDocuments()
    console.log('同步响应:', response) // 调试日志
    
    if (response.data && response.data.code === 0) {
      const data = response.data.data
      syncResult.value = data
      
      // 检查返回的数据中是否包含权限错误
      if (data.success === false) {
        const errorMsg = data.message || '同步失败'
        const isAuthError = checkIfAuthError(errorMsg)
      if (isAuthError) {
        needsAuth.value = true
        showAuthCard.value = true // 确保显示授权卡片
        ElMessage.warning('需要飞书授权才能同步文档')
        return
      }
      ElMessage.error(errorMsg)
    } else {
      ElMessage.success('文档同步成功')
      needsAuth.value = false
      showAuthCard.value = false // 同步成功，隐藏授权卡片
      // 同步成功后，更新搜索模式
      searchMode.value = 'vector'
    }
    } else {
      const errorMsg = response.data?.message || response.data?.detail || '同步失败'
      const isAuthError = checkIfAuthError(errorMsg)
      if (isAuthError) {
        needsAuth.value = true
        showAuthCard.value = true // 确保显示授权卡片
        ElMessage.warning('需要飞书授权才能同步文档')
      } else {
        ElMessage.error(errorMsg)
      }
      syncResult.value = { success: false, message: errorMsg }
    }
  } catch (error) {
    console.error('同步失败:', error)
    const errorMsg = error.message || '未知错误'
    const errorDetail = error.response?.data?.detail || error.response?.data?.message || error.response?.data?.data?.message || ''
    const fullErrorMsg = errorDetail || errorMsg
    
    // 检查是否是权限错误
    const isAuthError = checkIfAuthError(fullErrorMsg) || error.response?.status === 403
    
    console.log('错误检测:', { errorMsg, errorDetail, fullErrorMsg, isAuthError, status: error.response?.status }) // 调试日志
    
    if (isAuthError) {
      needsAuth.value = true
      showAuthCard.value = true // 确保显示授权卡片
      ElMessage.warning('需要飞书授权才能同步文档')
    } else {
      ElMessage.error('同步失败: ' + fullErrorMsg)
    }
    syncResult.value = { success: false, message: fullErrorMsg }
  } finally {
    syncing.value = false
  }
}

// 检查是否是权限错误的辅助函数
const checkIfAuthError = (msg) => {
  if (!msg) return false
  const msgLower = msg.toLowerCase()
  return (
    msg.includes('权限') ||
    msg.includes('授权') ||
    msg.includes('99991672') ||
    msgLower.includes('access denied') ||
    msgLower.includes('permission') ||
    msgLower.includes('unauthorized') ||
    msgLower.includes('forbidden')
  )
}

const handleAsk = async () => {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  asking.value = true
  const currentQuestion = question.value.trim()

  try {
    // 传递选中的知识库ID（如果选择了）
    const response = await aiApi.askQuestion(currentQuestion, selectedSpaceId.value || null)
    if (response.data && response.data.code === 0) {
      const data = response.data.data
      currentAnswer.value = {
        answer: data.answer,
        sources: data.sources || []
      }

      // 根据答案判断使用的搜索模式
      // 如果答案中提到"未找到相关文档"或"建议先同步文档"，说明使用的是实时搜索模式
      if (data.answer && (
        data.answer.includes('未找到相关文档') || 
        data.answer.includes('建议先同步文档') ||
        data.answer.includes('实时搜索')
      )) {
        searchMode.value = 'realtime'
      } else if (data.sources && data.sources.length > 0 && data.sources[0].similarity > 0) {
        // 如果有相似度分数，说明使用的是向量搜索模式
        searchMode.value = 'vector'
      }

      // 添加到历史记录
      history.value.unshift({
        question: currentQuestion,
        answer: data.answer,
        sources: data.sources || []
      })

      // 清空问题输入
      question.value = ''
    } else {
      ElMessage.error(response.data?.message || '回答失败')
    }
  } catch (error) {
    console.error('提问失败:', error)
    ElMessage.error('提问失败: ' + (error.message || '未知错误'))
  } finally {
    asking.value = false
  }
}

// 加载知识库空间列表
const loadWikiSpaces = async () => {
  loadingSpaces.value = true
  try {
    const response = await aiApi.getWikiSpaces()
    if (response.data && response.data.code === 0) {
      const data = response.data.data
      if (data.success && data.spaces) {
        wikiSpaces.value = data.spaces
        // 不显示成功消息，避免干扰用户
      } else {
        // 只在失败时显示警告
        if (data.message && !checkIfAuthError(data.message)) {
          ElMessage.warning(data.message || '获取知识库列表失败')
        }
      }
    } else {
      const errorMsg = response.data?.message || '获取知识库列表失败'
      if (!checkIfAuthError(errorMsg)) {
        ElMessage.error(errorMsg)
      }
    }
  } catch (error) {
    console.error('加载知识库列表失败:', error)
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '未知错误'
    // 如果是权限错误，不显示错误消息（因为授权卡片会显示）
    if (!checkIfAuthError(errorMsg)) {
      ElMessage.error('加载知识库列表失败: ' + errorMsg)
    }
  } finally {
    loadingSpaces.value = false
  }
}

// 检查向量存储状态
const checkVectorStoreStatus = async () => {
  try {
    const response = await aiApi.getCollectionInfo()
    if (response.data && response.data.code === 0) {
      const info = response.data.data?.info || {}
      const docCount = info.count || 0
      if (docCount > 0) {
        searchMode.value = 'vector'
      } else {
        searchMode.value = 'realtime'
      }
    }
  } catch (error) {
    // 如果检查失败，默认使用实时搜索模式
    searchMode.value = 'realtime'
  }
}

const clearHistory = () => {
  history.value = []
  currentAnswer.value = null
  ElMessage.success('历史记录已清空')
}

const formatAnswer = (text) => {
  // 简单的Markdown格式化（可以后续增强）
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
}

// 检查是否是OAuth回调
onMounted(() => {
  // 检查URL参数中是否有auth_success（OAuth回调成功）
  const authSuccess = route.query.auth_success
  if (authSuccess === 'true') {
    // OAuth回调成功，显示成功消息
    ElMessage.success('授权成功！现在可以使用知识库功能了')
    needsAuth.value = false // 授权成功，不需要授权
    showAuthCard.value = false // 隐藏授权卡片
    // 清除URL中的auth_success参数
    window.history.replaceState({}, '', window.location.pathname)
  }
  
  // 检查URL参数中是否有code（直接OAuth回调，虽然通常不会发生，但保留兼容性）
  const code = route.query.code
  if (code) {
    // OAuth回调，显示成功消息
    ElMessage.success('授权成功！现在可以使用知识库功能了')
    needsAuth.value = false // 授权成功，不需要授权
    showAuthCard.value = false // 隐藏授权卡片
    // 清除URL中的code参数
    window.history.replaceState({}, '', window.location.pathname)
  }
  
  // 检查向量存储状态，确定搜索模式
  checkVectorStoreStatus()
  
  // 加载知识库空间列表
  loadWikiSpaces()
})
</script>

<style scoped>
.knowledge-base-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  font-size: 28px;
  margin-bottom: 10px;
}

.subtitle {
  color: #666;
  font-size: 14px;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.auth-card,
.sync-card,
.qa-card {
  margin-bottom: 20px;
}

.auth-info {
  padding: 20px;
}

.auth-tip {
  text-align: center;
  color: #f56c6c;
  font-size: 16px;
  margin-bottom: 15px;
}

.auth-desc {
  text-align: center;
  color: #666;
  font-size: 14px;
  margin-bottom: 20px;
}

.auth-options {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 600px;
  margin: 0 auto;
}

.auth-option {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.auth-option h4 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #333;
  font-size: 16px;
}

.auth-option p {
  margin-bottom: 15px;
  color: #666;
  font-size: 14px;
}

.auth-divider {
  text-align: center;
  color: #999;
  font-size: 14px;
  position: relative;
}

.auth-divider::before,
.auth-divider::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 40%;
  height: 1px;
  background: #e4e7ed;
}

.auth-divider::before {
  left: 0;
}

.auth-divider::after {
  right: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sync-info {
  font-size: 14px;
}

.sync-alert {
  margin-bottom: 15px;
}

.alert-content {
  padding: 5px 0;
}

.alert-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #303133;
}

.alert-body {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.alert-body p {
  margin: 8px 0;
}

.alert-list {
  margin: 10px 0 0 20px;
  padding: 0;
}

.alert-list li {
  margin: 8px 0;
  line-height: 1.6;
}

.sync-collapse {
  margin: 15px 0;
}

.sync-tips-content {
  padding: 10px 0;
}

.tips-section {
  margin-bottom: 20px;
}

.tips-section:last-child {
  margin-bottom: 0;
}

.tips-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #303133;
}

.tips-section ul {
  margin: 8px 0 0 20px;
  padding: 0;
  color: #606266;
  line-height: 1.8;
}

.tips-section li {
  margin: 6px 0;
}

.sync-result {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #e4e7ed;
}

.sync-warning {
  margin-top: 10px;
}

.mode-alert {
  margin-bottom: 15px;
}

.success-text {
  color: #67c23a;
}

.error-text {
  color: #f56c6c;
}

.qa-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.question-input {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.answer-section {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}

.answer-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 18px;
}

.answer-content {
  line-height: 1.8;
  color: #333;
  margin-bottom: 20px;
}

.sources-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
}

.sources-section h4 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 16px;
}

.sources-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.source-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #e4e7ed;
}

.source-link {
  color: #409eff;
  text-decoration: none;
}

.source-link:hover {
  text-decoration: underline;
}

.similarity {
  color: #909399;
  font-size: 12px;
}

.history-section {
  margin-top: 30px;
}

.history-section h3 {
  margin-bottom: 15px;
  font-size: 18px;
}

.history-item {
  padding: 15px;
  background: #f9f9f9;
  border-radius: 4px;
  margin-bottom: 15px;
}

.history-question {
  margin-bottom: 10px;
  color: #409eff;
}

.history-answer {
  margin-bottom: 10px;
  color: #333;
}

.history-sources {
  font-size: 12px;
  color: #666;
}

.source-tag {
  margin-left: 8px;
}

.source-tag a {
  color: #409eff;
  text-decoration: none;
}

.source-tag a:hover {
  text-decoration: underline;
}
</style>

