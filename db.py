"""
Database connection and query utilities for EduTrack.
Supports both mysql.connector and PyMySQL, handles local and cloud databases
(Aiven, TiDB Cloud, Clever Cloud, Railway, Render), and supports DATABASE_URL.
"""

import os
import urllib.parse
from dotenv import load_dotenv
from flask import g, has_app_context, current_app

# Load .env file automatically
load_dotenv()

# Try importing mysql drivers with graceful fallback
DRIVER = None
try:
    import pymysql
    import pymysql.cursors
    DRIVER = "pymysql"
except ImportError:
    try:
        import mysql.connector
        DRIVER = "mysql.connector"
    except ImportError:
        DRIVER = None


def get_db_config():
    """
    Parse database configuration from environment variables.
    Supports single connection strings (DATABASE_URL, MYSQL_URL)
    or separate DB_* variables with sensible local defaults.
    """
    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("MYSQL_URL")
        or os.getenv("JAWSDB_URL")
        or os.getenv("CLEARDB_DATABASE_URL")
    )

    if db_url:
        parsed = urllib.parse.urlparse(db_url)
        database = parsed.path.lstrip("/")
        # Some URLs include query params like ?ssl-mode=REQUIRED
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": urllib.parse.unquote(parsed.username or "root"),
            "password": urllib.parse.unquote(parsed.password or ""),
            "database": database or "student_performance_db",
            "ssl_required": ("ssl" in parsed.query.lower() or parsed.hostname not in ("localhost", "127.0.0.1", None))
        }

    host = os.getenv("DB_HOST", "localhost").strip()
    port_str = os.getenv("DB_PORT", "3306").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 3306

    user = os.getenv("DB_USER", "root").strip()
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "student_performance_db").strip()

    # Determine SSL mode: enable by default for remote hosts, disable for localhost
    ssl_env = os.getenv("DB_SSL", "").strip().lower()
    if ssl_env in ("true", "1", "yes", "require", "required"):
        ssl_required = True
    elif ssl_env in ("false", "0", "no", "disable"):
        ssl_required = False
    else:
        # Default: require SSL for cloud hosts, disable for local
        ssl_required = host not in ("localhost", "127.0.0.1", "")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "ssl_required": ssl_required
    }


_pool = None


def get_pool():
    """Initialize or return the global connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    if DRIVER == "mysql.connector":
        from mysql.connector import pooling
        cfg = get_db_config()
        pool_kwargs = {
            "pool_name": "edutrack_pool",
            "pool_size": 4,
            "pool_reset_session": True,
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "password": cfg["password"],
            "database": cfg["database"],
            "connection_timeout": 10
        }
        if cfg["ssl_required"]:
            pool_kwargs["ssl_disabled"] = False
        else:
            pool_kwargs["ssl_disabled"] = True

        try:
            _pool = pooling.MySQLConnectionPool(**pool_kwargs)
            return _pool
        except Exception:
            _pool = None
            return None
    return None


def create_connection():
    """Create a database connection, preferring pooled connections for low latency."""
    if DRIVER is None:
        raise RuntimeError(
            "No MySQL driver installed. Please install mysql-connector-python or pymysql."
        )

    # Use connection pool if available (substantially reduces latency on cloud hosts like Aiven)
    pool = get_pool()
    if pool is not None:
        try:
            conn = pool.get_connection()
            if hasattr(conn, "ping"):
                try:
                    conn.ping(reconnect=True, attempts=2, delay=1)
                except Exception:
                    pass
            return conn
        except Exception:
            pass  # Fall back to direct connection if pool is busy or failed

    cfg = get_db_config()

    if DRIVER == "pymysql":
        kwargs = {
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "password": cfg["password"],
            "database": cfg["database"],
            "charset": "utf8mb4",
            "autocommit": False,
            "connect_timeout": 10
        }
        if cfg["ssl_required"]:
            kwargs["ssl"] = {"ssl_mode": "REQUIRED"}
        return pymysql.connect(**kwargs)

    else:  # mysql.connector direct
        kwargs = {
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "password": cfg["password"],
            "database": cfg["database"],
            "connection_timeout": 10
        }
        if cfg["ssl_required"]:
            kwargs["ssl_disabled"] = False
        else:
            kwargs["ssl_disabled"] = True

        return mysql.connector.connect(**kwargs)


def get_db():
    """
    Get or create a database connection.
    Stored on flask.g if inside an app context so all queries in one
    request share a single connection.
    """
    if has_app_context():
        if "db" not in g:
            g.db = create_connection()
        return g.db
    return create_connection()


def close_db(e=None):
    """Close the request-scoped database connection if open."""
    if has_app_context():
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def get_db_connection():
    """Compatibility alias for get_db()."""
    return get_db()


def get_dict_cursor(conn):
    """Return a cursor configured to return dictionaries across both drivers."""
    if DRIVER == "pymysql":
        return conn.cursor(pymysql.cursors.DictCursor)
    return conn.cursor(dictionary=True)


def query_db(query, args=(), one=False):
    """
    Execute a SELECT query and return rows as dictionaries.
    If one=True, returns the first row or None.
    """
    conn = get_db()
    cursor = get_dict_cursor(conn)
    try:
        cursor.execute(query, args)
        rows = cursor.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        cursor.close()
        if not has_app_context():
            conn.close()


def execute_db(query, args=(), commit=True):
    """
    Execute an INSERT, UPDATE, or DELETE query.
    Returns (rowcount, lastrowid).
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
        if commit:
            conn.commit()
        rowcount = cursor.rowcount
        lastrowid = getattr(cursor, "lastrowid", None)
        return rowcount, lastrowid
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        cursor.close()
        if not has_app_context():
            conn.close()


