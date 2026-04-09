import os
import sys

# Setup path for imports (project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database.database import SessionLocal
from app.models.materials import Material, Quotation, QuotationAttachment
from app.models.orders import PurchaseOrder, OrderItem, SupplierQuote, Invoice
from app.models.documents import Document, DocumentVersion
from app.models.records import Record
from app.models.tasks import Task, TaskAttachment


def get_all_db_file_paths(db):
    paths = set()
    
    # 1. Materials
    for m in db.query(Material).all():
        if m.image: paths.add(m.image)
        if m.drawing_pdf: paths.add(m.drawing_pdf)
    for q in db.query(Quotation).all():
        if q.file_path: paths.add(q.file_path)
    for qa in db.query(QuotationAttachment).all():
        if qa.file_path: paths.add(qa.file_path)
    
    # 2. PurchaseOrders & OrderItems & Quotes
    for o in db.query(PurchaseOrder).all():
        if o.invoice_file: paths.add(o.invoice_file)
    for i in db.query(OrderItem).all():
        if i.quotation_file: paths.add(i.quotation_file)
        if i.delivery_note: paths.add(i.delivery_note)
        if i.invoice_file: paths.add(i.invoice_file)
    for sq in db.query(SupplierQuote).all():
        if sq.invoice_file: paths.add(sq.invoice_file)
    for inv in db.query(Invoice).all():
         if inv.file_path: paths.add(inv.file_path)
        
    # 3. Documents
    for d in db.query(Document).all():
        if d.current_file_path: paths.add(d.current_file_path)
    for dv in db.query(DocumentVersion).all():
        if dv.file_path: paths.add(dv.file_path)
        
    # 4. Records
    for r in db.query(Record).all():
        if r.image_path: paths.add(r.image_path)
        
    # 5. Tasks
    for t in db.query(Task).all():
        if t.source_image: paths.add(t.source_image)
    for ta in db.query(TaskAttachment).all():
        if ta.file_path: paths.add(ta.file_path)

    # Normalize paths
    normalized = set()
    for p in paths:
        if p:
            # Strip leading slashes to match how os.walk might construct it if we format it
            # For example: '/uploads/materials/img.png' -> 'uploads/materials/img.png'
            n = str(p).strip().lstrip('/').replace('\\', '/')
            normalized.add(n)
            
    return normalized

def main():
    db = SessionLocal()
    allowed_paths = get_all_db_file_paths(db)
    db.close()
    
    upload_dir = os.path.join(PROJECT_ROOT, 'uploads')
    deleted_count = 0
    checked_count = 0
    
    if not os.path.exists(upload_dir):
        print("Uploads directory not found.")
        return
        
    for root, _, files in os.walk(upload_dir):
        for file in files:
            # Skip hidden files
            if file.startswith('.'):
                continue
                
            # Construct relative path to match DB convention: uploads/folder/file.pdf
            # os.path.join gives e.g. uploads\materials\img.png, so we replace \ with /
            file_path = os.path.join(root, file).replace('\\', '/')
            checked_count += 1
            
            if file_path not in allowed_paths:
                print(f"Deleting orphaned file: {file_path}")
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
                    
    print(f"Cleanup complete. Checked {checked_count} physical files. Hard-deleted {deleted_count} orphaned files.")

if __name__ == '__main__':
    main()
