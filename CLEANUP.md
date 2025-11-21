# 清理旧文件说明

## 需要删除的文件/目录

重构完成后，以下文件/目录已经不再需要：

### 1. `src/` 目录
- **原因**：所有代码已迁移到 `backend/` 目录
- **包含内容**：
  - `src/ai_demo_core/` - 已迁移到 `backend/core/`
  - `src/ai_demo_service/` - 已迁移到 `backend/app/`
  - `src/ai_demo_service.egg-info/` - 构建产物，可删除

### 2. 根目录的 `pyproject.toml`
- **原因**：已移动到 `backend/pyproject.toml`
- **注意**：如果根目录还需要保留用于整体项目配置，可以保留；否则可以删除

## 清理命令

```bash
# 删除旧的源代码目录
rm -rf src/

# 如果确定不需要根目录的 pyproject.toml，也可以删除
# rm pyproject.toml
```

## 注意事项

1. **备份**：删除前建议先提交到 Git，或创建备份
2. **验证**：删除前确保新代码能正常运行
3. **Git 历史**：删除文件不会影响 Git 历史记录

## 保留的文件

以下文件应该保留：
- `backend/` - 新的后端代码目录
- `frontend/` - 前端代码目录
- `scripts/` - 脚本目录
- `data/` - 数据目录
- `docs/` - 文档目录
- `README.md` - 项目说明
- `.gitignore` - Git 忽略配置

