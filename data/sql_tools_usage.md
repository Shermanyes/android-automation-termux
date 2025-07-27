# SQL工具使用说明

本文档提供了改进版SQLite数据库管理器和辅助工具的使用说明，这些工具旨在提高数据库的可维护性，允许开发者以易读的SQL文件格式导出和导入数据库。

## 目录

1. [改进的数据库管理器](#改进的数据库管理器)
2. [SQL导出工具](#sql导出工具)
3. [SQL导入工具](#sql导入工具)
4. [实现细节](#实现细节)
5. [常见问题](#常见问题)

## 改进的数据库管理器

### 主要改进

- 代码结构优化，提高可读性和可维护性
- 增加导出SQL文件的功能
- 增加从SQL文件导入数据的功能
- 连接池管理更加稳定
- 错误处理和日志记录更完善

### 替换步骤

1. 备份原始`data/database_manager.py`文件
2. 用新版的`database_manager.py`替换原文件

### 新增功能

在`DatabaseManager`类中，新增了两个有用的方法：

- `export_to_sql(output_path)`: 将整个数据库导出为可读的SQL文件
- `import_from_sql(sql_file_path)`: 从SQL文件导入数据到数据库

使用示例：
```python
from data.database_manager import DatabaseManager

# 创建数据库管理器实例
db = DatabaseManager("automation.db")

# 导出数据库到SQL文件
db.export_to_sql("backup.sql")

# 从SQL文件导入数据
db.import_from_sql("backup.sql")
```

## SQL导出工具

SQL导出工具可以将SQLite数据库导出为可读的SQL文件，方便查看和编辑。

### 使用方法

1. 使用以下命令导出数据库：

```bash
python -m data.sql_export_tool --db automation.db --output automation.sql
```

### 参数说明

- `--db`: SQLite数据库文件路径
- `--output`: 导出的SQL文件路径
- `--schema-only`: 仅导出表结构，不包含数据
- `--tables`: 要导出的表名列表（默认导出所有表）

### 导出示例

```bash
# 导出整个数据库（结构+数据）
python -m data.sql_export_tool --db automation.db --output full_export.sql

# 仅导出表结构
python -m data.sql_export_tool --db automation.db --output schema_only.sql --schema-only

# 只导出特定表
python -m data.sql_export_tool --db automation.db --output specific_tables.sql --tables apps accounts
```

## SQL导入工具

SQL导入工具可以从SQL文件导入数据到SQLite数据库，方便在不同系统之间迁移数据。

### 使用方法

使用以下命令导入数据库：

```bash
python -m data.sql_import_tool --db automation.db --sql automation.sql
```

### 参数说明

- `--db`: 目标SQLite数据库文件路径
- `--sql`: 输入的SQL文件路径
- `--force`: 出错时继续执行
- `--no-backup`: 不创建数据库备份

### 导入示例

```bash
# 导入SQL文件，自动创建备份
python -m data.sql_import_tool --db automation.db --sql exported_data.sql

# 强制导入，即使有错误也继续
python -m data.sql_import_tool --db automation.db --sql exported_data.sql --force

# 导入时不创建备份
python -m data.sql_import_tool --db automation.db --sql exported_data.sql --no-backup
```

## 实现细节

### SQL文件格式

生成的SQL文件包含以下内容：

1. 文件头部信息（导出时间、源数据库等）
2. 表结构定义（CREATE TABLE语句）
3. 表数据（INSERT语句）
4. 事务控制语句（BEGIN TRANSACTION, COMMIT）

例如：

```sql
-- 自动化系统数据库导出
-- 时间: 2025-03-30 10:00:00
-- 源数据库: automation.db
-- 导出工具: SQL导出工具

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 表 apps
DROP TABLE IF EXISTS apps;
CREATE TABLE apps (
    app_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    package_name TEXT,
    priority INTEGER DEFAULT 5,
    time_slice INTEGER DEFAULT 3600,
    daily_limit INTEGER DEFAULT 7200,
    reset_time TEXT DEFAULT '04:00',
    status TEXT DEFAULT 'inactive',
    config TEXT,
    last_update INTEGER
);

-- 表 apps 的数据
INSERT INTO apps (app_id, name, package_name, priority) VALUES ('app1', '测试应用', 'com.test.app', 5);

-- 更多表和数据...

COMMIT;
PRAGMA foreign_keys = ON;
```

### 连接池管理

数据库管理器使用连接池管理SQLite连接，有以下好处：

1. 减少频繁打开/关闭连接的开销
2. 限制同时打开的连接数量
3. 自动处理连接的获取和释放

## 常见问题

### Q: 为什么选择SQL文件而不是其他格式？
A: SQL文件是一种标准格式，可以被几乎所有的数据库工具读取和编辑，包括许多免费的SQL编辑器。

### Q: 导出的SQL文件可以被哪些工具打开？
A: 几乎所有的SQL编辑器都可以打开，包括：
- SQLite Browser (免费，跨平台)
- Navicat (商业软件)
- DBeaver (免费，跨平台)
- Visual Studio Code + SQLite扩展 (免费，跨平台)
- PyCharm Professional + 数据库插件

### Q: 导入SQL文件会覆盖现有数据吗？
A: 是的，SQL导入工具默认会先删除现有表，然后重新创建。但工具会在导入前自动创建数据库备份，除非使用`--no-backup`参数。

### Q: 导出/导入工具支持大型数据库吗？
A: 是的，这些工具经过优化，可以处理较大的数据库。对于特别大的数据库，导出工具支持只导出特定表。

### Q: 导出的SQL文件可以手动编辑吗？
A: 是的，这是SQL文件的主要优势之一。你可以用任何文本编辑器打开并修改内容，然后再导入回数据库。
