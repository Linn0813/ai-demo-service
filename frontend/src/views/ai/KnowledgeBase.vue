<template>
  <div class="knowledge-base-container">
    <div class="header">
      <h1>知识库问答</h1>
      <p class="subtitle">基于飞书文档库的智能问答系统</p>
    </div>

    <div class="content">
      <!-- 飞书授权区域（如果需要授权） -->
      <el-card v-if="needsAuth" class="auth-card" shadow="hover">
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
              <h4>方式一：扫码登录（推荐）</h4>
              <p>使用飞书APP扫码登录，谁扫码就用谁的权限</p>
              <div v-if="oauthUrl" class="qr-code-container">
                <div class="qr-code-wrapper">
                  <img :src="qrCodeUrl" alt="飞书授权二维码" class="qr-code" />
                  <p class="qr-tip">使用飞书APP扫描二维码</p>
                </div>
                <el-button
                  type="text"
                  @click="refreshQRCode"
                  :loading="authing"
                  size="small"
                >
                  {{ authing ? '刷新中...' : '刷新二维码' }}
                </el-button>
              </div>
              <el-button
                v-else
                type="primary"
                :loading="authing"
                @click="initQRCode"
                size="default"
              >
                {{ authing ? '生成中...' : '生成二维码' }}
              </el-button>
            </div>
            <div class="auth-divider">或</div>
            <div class="auth-option">
              <h4>方式二：浏览器登录</h4>
              <p>在浏览器中打开飞书授权页面</p>
              <el-button
                type="default"
                :loading="authing"
                @click="handleFeishuAuth"
                size="default"
              >
                {{ authing ? '跳转中...' : '在浏览器中授权' }}
              </el-button>
            </div>
            <div class="auth-divider">或</div>
            <div class="auth-option">
              <h4>方式三：申请应用身份权限</h4>
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
            <!-- 网络搜索选项 -->
            <div class="web-search-option">
              <el-checkbox v-model="useWebSearch">
                <span>🌐 启用网络搜索</span>
                <el-tooltip content="当知识库结果不理想时，自动使用网络搜索补充信息" placement="top">
                  <span style="margin-left: 5px; color: #909399; cursor: help;">❓</span>
                </el-tooltip>
              </el-checkbox>
            </div>
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
            <h3>{{ currentAnswer.question_type === 'document_list' ? '相关文档列表' : '答案' }}</h3>
            <div class="answer-content" v-html="formatAnswer(currentAnswer.answer)"></div>
            
            <!-- 文档列表模式提示 -->
            <div v-if="currentAnswer.question_type === 'document_list' && currentAnswer.sources && currentAnswer.sources.length > 0" class="document-list-tip">
              <el-alert
                type="info"
                :closable="false"
                show-icon
              >
                <template #title>
                  <span>找到 {{ currentAnswer.sources.length }} 个相关文档，点击文档标题可查看完整内容</span>
                </template>
              </el-alert>
            </div>

            <!-- 网络搜索建议按钮 -->
            <div v-if="currentAnswer.suggest_web_search && !currentAnswer.has_web_search" class="web-search-suggestion">
              <el-alert
                type="warning"
                :closable="false"
                show-icon
              >
                <template #title>
                  <div class="suggestion-content">
                    <p>💡 知识库文档相似度较低（{{ (currentAnswer.max_similarity * 100).toFixed(1) }}%），建议使用网络搜索获取更多信息</p>
                    <el-button
                      type="primary"
                      size="small"
                      :loading="asking"
                      @click="searchWithWeb"
                      style="margin-top: 10px;"
                    >
                      🌐 使用网络搜索
                    </el-button>
                  </div>
                </template>
              </el-alert>
            </div>

            <!-- 已使用网络搜索提示 -->
            <div v-if="currentAnswer.has_web_search" class="web-search-used">
              <el-tag type="success" size="small">
                ✓ 已使用网络搜索补充信息
              </el-tag>
            </div>

            <!-- 引用来源 / 文档列表 -->
            <div v-if="currentAnswer.sources && currentAnswer.sources.length > 0" class="sources-section">
              <h4>{{ currentAnswer.question_type === 'document_list' ? '文档列表' : '引用来源' }}</h4>
              <ul class="sources-list" :class="{ 'document-list-mode': currentAnswer.question_type === 'document_list' }">
                <li v-for="(source, index) in currentAnswer.sources" :key="index" class="source-item">
                  <a
                    :href="source.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="source-link"
                  >
                    {{ index + 1 }}. {{ source.title }}
                  </a>
                  <span v-if="source.similarity > 0" class="similarity">
                    {{ currentAnswer.question_type === 'document_list' ? '相关性' : '相似度' }}: {{ (source.similarity * 100).toFixed(1) }}%
                  </span>
                  <span v-else-if="source.source === 'web_search'" class="web-source">🌐 网络搜索</span>
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/apis/ai'

