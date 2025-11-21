# 前端启动指南

## 前置要求

- Node.js >= 18.0.0（推荐 20.x）
- npm 或 yarn

## 安装依赖

```bash
cd frontend
npm install
```

## 启动开发服务器

### 方式一：使用 npm scripts（推荐）

```bash
npm run dev
```

### 方式二：使用 npx（如果 vite 命令找不到）

```bash
npx vite
```

## 访问地址

启动成功后访问：http://localhost:3000

## 常见问题

### 1. vite: command not found

**解决方法**：
- 确保已运行 `npm install`
- 或使用 `npx vite` 代替 `vite`
- 或使用 `npm run dev`（已配置使用 npx）

### 2. Node.js 版本不兼容

如果遇到 Node.js 版本警告：
- 升级 Node.js 到 20.19+ 或 22.12+（推荐）
- 或使用兼容的 Vite 版本（已降级到 5.4.0）

### 3. 端口被占用

Vite 会自动使用下一个可用端口（3001, 3002...）

## 其他命令

```bash
# 开发模式
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

