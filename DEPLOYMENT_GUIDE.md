# 项目部署指南

## 代码托管平台选择

### 推荐方案：GitHub（主）+ Gitee（镜像）

**选择 GitHub 的原因：**
1. ✅ **SEO 友好**：GitHub 内容更容易被搜索引擎索引
2. ✅ **国际化**：GitHub 在全球范围内访问速度快
3. ✅ **GitHub Pages**：可以直接部署前端到 GitHub Pages
4. ✅ **社区活跃**：便于分享和协作
5. ✅ **与博客集成**：如果博客在 GitHub，项目也在 GitHub 更方便

**Gitee 作为镜像：**
- 方便国内用户访问和克隆
- 可以作为备份

## 部署架构建议

### 方案一：前后端分离部署（推荐）

```
前端（GitHub Pages / Vercel / Netlify）
  ↓ API 调用
后端（Railway / Render / Fly.io / Zeabur）
```

**优势：**
- 前后端独立扩展
- 前端可以享受 CDN 加速
- SEO 友好（静态页面）

### 方案二：全栈部署（简化）

```
全栈（Vercel / Netlify / Railway）
  ↓
前后端一起部署
```

**优势：**
- 部署简单
- 统一管理

## 具体部署步骤

### 1. 准备上传到 GitHub

#### 1.1 检查 .gitignore

确保以下内容已忽略：
- `.env` 文件（包含敏感信息）
- `node_modules/`
- `__pycache__/`
- `*.egg-info/`
- `data/debug/`（调试数据）
- `.venv/`（虚拟环境）

#### 1.2 创建仓库

```bash
# 在 GitHub 创建新仓库，例如：ai-demo-service
# 然后执行：

git init
git add .
git commit -m "Initial commit: AI Demo Service with test case generation and knowledge base support"
git branch -M main
git remote add origin https://github.com/yourusername/ai-demo-service.git
git push -u origin main
```

### 2. 前端部署（GitHub Pages）

#### 方式一：GitHub Pages

1. 在仓库设置中启用 GitHub Pages
2. 选择 `frontend/dist` 目录作为源
3. 配置构建脚本：

```yaml
# .github/workflows/deploy-frontend.yml
name: Deploy Frontend

on:
  push:
    branches: [ main ]
    paths:
      - 'frontend/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: |
          cd frontend
          npm install
          npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./frontend/dist
```

#### 方式二：Vercel（推荐，更简单）

1. 连接 GitHub 仓库到 Vercel
2. 设置构建配置：
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
3. 环境变量：
   - `VITE_API_BASE_URL`: 后端 API 地址

### 3. 后端部署

#### Railway（推荐，简单）

1. 连接 GitHub 仓库
2. 设置：
   - Root Directory: `backend`
   - Start Command: `python -m app.main`
3. 环境变量：
   ```
   AI_DEMO_BACKEND_HOST=0.0.0.0
   AI_DEMO_BACKEND_PORT=$PORT
   AI_DEMO_CORS_ORIGINS=https://your-frontend-domain.com
   AI_DEMO_LLM_BASE_URL=http://localhost:11434
   ```

#### Render

1. 创建 Web Service
2. 设置：
   - Build Command: `cd backend && pip install -e .`
   - Start Command: `cd backend && python -m app.main`
3. 配置环境变量

### 4. 博客集成

#### 方式一：在博客中添加入口链接

在 Hexo 博客中添加一个页面或文章：

```markdown
---
title: AI 测试用例生成工具
date: 2024-01-01
---

## AI 测试用例生成工具

这是一个基于 AI 的测试用例生成工具，支持：
- 需求文档分析
- 功能模块提取
- 测试用例自动生成

[访问工具](https://your-frontend-domain.com)
```

#### 方式二：嵌入到博客中（iframe）

```html
<iframe 
  src="https://your-frontend-domain.com" 
  width="100%" 
  height="800px"
  frameborder="0">
</iframe>
```

#### 方式三：部署到博客子目录

如果使用 GitHub Pages，可以部署到：
- `yourusername.github.io/ai-demo/`

## SEO 优化建议

### 1. 前端 SEO

在 `frontend/index.html` 中添加：

```html
<head>
  <meta name="description" content="AI驱动的测试用例生成工具，支持需求文档分析和测试用例自动生成">
  <meta name="keywords" content="AI,测试用例,自动化测试,需求分析">
  <meta property="og:title" content="AI 测试用例生成工具">
  <meta property="og:description" content="基于AI的智能测试用例生成平台">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://your-domain.com">
</head>
```

### 2. 添加 sitemap.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://your-domain.com/</loc>
    <lastmod>2024-01-01</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
```

### 3. 添加 robots.txt

```
User-agent: *
Allow: /
Sitemap: https://your-domain.com/sitemap.xml
```

### 4. 博客文章优化

在博客中写文章介绍这个项目：
- 项目背景和功能
- 使用场景
- 技术栈介绍
- 链接到项目地址

## 环境变量配置

### 开发环境

创建 `.env.example` 文件（已创建），不要提交 `.env` 文件。

### 生产环境

在各部署平台配置环境变量，不要硬编码敏感信息。

## 域名配置（可选）

如果希望使用自定义域名：
1. 购买域名
2. 配置 DNS 解析
3. 在部署平台绑定域名
4. 配置 SSL 证书（通常自动）

## 监控和分析

### 1. Google Analytics

在 `frontend/index.html` 中添加：

```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
```

### 2. 百度统计（国内）

```html
<script>
var _hmt = _hmt || [];
(function() {
  var hm = document.createElement("script");
  hm.src = "https://hm.baidu.com/hm.js?YOUR_ID";
  var s = document.getElementsByTagName("script")[0];
  s.parentNode.insertBefore(hm, s);
})();
</script>
```

## 总结

**推荐方案：**
1. ✅ 代码托管：GitHub（主）+ Gitee（镜像）
2. ✅ 前端部署：Vercel 或 GitHub Pages
3. ✅ 后端部署：Railway 或 Render
4. ✅ 博客集成：在 Hexo 博客中添加入口链接
5. ✅ SEO 优化：添加 meta 标签、sitemap、robots.txt

这样既能保证 SEO 友好，又能方便部署和维护。