def init_db(conn=None):
    """
    Initialize database schema and default seed data.
    Idempotent and safe to run on startup.
    """
    should_close = False
    if conn is None:
        conn = create_connection()
        should_close = True

    cursor = conn.cursor()
    try:
        # Create students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INT AUTO_INCREMENT PRIMARY KEY,
                roll_no VARCHAR(30) NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                section VARCHAR(30) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Create subjects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id INT AUTO_INCREMENT PRIMARY KEY,
                subject_name VARCHAR(100) NOT NULL UNIQUE,
                max_marks INT NOT NULL DEFAULT 100,
                pass_marks INT NOT NULL DEFAULT 40
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Create marks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marks (
                mark_id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                subject_id INT NOT NULL,
                assessment VARCHAR(30) NOT NULL,
                marks_obtained DECIMAL(5,2) NOT NULL,
                max_marks INT NOT NULL,
                CONSTRAINT uq_student_subject_assessment UNIQUE (student_id, subject_id, assessment),
                CONSTRAINT fk_marks_student FOREIGN KEY (student_id)
                    REFERENCES students(student_id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_marks_subject FOREIGN KEY (subject_id)
                    REFERENCES subjects(subject_id)
                    ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Insert default subjects if they do not exist
        default_subjects = [
            ("Java", 100, 40),
            ("Python", 100, 40),
            ("DBMS", 100, 40),
            ("Mathematics", 100, 40),
        ]
        for name, max_m, pass_m in default_subjects:
            cursor.execute("""
                INSERT IGNORE INTO subjects (subject_name, max_marks, pass_marks)
                VALUES (%s, %s, %s)
            """, (name, max_m, pass_m))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        if should_close:
            conn.close()


def seed_sample_data(conn=None):
    """Populate sample students and marks for demonstration."""
    should_close = False
    if conn is None:
        conn = create_connection()
        should_close = True

    cursor = get_dict_cursor(conn)
    try:
        # Check if students already exist
        cursor.execute("SELECT COUNT(*) AS total FROM students")
        row = cursor.fetchone()
        if row and (row["total"] if isinstance(row, dict) else row[0]) > 0:
            return False, "Database already has students; skipping seed."

        sample_students = [
            ("22CS001", "Aarav Sharma", "CSE-A"),
            ("22CS002", "Diya Patel", "CSE-A"),
            ("22CS003", "Karthik Raja", "CSE-B"),
            ("22CS004", "Meera Nair", "CSE-B"),
            ("22CS005", "Rohan Verma", "CSE-A")
        ]

        for roll_no, name, sec in sample_students:
            cursor.execute(
                "INSERT INTO students (roll_no, name, section) VALUES (%s, %s, %s)",
                (roll_no, name, sec)
            )

        # Retrieve student IDs and subject IDs
        cursor.execute("SELECT student_id, roll_no FROM students")
        students = cursor.fetchall()
        cursor.execute("SELECT subject_id, subject_name FROM subjects")
        subjects = cursor.fetchall()

        stud_map = {s["roll_no"]: s["student_id"] for s in students}
        subj_map = {s["subject_name"]: s["subject_id"] for s in subjects}

        sample_marks = [
            # Aarav Sharma - Internal 1 (High performer)
            ("22CS001", "Java", "Internal 1", 46.0, 50),
            ("22CS001", "Python", "Internal 1", 48.0, 50),
            ("22CS001", "DBMS", "Internal 1", 44.0, 50),
            ("22CS001", "Mathematics", "Internal 1", 47.0, 50),

            # Diya Patel - Internal 1 (Good performer)
            ("22CS002", "Java", "Internal 1", 40.0, 50),
            ("22CS002", "Python", "Internal 1", 42.0, 50),
            ("22CS002", "DBMS", "Internal 1", 38.0, 50),
            ("22CS002", "Mathematics", "Internal 1", 35.0, 50),

            # Karthik Raja - Internal 1 (Needs assistance in Mathematics)
            ("22CS003", "Java", "Internal 1", 30.0, 50),
            ("22CS003", "Python", "Internal 1", 28.0, 50),
            ("22CS003", "DBMS", "Internal 1", 25.0, 50),
            ("22CS003", "Mathematics", "Internal 1", 16.0, 50),  # Failed (<20)

            # Meera Nair - Internal 1 (Needs assistance in DBMS)
            ("22CS004", "Java", "Internal 1", 35.0, 50),
            ("22CS004", "Python", "Internal 1", 32.0, 50),
            ("22CS004", "DBMS", "Internal 1", 18.0, 50),  # Failed (<20)
            ("22CS004", "Mathematics", "Internal 1", 34.0, 50),

            # Rohan Verma - Incomplete (only Java and Python recorded)
            ("22CS005", "Java", "Internal 1", 39.0, 50),
            ("22CS005", "Python", "Internal 1", 41.0, 50),
        ]

        for roll_no, sub_name, exam, marks, max_m in sample_marks:
            s_id = stud_map.get(roll_no)
            sub_id = subj_map.get(sub_name)
            if s_id and sub_id:
                cursor.execute("""
                    INSERT IGNORE INTO marks (student_id, subject_id, assessment, marks_obtained, max_marks)
                    VALUES (%s, %s, %s, %s, %s)
                """, (s_id, sub_id, exam, marks, max_m))

        conn.commit()
        return True, "Sample students and assessment marks seeded successfully!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        if should_close:
            conn.close()
