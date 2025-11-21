# 重构迁移总结

## 已完成的工作

### ✅ 1. 目录结构创建
- 创建了 `backend/` 目录结构
- 创建了 `backend/core/engine/base/` 基础共享服务目录
- 创建了 `backend/core/engine/test_case/` 测试用例生成目录
- 创建了 `backend/app/` 应用层目录结构

### ✅ 2. 核心代码迁移
- ✅ `logger.py` → `backend/core/logger.py`
- ✅ `config.py` → `backend/core/engine/base/config.py`（更新为共享配置）
- ✅ `llm_service.py` → `backend/core/engine/base/llm_service.py`（共享服务）
- ✅ `debug_recorder.py` → `backend/core/engine/base/debug_recorder.py`（共享服务）
- ✅ 测试用例生成相关模块 → `backend/core/engine/test_case/`

### ✅ 3. 应用代码迁移
- ✅ `main.py` → `backend/app/main.py`
- ✅ `config.py` → `backend/app/config.py`
- ✅ `schemas.py` → `backend/app/schemas/common.py`
- ✅ `api/routes.py` → `backend/app/api/routes.py`
- ✅ `services/test_case_service.py` → `backend/app/services/test_case_service.py`

### ✅ 4. 导入路径更新
- ✅ 所有 `ai_demo_core.*` → `core.*`
- ✅ 所有 `ai_demo_service.*` → `app.*`
- ✅ 基础服务导入：`from core.engine.base.*`
- ✅ 测试用例生成导入：`from core.engine.test_case.*`

### ✅ 5. 配置文件更新
- ✅ 创建了 `backend/pyproject.toml`
- ✅ 更新了包配置路径

## 待完成的工作

### ⏳ 6. 脚本迁移
- [ ] 移动 `start.py` → `scripts/start_dev.py`
- [ ] 移动 `start.sh` → `scripts/start_dev.sh`
- [ ] 更新脚本中的路径引用

### ⏳ 7. 前端配置
- [ ] 检查前端 API 配置是否需要更新
- [ ] 更新前端环境变量配置（如果需要）

### ⏳ 8. 测试验证
- [ ] 测试后端启动：`cd backend && python -m app.main`
- [ ] 测试前端启动：`cd frontend && npm run dev`
- [ ] 验证 API 接口是否正常工作

## 新的目录结构

```
backend/
├── app/                    # 应用层
│   ├── main.py            # FastAPI 入口（可直接运行）
│   ├── config.py
│   ├── api/
│   │   └── routes.py
│   ├── schemas/
│   │   ├── common.py
│   │   └── __init__.py
│   └── services/
│       └── test_case_service.py
│
└── core/                   # 核心引擎
    ├── logger.py
    └── engine/
        ├── base/          # 基础共享服务
        │   ├── config.py
        │   ├── llm_service.py
        │   └── debug_recorder.py
        └── test_case/     # 测试用例生成
            ├── extractors.py
            ├── test_case_generator.py
            └── ...
```

## 启动方式

### 后端启动（新方式）
```bash
cd backend
python -m app.main
```

### 后端启动（uvicorn方式）
```bash
cd backend
uvicorn app.main:app --reload --port 8113
```

## 注意事项

1. **Python 路径**：需要在 `backend/` 目录下运行，或者设置 `PYTHONPATH`
2. **环境变量**：保持原有的环境变量配置不变
3. **数据目录**：`data/debug/` 目录路径已更新
4. **向后兼容**：schemas 模块通过 `__init__.py` 保持向后兼容

## 下一步

1. 完成脚本迁移
2. 测试验证功能
3. 更新 README 文档
4. 清理旧目录（可选）

