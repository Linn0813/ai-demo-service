# GitHub 上传完整指南

## 步骤一：在 GitHub 创建仓库

### 1. 登录 GitHub
访问 [https://github.com](https://github.com) 并登录

### 2. 创建新仓库
1. 点击右上角的 **"+"** 按钮
2. 选择 **"New repository"**

### 3. 填写仓库信息
- **Repository name**: `ai-demo-service`（或你喜欢的名字）
- **Description**: `AI驱动的测试用例生成工具，支持需求文档分析和测试用例自动生成`
- **Visibility**: 选择 **Public**（公开，便于SEO和分享）
- **不要勾选**以下选项（因为项目已有这些文件）：
  - ❌ Add a README file
  - ❌ Add .gitignore
  - ❌ Choose a license（我们已添加 LICENSE 文件）

### 4. 点击 "Create repository"

创建完成后，GitHub 会显示一个页面，上面有仓库地址，类似：
```
https://github.com/yourusername/ai-demo-service.git
```

## 步骤二：在本地初始化 Git

### 1. 检查是否已初始化 Git

```bash
# 在项目根目录执行
cd /Users/yuxiaoling/PycharmProjects/ai_demo_service
git status
```

如果显示 "not a git repository"，需要初始化。

### 2. 初始化 Git（如果还没有）

```bash
git init
```

### 3. 检查文件状态

```bash
git status
```

应该看到很多未跟踪的文件。

## 步骤三：添加和提交文件

### 1. 添加所有文件

```bash
git add .
```

### 2. 检查要提交的文件

```bash
git status
```

确认 `.env`、`node_modules/`、`__pycache__/` 等敏感文件没有被添加。

### 3. 提交文件

```bash
git commit -m "Initial commit: AI Demo Service

- 前后端分离架构（FastAPI + Vue3）
- 测试用例生成功能
- 知识库问答功能（规划中）
- 支持多种LLM模型（Qwen、DeepSeek等）
- 完整的项目文档和部署指南"
```

## 步骤四：连接到 GitHub 并推送

### 1. 添加远程仓库

将 `yourusername` 替换为你的 GitHub 用户名：

```bash
git remote add origin https://github.com/yourusername/ai-demo-service.git
```

### 2. 重命名分支为 main（如果当前是 master）

```bash
git branch -M main
```

### 3. 推送到 GitHub

```bash
git push -u origin main
```

如果提示输入用户名和密码：
- **用户名**：你的 GitHub 用户名
- **密码**：使用 **Personal Access Token**（不是 GitHub 密码）

### 4. 如何获取 Personal Access Token

如果提示需要密码，需要创建 Personal Access Token：

1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 填写信息：
   - Note: `ai-demo-service-upload`
   - Expiration: 选择过期时间（建议 90 天或 No expiration）
   - 勾选权限：`repo`（全部权限）
4. 点击 "Generate token"
5. **复制 token**（只显示一次，务必保存）
6. 在命令行粘贴 token 作为密码

## 步骤五：验证上传成功

1. 刷新 GitHub 仓库页面
2. 应该能看到所有文件
3. 检查 README.md 是否正确显示

## 常见问题

### 1. 如果已经初始化过 Git

如果项目已经有 Git 历史，直接添加远程仓库：

```bash
git remote add origin https://github.com/yourusername/ai-demo-service.git
git branch -M main
git push -u origin main
```

### 2. 如果远程仓库已存在

```bash
# 先删除旧的远程仓库
git remote remove origin

# 添加新的远程仓库
git remote add origin https://github.com/yourusername/ai-demo-service.git
```

### 3. 如果推送被拒绝

```bash
# 先拉取远程更改（如果有）
git pull origin main --allow-unrelated-histories

# 然后再推送
git push -u origin main
```

### 4. 如果文件太大

GitHub 限制单个文件 100MB，如果超过：

```bash
# 检查大文件
find . -type f -size +50M

# 如果 node_modules 太大，确保已在 .gitignore 中
```

## 后续操作

### 1. 设置仓库 Topics（标签）

在 GitHub 仓库页面：
1. 点击仓库名称下方的齿轮图标
2. 在 "Topics" 中添加：`ai`, `test-case-generation`, `fastapi`, `vue3`, `llm`, `python`, `automation`

### 2. 添加仓库描述

在仓库页面点击 "Edit" 按钮，添加更详细的描述。

### 3. 设置 GitHub Pages（可选）

如果需要使用 GitHub Pages 部署前端：
1. 进入 Settings → Pages
2. Source 选择 "GitHub Actions"
3. 已配置自动部署工作流

## 完成！

上传成功后，你的项目就可以：
- ✅ 被搜索引擎索引
- ✅ 被其他开发者发现和使用
- ✅ 在博客中链接和展示
- ✅ 持续更新和维护

