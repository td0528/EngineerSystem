"""
Initialize database with default data
Creates admin user and sample data
"""
import sys
sys.path.insert(0, '.')

from app.database.database import engine, SessionLocal, Base
from app.models.users import User, Supplier

def init_database():
    """Initialize database with default data"""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            # Create admin user with pre-hashed password 'admin123'
            admin = User(
                username="admin",
                hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Zy1.hM2rPH.bom",
                full_name="System Admin",
                email="admin@voniko.vn",
                department="IT",
                is_superuser=True
            )
            db.add(admin)
            print("[OK] Created admin user (username: admin, password: admin123)")
        else:
            print("[INFO] Admin user already exists")
        
        # Create a sample supplier for testing
        sample_supplier = db.query(Supplier).filter(Supplier.code == "SUP001").first()
        if not sample_supplier:
            supplier = Supplier(
                name="Sample Supplier Co., Ltd",
                code="SUP001",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Zy1.hM2rPH.bom",  # Same as admin123
                contact_person="John Doe",
                phone="0123456789",
                email="supplier@example.com"
            )
            db.add(supplier)
            print("[OK] Created sample supplier (code: SUP001, password: admin123)")
        
        db.commit()
        print("[OK] Database initialization complete!")
        
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
