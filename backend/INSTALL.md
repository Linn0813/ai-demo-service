# 安装说明

## 在虚拟环境中安装

### 1. 激活虚拟环境

```bash
# 在项目根目录
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate  # Windows
```

### 2. 进入 backend 目录并安装

```bash
cd backend
pip install -e .
```

### 3. 验证安装

```bash
python -c "import app; import uvicorn; print('安装成功！')"
```

### 4. 启动服务

```bash
# 在 backend 目录下
python -m app.main
```

## 如果遇到问题

### 问题1：找不到模块
确保在 `backend/` 目录下运行，或者设置 PYTHONPATH：
```bash
export PYTHONPATH=$PWD/backend:$PYTHONPATH
```

### 问题2：依赖版本冲突
可以尝试单独安装依赖：
```bash
pip install fastapi uvicorn[standard] requests python-dotenv
```

### 问题3：Python 版本
确保 Python 版本 >= 3.10：
```bash
python --version
```

