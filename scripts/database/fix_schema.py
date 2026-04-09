import os
import sqlite3


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'voniko.db')

def fix_schema():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Disable foreign keys for this transaction
    c.execute("PRAGMA foreign_keys=OFF")
    
    # 2. Extract original DDL and replace "purchase_orders_old" with "purchase_orders"
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_items'")
    old_sql = c.fetchone()[0]
    
    new_sql = old_sql.replace('"purchase_orders_old"', 'purchase_orders')
    new_sql = new_sql.replace('CREATE TABLE order_items', 'CREATE TABLE order_items_new')
    
    # Extract indexes before dropping
    c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='order_items' AND sql IS NOT NULL")
    indexes = [row[0] for row in c.fetchall()]
    
    print("Executing new DDL: ", new_sql)
    
    # 3. Create the new table
    c.execute(new_sql)
    
    # 4. Copy data
    c.execute("INSERT INTO order_items_new SELECT * FROM order_items")
    print(f"Data copied: {c.rowcount} rows inserted.")
    
    # 5. Drop old table
    c.execute("DROP TABLE order_items")
    print("Old table dropped.")
    
    # 6. Rename new table
    c.execute("ALTER TABLE order_items_new RENAME TO order_items")
    print("Table renamed successfully.")
    
    # 7. Recreate indexes
    for idx_sql in indexes:
        print(f"Recreating index: {idx_sql}")
        c.execute(idx_sql)
        
    conn.commit()
    conn.close()
    print("Schema fix complete.")

if __name__ == "__main__":
    fix_schema()
