# Verification

- 日期：2026-04-24 14:24:54 +08:00
- 执行者：Codex

## 已验证

- 后端完整测试：`uv run pytest`，44 passed。
- 旧 SQLite schema 回归测试：覆盖 `paper`、`knowledge_point`、`solution_method` 的遗留 `subject` 列清理。
- 当前本地数据库：已执行 `init_db()`，`paper` 表 schema 中不再有 `subject`。

## 故障结论

文件夹批量导入的 network error 不是前端目录选择或网络连通性问题，而是旧 SQLite 表结构与当前模型不一致导致服务端插入失败。
