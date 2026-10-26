"""
Database connection test script for EduTrack.
Tests connectivity and prints table information.
"""

from db import create_connection, DRIVER, get_db_config, init_db

print("=" * 60)
print("EduTrack Database Connection Diagnostic")
print("=" * 60)
print(f"Driver in use: {DRIVER}")

cfg = get_db_config()
print(f"Target Host: {cfg['host']}:{cfg['port']}")
print(f"Database:    {cfg['database']}")
print(f"User:        {cfg['user']}")
print(f"SSL Mode:    {'Enabled' if cfg['ssl_required'] else 'Disabled'}")
print("-" * 60)

try:
    conn = create_connection()
    print("MySQL connection SUCCESSFUL!")

    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tables = [row[0] if isinstance(row, tuple) else list(row.values())[0] for row in cursor.fetchall()]

    print(f"\nTables present in database ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")

    if not tables:
        print("\nNo tables found. Initializing schema automatically...")
        init_db(conn)
        print("Schema initialized successfully!")

    cursor.close()
    conn.close()
    print("-" * 60)
    print("Database is ready for EduTrack!")
except Exception as e:
    print("\nDatabase connection FAILED!")
    print(f"Error: {e}")
    print("-" * 60)
    print("Troubleshooting steps:")
    print("  1. Verify MySQL server is running.")
    print("  2. Check host, port, user, and password in .env or Render environment.")
    print("  3. For cloud databases (Aiven/TiDB), ensure DB_SSL=true or use DATABASE_URL.")
