# 数据安全与迁移脚本

本目录包含保护老用户数据的安全机制和恢复工具。

## 🛡️ 数据安全保护机制

### 自动备份触发
- **时机**: 每次数据库迁移前自动触发
- **位置**: `app/db/migration.py:127` 集成到应用启动流程
- **覆盖**: 所有用户相关表数据

### 备份内容
```
data_backups/
└── checkpoint_YYYYMMDD_HHMMSS/
    ├── checkpoint_info.json      # 检查点元信息
    ├── users_backup_*.json       # 用户数据
    ├── novels_backup_*.json      # 小说数据
    ├── chapters_backup_*.json    # 章节数据
    ├── chapter_options_backup_*.json
    ├── user_choices_backup_*.json
    └── generation_tasks_backup_*.json
```

## 🔧 使用方法

### 1. 手动创建备份
```bash
# 创建当前数据的完整备份
cd E:\DevRep\inkflow
uv run python scripts/data_migration_safety.py
```

### 2. 交互式数据恢复
```bash
# 启动交互式恢复工具
cd E:\DevRep\inkflow
uv run python scripts/data_recovery.py
```

恢复流程：
1. 显示所有可用检查点
2. 用户选择恢复时间点
3. 二次确认（输入 'YES'）
4. 自动按依赖顺序恢复表数据
5. 验证数据完整性

### 3. 程序化恢复
```python
from scripts.data_recovery import DataRecoveryManager

async def restore_data():
    manager = DataRecoveryManager()
    await manager.connect()

    # 列出备份
    backups = manager.list_available_backups()

    # 恢复最新备份
    if backups:
        await manager.restore_from_checkpoint(backups[0]["checkpoint_path"])

    await manager.disconnect()
```

## 🔍 数据完整性检查

每次备份和恢复都会验证：
- ✅ 用户-小说关联完整性
- ✅ 小说-章节关联完整性
- ✅ 外键约束无孤立记录
- ✅ 基础数据统计

## ⚠️ 重要说明

### 使用注意事项
1. **恢复操作不可逆** - 会清空当前数据
2. **停止服务** - 恢复时确保应用服务已停止
3. **备份验证** - 优先选择数据完整性✅的检查点
4. **依赖顺序** - 系统会自动按外键依赖顺序恢复

### 紧急恢复流程
```bash
# 1. 停止服务
docker-compose down

# 2. 启动数据库
docker-compose up -d postgres

# 3. 执行恢复
uv run python scripts/data_recovery.py

# 4. 重启服务
docker-compose up -d
```

## 🚀 生产环境建议

### 定期备份策略
```bash
# 添加到 crontab
0 2 * * * cd /path/to/inkflow && uv run python scripts/data_migration_safety.py
```

### 监控告警
- 备份失败时发送通知
- 磁盘空间监控
- 数据完整性异常报警

### 多层备份
1. **应用级**: 此脚本提供的JSON备份
2. **数据库级**: PostgreSQL pg_dump
3. **系统级**: 磁盘快照/备份

## 📊 检查点信息格式

```json
{
  "checkpoint_time": "20250923_142355",
  "database_url": "postgresql+asyncpg://...",
  "backup_files": {
    "users": "/path/to/users_backup.json",
    "novels": "/path/to/novels_backup.json"
  },
  "data_integrity": true,
  "migration_notes": "迁移前自动检查点 - 保护老用户数据"
}
```

这套机制确保任何数据库迁移都不会导致老用户数据丢失，并提供快速恢复能力。