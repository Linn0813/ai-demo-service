#!/bin/bash

# GitHub 上传脚本
# 使用方法：bash UPLOAD_STEPS.sh

echo "=========================================="
echo "  GitHub 上传准备脚本"
echo "=========================================="
echo ""

# 检查是否已初始化 Git
if [ ! -d ".git" ]; then
    echo "1. 初始化 Git 仓库..."
    git init
    echo "✅ Git 仓库已初始化"
else
    echo "✅ Git 仓库已存在"
fi

echo ""
echo "2. 检查 Git 配置..."
if ! git config user.name > /dev/null 2>&1; then
    echo "⚠️  需要配置 Git 用户信息"
    echo "   请执行："
    echo "   git config user.name '你的名字'"
    echo "   git config user.email 'your.email@example.com'"
    exit 1
fi

echo "✅ Git 用户信息已配置"
echo "   用户名: $(git config user.name)"
echo "   邮箱: $(git config user.email)"
echo ""

echo "3. 添加文件到暂存区..."
git add .
echo "✅ 文件已添加到暂存区"
echo ""

echo "4. 检查要提交的文件..."
echo "   文件数量: $(git status --short | wc -l | xargs)"
echo ""

echo "5. 准备提交..."
echo "   请确认要提交的文件列表："
git status --short | head -20
echo "   ..."
echo ""

read -p "是否继续提交？(y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 1
fi

echo ""
echo "6. 提交文件..."
git commit -m "Initial commit: AI Demo Service

- 前后端分离架构（FastAPI + Vue3）
- 测试用例生成功能
- 知识库问答功能（规划中）
- 支持多种LLM模型（Qwen、DeepSeek等）
- 完整的项目文档和部署指南"

if [ $? -eq 0 ]; then
    echo "✅ 文件已提交"
else
    echo "❌ 提交失败"
    exit 1
fi

echo ""
echo "7. 设置主分支..."
git branch -M main
echo "✅ 主分支已设置为 main"
echo ""

echo "=========================================="
echo "  下一步操作："
echo "=========================================="
echo ""
echo "1. 在 GitHub 创建仓库（如果还没有）"
echo "   https://github.com/new"
echo ""
echo "2. 添加远程仓库（替换 yourusername 为你的用户名）："
echo "   git remote add origin https://github.com/yourusername/ai-demo-service.git"
echo ""
echo "3. 推送到 GitHub："
echo "   git push -u origin main"
echo ""
echo "4. 如果需要 Personal Access Token："
echo "   访问：https://github.com/settings/tokens"
echo "   创建 token，权限选择 'repo'"
echo ""
echo "=========================================="

