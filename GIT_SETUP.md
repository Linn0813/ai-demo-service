# Git 仓库设置指南

## 推荐方案：GitHub（主）+ Gitee（镜像）

### 为什么选择 GitHub？

1. ✅ **SEO 友好**：GitHub 内容更容易被 Google、Bing 等搜索引擎索引
2. ✅ **国际化**：全球访问速度快，适合面向国际用户
3. ✅ **GitHub Pages**：可以直接部署前端，免费且稳定
4. ✅ **社区活跃**：便于分享、协作和获得 Star
5. ✅ **与博客集成**：如果博客在 GitHub，项目也在 GitHub 更方便管理

### Gitee 作为镜像

- 方便国内用户访问和克隆
- 可以作为备份
- 可以使用 GitHub Actions 自动同步

## 上传步骤

### 1. 准备 Git 仓库

#### 1.1 检查文件

确保以下文件已准备好：
- ✅ `.gitignore` - 已配置，忽略敏感文件
- ✅ `README.md` - 项目说明文档
- ✅ `LICENSE` - 许可证（可选，建议添加）

#### 1.2 创建 GitHub 仓库

1. 登录 GitHub
2. 点击右上角 "+" → "New repository"
3. 填写信息：
   - Repository name: `ai-demo-service`
   - Description: `AI驱动的测试用例生成工具，支持需求文档分析和测试用例自动生成`
   - 选择 Public（公开，便于SEO）
   - 不要初始化 README（已有）
4. 点击 "Create repository"

### 2. 初始化并上传代码

```bash
# 在项目根目录执行

# 初始化 Git（如果还没有）
git init

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit: AI Demo Service

- 前后端分离架构
- 测试用例生成功能
- 知识库问答功能（规划中）
- 支持多种LLM模型"

# 添加远程仓库
git remote add origin https://github.com/yourusername/ai-demo-service.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 3. 设置 Gitee 镜像（可选）

#### 方式一：手动同步

1. 在 Gitee 创建同名仓库
2. 添加 Gitee 远程：
```bash
git remote add gitee https://gitee.com/yourusername/ai-demo-service.git
git push gitee main
```

#### 方式二：自动同步（推荐）

使用 GitHub Actions 自动同步到 Gitee：

1. 在 Gitee 创建同名仓库
2. 在 GitHub 仓库设置中添加 Secret：
   - Name: `GITEE_SSH_PRIVATE_KEY`
   - Value: 你的 Gitee SSH 私钥
3. GitHub Actions 会自动同步（已配置 `.github/workflows/sync-to-gitee.yml`）

## 部署到博客

### 方式一：在博客中添加入口链接（推荐）

在 Hexo 博客中添加一个页面：

```bash
# 在博客目录
hexo new page ai-demo
```

编辑 `source/ai-demo/index.md`：

```markdown
---
title: AI 测试用例生成工具
date: 2024-01-01
layout: page
---

## AI 测试用例生成工具

这是一个基于 AI 的智能测试用例生成工具，支持：

- 📝 需求文档分析
- 🎯 功能模块自动提取
- ✅ 测试用例自动生成
- 🔍 知识库问答（规划中）

### 功能特点

- 使用先进的 LLM 技术
- 支持多种模型（Qwen、DeepSeek等）
- 前后端分离架构
- 支持自定义配置

### 在线体验

[访问工具 →](https://your-frontend-domain.com)

### 项目地址

- GitHub: [https://github.com/yourusername/ai-demo-service](https://github.com/yourusername/ai-demo-service)
- 在线演示: [https://your-frontend-domain.com](https://your-frontend-domain.com)
```

### 方式二：嵌入到博客文章

在博客文章中嵌入：

```markdown
## AI 测试用例生成工具

这是一个基于 AI 的测试用例生成工具...

<iframe 
  src="https://your-frontend-domain.com" 
  width="100%" 
  height="800px"
  frameborder="0"
  style="border: 1px solid #ddd; border-radius: 8px;">
</iframe>

[访问完整页面](https://your-frontend-domain.com)
```

### 方式三：部署到博客子目录

如果使用 GitHub Pages，可以部署到：
- `yourusername.github.io/ai-demo/`

## SEO 优化

### 1. GitHub 仓库 SEO

- ✅ 添加详细的 README.md
- ✅ 添加 LICENSE 文件
- ✅ 使用有意义的仓库描述
- ✅ 添加 Topics（标签）：`ai`, `test-case-generation`, `fastapi`, `vue3`, `llm`

### 2. 博客文章 SEO

在博客中写文章介绍项目：

```markdown
---
title: 使用AI自动生成测试用例 - 我的开源项目
date: 2024-01-01
tags: [AI, 测试, 开源项目]
categories: [项目]
---

## 项目背景

介绍项目背景、解决的问题...

## 技术栈

- 后端：FastAPI + Python
- 前端：Vue3 + Vite
- AI：LLM（支持多种模型）

## 功能演示

[在线演示链接](https://your-frontend-domain.com)

## 项目地址

GitHub: [链接]
```

### 3. 搜索引擎提交

#### Google Search Console

1. 访问 [Google Search Console](https://search.google.com/search-console)
2. 添加属性（你的博客域名）
3. 提交 sitemap.xml

#### 百度站长平台

1. 访问 [百度站长平台](https://ziyuan.baidu.com/)
2. 添加网站
3. 提交 sitemap.xml

## 部署平台推荐

### 前端部署

1. **Vercel**（推荐）
   - 免费、快速、自动 HTTPS
   - 与 GitHub 集成方便
   - 全球 CDN

2. **Netlify**
   - 类似 Vercel
   - 免费额度充足

3. **GitHub Pages**
   - 免费
   - 与 GitHub 集成
   - 适合静态页面

### 后端部署

1. **Railway**（推荐）
   - 免费额度充足
   - 部署简单
   - 自动 HTTPS

2. **Render**
   - 免费套餐可用
   - 部署简单

3. **Fly.io**
   - 全球部署
   - 性能好

## 总结

**推荐配置：**
1. ✅ 代码托管：GitHub（主）+ Gitee（镜像）
2. ✅ 前端部署：Vercel 或 GitHub Pages
3. ✅ 后端部署：Railway 或 Render
4. ✅ 博客集成：在 Hexo 博客中添加入口链接
5. ✅ SEO 优化：添加 meta 标签、提交搜索引擎

这样既能保证 SEO 友好，又能方便部署和维护！

