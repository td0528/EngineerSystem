"""
VONIKO Factory Management System
Main application entry point
"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

import asyncio
from datetime import datetime, timedelta
import shutil
import glob

# Import routers
from app.api import auth, materials, orders, warehouse, tasks, records, documents, devices, supplier_portal, configurations, backup
from app.database.database import engine, Base, SessionLocal


async def backup_worker():
    """Background task for automatic database backups"""
    from app.models.configurations import ConfigOption
    
    while True:
        try:
            # Check every hour to avoid spamming the DB, or every minute if testing
            # Let's check every 15 minutes in production, but here we'll do 60s
            await asyncio.sleep(60)
            
            db = SessionLocal()
            try:
                # Get configured interval
                config = db.query(ConfigOption).filter(
                    ConfigOption.option_type == "system_setting",
                    ConfigOption.option_value == "backup_interval_hours"
                ).first()
                
                interval_hours = int(config.parent_value) if config and config.parent_value else 0
                
                if interval_hours > 0:
                    # Check when last backup was created
                    backup_dir = "backups"
                    os.makedirs(backup_dir, exist_ok=True)
                    
                    backups = glob.glob(os.path.join(backup_dir, "*.db"))
                    last_backup_time = 0
                    if backups:
                        latest_backup = max(backups, key=os.path.getmtime)
                        last_backup_time = os.path.getmtime(latest_backup)
                    
                    # If time since last backup > interval, create new backup
                    time_since_last = datetime.now().timestamp() - last_backup_time
                    if time_since_last > (interval_hours * 3600):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        # Use voniko.db or the path from env
                        db_path = os.getenv("DATABASE_URL", "sqlite:///./voniko.db").replace("sqlite:///./", "")
                        if os.path.exists(db_path):
                            backup_path = os.path.join(backup_dir, f"voniko_auto_{timestamp}.db")
                            shutil.copy2(db_path, backup_path)
                            print(f"[Backup] Automatic backup created: {backup_path}")
            finally:
                db.close()
        except Exception as e:
            print(f"[Backup Error] {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Create database tables on startup
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created")
    
    # Start background backup worker
    task = asyncio.create_task(backup_worker())
    
    yield
    
    # Cancel background task on shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print("[OK] Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="VONIKO Factory Management System",
    description="工厂集成管理系统 - 采购、库存、任务、资料管理",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directories
UPLOAD_DIRS = ["uploads", "uploads/materials", "uploads/documents", "uploads/tasks", "uploads/invoices", "uploads/quotations", "uploads/delivery_notes"]
for dir_path in UPLOAD_DIRS:
    os.makedirs(dir_path, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(materials.router, prefix="/api/materials", tags=["物料管理"])
app.include_router(orders.router, prefix="/api/orders", tags=["采购订单"])
app.include_router(warehouse.router, prefix="/api/warehouse", tags=["仓库管理"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务系统"])
app.include_router(records.router, prefix="/api/records", tags=["记录功能"])
app.include_router(documents.router, prefix="/api/documents", tags=["资料管理"])
app.include_router(devices.router, prefix="/api/devices", tags=["设备监控"])
app.include_router(supplier_portal.router, prefix="/api/supplier", tags=["供应商门户"])
app.include_router(configurations.router, prefix="/api/config", tags=["配置管理"])
app.include_router(backup.router, prefix="/api/backup", tags=["系统备份"])


@app.get("/")
async def root():
    """Redirect to main application"""
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
