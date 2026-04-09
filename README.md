# VONIKO Factory Management System

工厂集成管理系统后端服务

## 技术栈
- Python 3.11 + FastAPI
- SQLite + SQLAlchemy
- 纯HTML/CSS/JS前端

## 安装
```bash
pip install -r requirements.txt
```

## 运行
```bash
python main.py
```

访问 http://localhost:8000

## 脚本指南

维护与数据库脚本说明见 [scripts/README.md](scripts/README.md)。

常用命令（在项目根目录执行）：

```bash
python scripts/database/init_db.py
python scripts/database/fix_schema.py
python scripts/maintenance/hard_delete_orphans.py
```
