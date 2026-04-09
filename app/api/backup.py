"""
Database Backup API router
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import os
import shutil
import glob

from app.database.database import get_db, engine
from app.models.users import User
from app.models.configurations import ConfigOption
from app.api.auth import get_current_user

router = APIRouter()

BACKUP_DIR = "backups"
DB_FILE = "voniko.db"

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)


@router.get("/config")
async def get_backup_config(db: Session = Depends(get_db)):
    """获取自动备份配置"""
    config = db.query(ConfigOption).filter(
        ConfigOption.option_type == "system_setting",
        ConfigOption.option_value == "backup_interval_hours"
    ).first()
    
    interval = int(config.parent_value) if config and config.parent_value else 0
    return {"interval_hours": interval}


@router.post("/config")
async def set_backup_config(
    interval_hours: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """设置自动备份配置"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    config = db.query(ConfigOption).filter(
        ConfigOption.option_type == "system_setting",
        ConfigOption.option_value == "backup_interval_hours"
    ).first()
    
    if not config:
        config = ConfigOption(
            option_type="system_setting",
            option_value="backup_interval_hours",
            parent_value=str(interval_hours)
        )
        db.add(config)
    else:
        config.parent_value = str(interval_hours)
        
    db.commit()
    return {"message": "备份配置已更新", "interval_hours": interval_hours}


@router.get("/list")
async def list_backups(current_user: User = Depends(get_current_user)):
    """获取所有备份文件列表"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    backups = []
    for file_path in glob.glob(os.path.join(BACKUP_DIR, "*.db")):
        stat = os.stat(file_path)
        backups.append({
            "filename": os.path.basename(file_path),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
        
    # Sort by created_at descending
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


@router.post("/create")
async def create_backup(current_user: User = Depends(get_current_user)):
    """手动创建全量备份"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    if not os.path.exists(DB_FILE):
        raise HTTPException(status_code=404, detail="主数据库文件不存在")
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"voniko_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        # SQLite handles simple file copy fine for basic backups, 
        # but in production a proper backup command or lock might be needed.
        shutil.copy2(DB_FILE, backup_path)
        
        stat = os.stat(backup_path)
        return {
            "message": "备份创建成功",
            "backup": {
                "filename": backup_filename,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@router.post("/restore/{filename}")
async def restore_backup(
    filename: str, 
    current_user: User = Depends(get_current_user)
):
    """从指定文件还原数据库"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")
        
    try:
        # Close all active connections before replacing the file
        engine.dispose()
        
        # Replace the database file
        shutil.copy2(backup_path, DB_FILE)
        
        return {"message": "数据库还原成功，建议刷新页面或重启服务"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"还原失败: {str(e)}")


@router.delete("/{filename}")
async def delete_backup(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """删除备份文件"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")
        
    try:
        os.remove(backup_path)
        return {"message": "备份文件已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
