# Scripts Guide

本目录用于集中管理非核心运行脚本（数据库初始化/修复、运维清理等）。

## Directory Layout

- database/
  - init_db.py: 初始化数据库基础数据（管理员、示例供应商）
  - fix_schema.py: 一次性数据库结构修复脚本（高风险）
- maintenance/
  - hard_delete_orphans.py: 清理 uploads 中数据库未引用的孤儿文件（高风险，物理删除）

## Risk Levels

- Low
  - init_db.py
  - 说明: 幂等执行为主，但会创建默认数据。
- High
  - fix_schema.py
  - 说明: 直接执行 DDL/DML，可能影响生产数据完整性。
- High
  - hard_delete_orphans.py
  - 说明: 会物理删除文件，删除后不可恢复（除非有备份）。

## Recommended Execution Order

1. 备份数据库与 uploads 目录。
2. 执行数据库初始化（仅首次部署或缺失初始数据时）。
3. 如确有结构问题，再执行 schema 修复脚本。
4. 最后按需执行孤儿文件清理。

## Commands

在项目根目录执行：

```bash
python scripts/database/init_db.py
python scripts/database/fix_schema.py
python scripts/maintenance/hard_delete_orphans.py
```

## Safety Checklist

- 先在测试环境验证，再在生产执行。
- 执行前后记录数据库行数和关键表状态。
- 对 fix_schema.py 与 hard_delete_orphans.py，必须先做全量备份。
- 清理脚本执行后抽样校验关键文件是否仍可访问。

## Notes

- 主应用入口仍为 main.py，不属于 scripts 目录。
- scripts 目录中的脚本不应在应用启动链中自动运行。