const route = useRoute()

const question = ref('')
const asking = ref(false)
const syncing = ref(false)
const authing = ref(false)
const needsAuth = ref(false) // 是否需要授权（根据错误判断）
const currentAnswer = ref(null)
const syncResult = ref(null)
const history = ref([])
const activeSyncInfo = ref([]) // 控制同步说明的展开/折叠
const searchMode = ref(null) // 当前搜索模式：'realtime' 或 'vector'
const wikiSpaces = ref([]) // 知识库空间列表
const selectedSpaceId = ref(null) // 选中的知识库空间ID
const loadingSpaces = ref(false) // 加载知识库列表状态
const useWebSearch = ref(false) // 是否启用网络搜索
const lastQuestion = ref('') // 保存上次的问题，用于网络搜索
const oauthUrl = ref('') // OAuth授权URL
const qrCodeUrl = ref('') // 二维码图片URL
const checkAuthTimer = ref(null) // 检查授权状态的定时器

// 初始化二维码
const initQRCode = async () => {
  authing.value = true
  try {
    const response = await aiApi.getFeishuOAuthUrl()
    if (response.data && response.data.code === 0) {
      const url = response.data.data.oauth_url
      if (url) {
        oauthUrl.value = url
        // 生成二维码（使用在线API）
        qrCodeUrl.value = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(url)}`
        // 开始轮询检查授权状态
        startAuthCheck()
        ElMessage.success('二维码已生成，请使用飞书APP扫描')
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

// 刷新二维码
const refreshQRCode = async () => {
  oauthUrl.value = ''
  qrCodeUrl.value = ''
  stopAuthCheck()
  await initQRCode()
}

// 开始检查授权状态
const startAuthCheck = () => {
  // 每3秒检查一次授权状态
  checkAuthTimer.value = setInterval(async () => {
    try {
      // 尝试加载知识库列表，如果成功说明已授权
      const response = await aiApi.getWikiSpaces()
      if (response.data && response.data.code === 0) {
        const data = response.data.data
        if (data.success && data.spaces && data.spaces.length > 0) {
          // 授权成功，有知识库数据
          stopAuthCheck()
          needsAuth.value = false
          oauthUrl.value = ''
          qrCodeUrl.value = ''
          ElMessage.success('授权成功！')
          // 重新加载知识库列表
          await loadWikiSpaces()
        } else if (data.success && (!data.spaces || data.spaces.length === 0)) {
          // 授权成功但列表为空，可能是没有知识库或权限不足
          // 继续检查，但不清除授权状态
          console.debug('授权成功但知识库列表为空，继续检查...')
        }
      } else {
        // 检查是否是权限错误
        const errorMsg = response.data?.message || response.data?.detail || '获取知识库列表失败'
        const isAuthError = checkIfAuthError(errorMsg)
        if (!isAuthError) {
          // 不是权限错误，可能是其他错误，停止检查
          stopAuthCheck()
        }
      }
    } catch (error) {
      // 检查是否是权限错误
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '未知错误'
      const isAuthError = checkIfAuthError(errorMsg) || error.response?.status === 403 || error.response?.status === 401
      if (!isAuthError) {
        // 不是权限错误，停止检查
        stopAuthCheck()
      } else {
        // 继续等待授权
        console.debug('等待授权中...')
      }
    }
  }, 3000)
}

// 停止检查授权状态
const stopAuthCheck = () => {
  if (checkAuthTimer.value) {
    clearInterval(checkAuthTimer.value)
    checkAuthTimer.value = null
  }
}

const handleFeishuAuth = async () => {
  authing.value = true
  try {
    const response = await aiApi.getFeishuOAuthUrl()
    if (response.data && response.data.code === 0) {
      const url = response.data.data.oauth_url
      if (url) {
        // 跳转到飞书授权页面
        window.location.href = url
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
        ElMessage.warning('需要飞书授权才能同步文档')
        return
      }
      ElMessage.error(errorMsg)
    } else {
      ElMessage.success('文档同步成功')
      needsAuth.value = false // 同步成功，清除授权状态
      // 同步成功后，更新搜索模式
      searchMode.value = 'vector'
    }
    } else {
      const errorMsg = response.data?.message || response.data?.detail || '同步失败'
      const isAuthError = checkIfAuthError(errorMsg)
      if (isAuthError) {
        needsAuth.value = true
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
  const msgStr = String(msg)
  return (
    msgStr.includes('权限') ||
    msgStr.includes('授权') ||
    msgStr.includes('99991672') ||
    msgStr.includes('99991663') ||
    msgStr.includes('99991664') ||
    msgStr.includes('99991679') ||
    msgLower.includes('access denied') ||
    msgLower.includes('permission') ||
    msgLower.includes('unauthorized') ||
    msgLower.includes('forbidden') ||
    msgLower.includes('token') && (msgLower.includes('invalid') || msgLower.includes('expired') || msgLower.includes('missing'))
  )
}

const handleAsk = async () => {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  asking.value = true
  const currentQuestion = question.value.trim()
  lastQuestion.value = currentQuestion // 保存问题，用于网络搜索

  try {
    // 传递选中的知识库ID和网络搜索选项
    const response = await aiApi.askQuestion(
      currentQuestion, 
      selectedSpaceId.value || null,
      useWebSearch.value
    )
    if (response.data && response.data.code === 0) {
      const data = response.data.data
      currentAnswer.value = {
        answer: data.answer,
        sources: data.sources || [],
        suggest_web_search: data.suggest_web_search || false,
        has_web_search: data.has_web_search || false,
        max_similarity: data.max_similarity || 0,
        question_type: data.question_type || 'content_qa' // 记录问题类型
      }
      
      // 如果是文档列表查询，显示特殊提示
      if (data.question_type === 'document_list') {
        console.log('文档列表查询模式，找到', data.sources?.length || 0, '个文档')
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
        sources: data.sources || [],
        has_web_search: data.has_web_search || false
      })

      // 清空问题输入
      question.value = ''
    } else {
      ElMessage.error(response.data?.message || '回答失败')
    }
  } catch (error) {
    console.error('提问失败:', error)
    const errorMsg = error.message || '未知错误'
    const errorDetail = error.response?.data?.detail || error.response?.data?.message || error.response?.data?.data?.message || ''
    const fullErrorMsg = errorDetail || errorMsg
    
    // 检查是否是权限错误
    const isAuthError = checkIfAuthError(fullErrorMsg) || error.response?.status === 403
    
    if (isAuthError) {
      needsAuth.value = true // 自动显示授权卡片
      ElMessage.warning('需要飞书授权才能使用知识库功能')
    } else {
      ElMessage.error('提问失败: ' + fullErrorMsg)
    }
  } finally {
    asking.value = false
  }
}

// 使用网络搜索
const searchWithWeb = async () => {
  if (!lastQuestion.value.trim()) {
    ElMessage.warning('没有可搜索的问题')
    return
  }

  asking.value = true
  try {
    // 使用相同的问题，但启用网络搜索
    const response = await aiApi.askQuestion(
      lastQuestion.value,
      selectedSpaceId.value || null,
      true // 启用网络搜索
    )
    if (response.data && response.data.code === 0) {
      const data = response.data.data
      currentAnswer.value = {
        answer: data.answer,
        sources: data.sources || [],
        suggest_web_search: false, // 已经使用了，不再建议
        has_web_search: data.has_web_search || false,
        max_similarity: data.max_similarity || 0
      }

      // 更新历史记录中的最后一条
      if (history.value.length > 0 && history.value[0].question === lastQuestion.value) {
        history.value[0] = {
          question: lastQuestion.value,
          answer: data.answer,
          sources: data.sources || [],
          has_web_search: true
        }
      }

      ElMessage.success('已使用网络搜索补充信息')
    } else {
      ElMessage.error(response.data?.message || '网络搜索失败')
    }
  } catch (error) {
    console.error('网络搜索失败:', error)
    ElMessage.error('网络搜索失败: ' + (error.message || '未知错误'))
  } finally {
    asking.value = false
  }
}

// 加载知识库空间列表（带重试机制）
const loadWikiSpaces = async (retryCount = 0) => {
  loadingSpaces.value = true
  try {
    const response = await aiApi.getWikiSpaces()
    if (response.data && response.data.code === 0) {
      const data = response.data.data
      if (data.success && data.spaces) {
        wikiSpaces.value = data.spaces
        needsAuth.value = false // 加载成功，清除授权状态
        // 不显示成功消息，避免干扰用户
      } else {
        // 检查是否是权限错误
        const errorMsg = data.message || '获取知识库列表失败'
        const isAuthError = checkIfAuthError(errorMsg)
        console.log('检查权限错误:', { errorMsg, isAuthError }) // 调试日志
        if (isAuthError) {
          needsAuth.value = true // 自动显示授权卡片
          console.log('检测到权限错误，设置 needsAuth = true') // 调试日志
        } else {
          ElMessage.warning(errorMsg)
        }
      }
    } else {
      const errorMsg = response.data?.message || response.data?.detail || '获取知识库列表失败'
      const isAuthError = checkIfAuthError(errorMsg)
      console.log('检查权限错误:', { errorMsg, isAuthError }) // 调试日志
      if (isAuthError) {
        needsAuth.value = true // 自动显示授权卡片
        console.log('检测到权限错误，设置 needsAuth = true') // 调试日志
      } else {
        ElMessage.error(errorMsg)
      }
    }
  } catch (error) {
    console.error('加载知识库列表失败:', error)
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '未知错误'
    const statusCode = error.response?.status
    const isAuthError = checkIfAuthError(errorMsg) || statusCode === 403 || statusCode === 401
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout')
    
    console.log('错误检测:', { errorMsg, statusCode, isAuthError, isTimeout }) // 调试日志
    
    // 如果是超时错误，提示用户后端仍在处理
    if (isTimeout) {
      ElMessage.warning('请求超时，后端可能仍在处理中。请稍后刷新页面或重试')
      // 超时后不立即重试，让用户手动刷新
      loadingSpaces.value = false
      return
    }
    
    // 如果是连接错误且重试次数少于3次，则重试
    if (!isAuthError && (error.code === 'ECONNRESET' || error.message?.includes('ECONNRESET')) && retryCount < 3) {
      console.log(`连接重置，${1000 * (retryCount + 1)}ms后重试...`)
      setTimeout(() => {
        loadWikiSpaces(retryCount + 1)
      }, 1000 * (retryCount + 1))
      return
    }
    
    if (isAuthError) {
      needsAuth.value = true // 自动显示授权卡片
      console.log('检测到权限错误，设置 needsAuth = true') // 调试日志
    } else {
      ElMessage.error('加载知识库列表失败: ' + errorMsg)
    }
  } finally {
    loadingSpaces.value = false
  }
}

// 检查向量存储状态（带重试机制）
const checkVectorStoreStatus = async (retryCount = 0) => {
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
    // 如果是连接错误且重试次数少于3次，则重试
    if ((error.code === 'ECONNRESET' || error.message?.includes('ECONNRESET')) && retryCount < 3) {
      console.log(`连接重置，${1000 * (retryCount + 1)}ms后重试...`)
      setTimeout(() => {
        checkVectorStoreStatus(retryCount + 1)
      }, 1000 * (retryCount + 1))
      return
    }
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
onMounted(async () => {
  // 检查URL参数中是否有auth_success（OAuth回调成功）
  const authSuccess = route.query.auth_success
  if (authSuccess === 'true') {
    // OAuth回调成功，先停止授权检查定时器
    stopAuthCheck()
    // 显示成功消息
    ElMessage.success('授权成功！正在加载知识库...')
    needsAuth.value = false // 授权成功，清除授权状态
    oauthUrl.value = ''
    qrCodeUrl.value = ''
    // 清除URL中的auth_success参数
    window.history.replaceState({}, '', window.location.pathname)
    // 等待一小段时间，确保token已保存
    await new Promise(resolve => setTimeout(resolve, 500))
    // 重新加载知识库列表（带重试）
    let retryCount = 0
    const maxRetries = 3
    while (retryCount < maxRetries) {
      try {
        await loadWikiSpaces()
        // 如果加载成功，检查是否真的成功
        if (!needsAuth.value) {
          if (wikiSpaces.value.length > 0) {
            ElMessage.success('知识库加载成功！')
          } else {
            ElMessage.success('授权成功！知识库列表为空，可能是没有可访问的知识库')
          }
          break
        } else {
          // 如果仍然需要授权，可能是token还没生效，重试
          retryCount++
          if (retryCount < maxRetries) {
            console.log(`授权后加载失败，${1000 * retryCount}ms后重试... (${retryCount}/${maxRetries})`)
            await new Promise(resolve => setTimeout(resolve, 1000 * retryCount))
          } else {
            ElMessage.warning('授权成功，但加载知识库失败，请刷新页面重试')
            needsAuth.value = true
          }
        }
      } catch (error) {
        retryCount++
        console.error(`加载知识库失败 (${retryCount}/${maxRetries}):`, error)
        const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '未知错误'
        const isAuthError = checkIfAuthError(errorMsg) || error.response?.status === 403 || error.response?.status === 401
        if (isAuthError && retryCount < maxRetries) {
          // 权限错误，可能是token还没生效，重试
          await new Promise(resolve => setTimeout(resolve, 1000 * retryCount))
        } else if (retryCount >= maxRetries) {
          if (isAuthError) {
            ElMessage.warning('授权成功，但加载知识库时仍提示权限不足，请刷新页面重试')
            needsAuth.value = true
          } else {
            ElMessage.error('加载知识库失败，请刷新页面重试')
          }
        }
      }
    }
    return
  }
  
  // 检查URL参数中是否有code（直接OAuth回调，虽然通常不会发生，但保留兼容性）
  const code = route.query.code
  if (code) {
    // OAuth回调，显示成功消息
    ElMessage.success('授权成功！正在加载知识库...')
    needsAuth.value = false // 授权成功，清除授权状态
    // 清除URL中的code参数
    window.history.replaceState({}, '', window.location.pathname)
    // 等待一小段时间，确保token已保存
    await new Promise(resolve => setTimeout(resolve, 500))
    // 重新加载知识库列表
    await loadWikiSpaces()
    return
  }
  
  // 检查向量存储状态，确定搜索模式
  checkVectorStoreStatus()
  
  // 加载知识库空间列表（会自动检测授权状态）
  await loadWikiSpaces()
  
  // 等待加载完成后，如果需要授权，自动生成二维码
  if (needsAuth.value) {
    await initQRCode()
  }
})

// 组件卸载时清理定时器
onBeforeUnmount(() => {
  stopAuthCheck()
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

.qr-code-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
  margin-top: 15px;
}

.qr-code-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.qr-code {
  width: 200px;
  height: 200px;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  background: white;
  padding: 10px;
}

.qr-tip {
  margin: 0;
  color: #666;
  font-size: 13px;
  text-align: center;
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

.web-search-option {
  display: flex;
  align-items: center;
  padding: 8px 0;
}

.web-search-suggestion {
  margin-top: 20px;
}

.suggestion-content {
  display: flex;
  flex-direction: column;
}

.suggestion-content p {
  margin: 0;
  font-size: 14px;
}

.web-search-used {
  margin-top: 15px;
  margin-bottom: 10px;
}

.web-source {
  color: #67c23a;
  font-size: 12px;
  font-weight: 500;
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

.document-list-mode .source-item {
  padding: 12px 0;
}

.document-list-mode .source-link {
  font-size: 15px;
  font-weight: 500;
}

.document-list-tip {
  margin-top: 15px;
  margin-bottom: 10px;
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

