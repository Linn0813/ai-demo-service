import axios from 'axios'

// API 基础 URL 配置（支持前后端分离部署）
// 开发环境：
//   - 如果设置了 VITE_API_BASE_URL，使用该值
//   - 否则使用空字符串，通过 Vite 代理（/api -> http://localhost:8113）转发到后端
// 生产环境：
//   - 必须设置 VITE_API_BASE_URL 为后端服务的完整 URL，例如：http://api.yourdomain.com
//   - 或者如果前后端部署在同一域名下，可以使用相对路径
const baseUrl = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? '' : 'http://localhost:8113')

// 创建专用实例
const aiRequest = axios.create({
  baseURL: baseUrl,
  timeout: 60000, // 60秒超时，知识库操作可能需要较长时间
})

// 请求拦截器（独立服务不需要token认证，但保留结构以便后续扩展）
aiRequest.interceptors.request.use(config => {
  // 如果需要添加API密钥或其他认证，可以在这里添加
  return config
})

// 响应拦截器
aiRequest.interceptors.response.use(
  response => response,
  error => {
    console.error('AI API Error:', error.response?.status, error.response?.data)
    // 如果是超时错误，提供更友好的提示
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.message = '请求超时，后端仍在处理中，请稍后刷新页面查看结果'
    }
    return Promise.reject(error)
  }
)

// FastAPI返回格式适配器：将FastAPI直接返回的数据包装成Flask格式，保持前端代码兼容
const adaptResponse = (response) => {
  // FastAPI直接返回数据，包装成 { code: 0, data: ... } 格式
  return {
    data: {
      code: 0,
      data: response.data,
      message: 'success'
    }
  }
}

export const aiApi = {
  // 获取可用模型列表
  async getAvailableModels() {
    const response = await aiRequest.get('/api/v1/models')
    return adaptResponse(response)
  },

  // 生成测试用例 - 同步接口（可能超时）
  async generateTestCases(data) {
    const response = await aiRequest.post('/api/v1/test-cases/generate', data)
    return adaptResponse(response)
  },

  // 异步生成测试用例（提交任务）
  async createGenerationTask(data) {
    const response = await aiRequest.post('/api/v1/test-cases/generate-async', data)
    return adaptResponse(response)
  },

  // 提取功能模块并匹配原文（用于用户确认）- 同步接口（可能超时）
  async extractFunctionModules(data) {
    const response = await aiRequest.post('/api/v1/function-modules/extract', data)
    return adaptResponse(response)
  },

  // 异步提取功能模块（提交任务）
  async extractFunctionModulesAsync(data) {
    const response = await aiRequest.post('/api/v1/function-modules/extract-async', data)
    return adaptResponse(response)
  },

  // 查询任务状态
  async getTaskStatus(taskId) {
    const response = await aiRequest.get(`/api/v1/tasks/${taskId}`)
    return adaptResponse(response)
  },

  // 确认功能点并生成测试用例（与generateTestCases相同）
  async confirmAndGenerate(data) {
    const response = await aiRequest.post('/api/v1/test-cases/generate', data)
    return adaptResponse(response)
  },

  // 重新匹配单个模块的原文内容
  async rematchModuleContent(data) {
    const response = await aiRequest.post('/api/v1/modules/rematch', data)
    return adaptResponse(response)
  },

  // 获取飞书OAuth授权URL
  async getFeishuOAuthUrl() {
    const response = await aiRequest.get('/api/v1/feishu/oauth/authorize')
    return adaptResponse(response)
  },

  // 上传Word文档并解析
  async uploadWordDocument(file) {
    // 使用 FormData 上传文件
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const response = await aiRequest.post('/api/v1/upload/word', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      return adaptResponse(response)
    } catch (error) {
      // 如果接口不存在，返回友好的错误提示
      if (error.response?.status === 404) {
        return {
          data: {
            code: -1,
            message: 'Word文档上传功能暂未实现，请直接粘贴文档内容',
            data: null
          }
        }
      }
      throw error
    }
  },

  // 知识库相关API
  // 同步知识库文档
  async syncDocuments(spaceId = null) {
    const response = await aiRequest.post('/api/v1/knowledge-base/sync', {
      space_id: spaceId
    })
    return adaptResponse(response)
  },

  // 问答接口
  async askQuestion(question, spaceId = null, useWebSearch = false) {
    const response = await aiRequest.post('/api/v1/knowledge-base/ask', {
      question,
      space_id: spaceId,
      use_web_search: useWebSearch
    })
    return adaptResponse(response)
  },

  // 获取集合信息
  async getCollectionInfo() {
    const response = await aiRequest.get('/api/v1/knowledge-base/info')
    return adaptResponse(response)
  },

  // 获取知识库空间列表
  async getWikiSpaces() {
    const response = await aiRequest.get('/api/v1/knowledge-base/spaces')
    return adaptResponse(response)
  }
}
