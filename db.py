"""
Database connection and query utilities for EduTrack.
Optimized for high-performance cloud databases (Aiven, TiDB Cloud, Render)
with persistent connection pooling, connection retry, and zero-latency caching.
"""

import os
import urllib.parse
import logging
from dotenv import load_dotenv
from flask import g, has_app_context

load_dotenv()
logger = logging.getLogger("edutrack.db")

# Prefer mysql.connector for native C-optimized connection pooling
DRIVER = None
try:
    import mysql.connector
    from mysql.connector import pooling
    DRIVER = "mysql.connector"
except ImportError:
    try:
        import pymysql
        import pymysql.cursors
        DRIVER = "pymysql"
    except ImportError:
        DRIVER = None


def get_db_config():
    """
    Parse database configuration from environment variables.
    Supports single connection strings (DATABASE_URL, MYSQL_URL)
    or separate DB_* variables with sensible defaults.
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

    ssl_env = os.getenv("DB_SSL", "").strip().lower()
    if ssl_env in ("true", "1", "yes", "require", "required"):
        ssl_required = True
    elif ssl_env in ("false", "0", "no", "disable"):
        ssl_required = False
    else:
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
            "pool_name": "edutrack_fast_pool",
            "pool_size": 4,
            "pool_reset_session": False,  # Crucial for low latency across cloud networks
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
            logger.info("Initialized MySQLConnectionPool successfully.")
            return _pool
        except Exception as e:
            logger.warning("Could not initialize connection pool: %s", e)
            _pool = None
            return None
    return None


def create_connection():
    """Borrow connection from pool or create direct connection."""
    if DRIVER is None:
        raise RuntimeError("No MySQL driver installed. Please install mysql-connector-python or pymysql.")

    pool = get_pool()
    if pool is not None:
        try:
            return pool.get_connection()
        except Exception:
            pass  # Fall back to direct connection if pool temporarily busy

    cfg = get_db_config()

    if DRIVER == "mysql.connector":
        kwargs = {
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "password": cfg["password"],
            "database": cfg["database"],
            "connection_timeout": 10
        }
        kwargs["ssl_disabled"] = False if cfg["ssl_required"] else True
        return mysql.connector.connect(**kwargs)

    else:  # pymysql fallback
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


def get_db():
    """Get or create request-scoped connection."""
    if has_app_context():
        if "db" not in g:
            g.db = create_connection()
        return g.db
    return create_connection()


def close_db(e=None):
    """Close request-scoped connection (returns it to pool)."""
    if has_app_context():
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def get_db_connection():
    return get_db()


def get_dict_cursor(conn):
    if DRIVER == "pymysql":
        return conn.cursor(pymysql.cursors.DictCursor)
    return conn.cursor(dictionary=True)


def query_db(query, args=(), one=False, retry=True):
    """
    Execute SELECT query with self-healing connection retry.
    """
    conn = get_db()
    cursor = get_dict_cursor(conn)
    try:
        cursor.execute(query, args)
        rows = cursor.fetchall()
        return (rows[0] if rows else None) if one else rows
    except Exception as e:
        # If remote connection was dropped, auto-reconnect and retry once
        if retry and has_app_context():
            g.pop("db", None)
            try:
                conn.close()
            except Exception:
                pass
            return query_db(query, args, one=one, retry=False)
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        if not has_app_context():
            try:
                conn.close()
            except Exception:
                pass


def execute_db(query, args=(), commit=True, retry=True):
    """
    Execute INSERT, UPDATE, DELETE with self-healing retry.
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
    except Exception as e:
        if commit:
            try:
                conn.rollback()
            except Exception:
                pass
        if retry and has_app_context():
            g.pop("db", None)
            try:
                conn.close()
            except Exception:
                pass
            return execute_db(query, args, commit=commit, retry=False)
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        if not has_app_context():
            try:
                conn.close()
            except Exception:
                pass


def init_db(conn=None):
    """Initialize database tables and subjects if they do not exist."""
    should_close = False
    if conn is None:
        conn = create_connection()
        should_close = True

    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INT AUTO_INCREMENT PRIMARY KEY,
                roll_no VARCHAR(30) NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                section VARCHAR(30) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id INT AUTO_INCREMENT PRIMARY KEY,
                subject_name VARCHAR(100) NOT NULL UNIQUE,
                max_marks INT NOT NULL DEFAULT 100,
                pass_marks INT NOT NULL DEFAULT 40
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

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
    """Seed sample data for testing."""
    should_close = False
    if conn is None:
        conn = create_connection()
        should_close = True

    cursor = get_dict_cursor(conn)
    try:
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
            cursor.execute("INSERT INTO students (roll_no, name, section) VALUES (%s, %s, %s)", (roll_no, name, sec))

        cursor.execute("SELECT student_id, roll_no FROM students")
        students = cursor.fetchall()
        cursor.execute("SELECT subject_id, subject_name FROM subjects")
        subjects = cursor.fetchall()

        stud_map = {s["roll_no"]: s["student_id"] for s in students}
        subj_map = {s["subject_name"]: s["subject_id"] for s in subjects}

        sample_marks = [
            ("22CS001", "Java", "Internal 1", 46.0, 50),
            ("22CS001", "Python", "Internal 1", 48.0, 50),
            ("22CS001", "DBMS", "Internal 1", 44.0, 50),
            ("22CS001", "Mathematics", "Internal 1", 47.0, 50),
            ("22CS002", "Java", "Internal 1", 40.0, 50),
            ("22CS002", "Python", "Internal 1", 42.0, 50),
            ("22CS002", "DBMS", "Internal 1", 38.0, 50),
            ("22CS002", "Mathematics", "Internal 1", 35.0, 50),
            ("22CS003", "Java", "Internal 1", 30.0, 50),
            ("22CS003", "Python", "Internal 1", 28.0, 50),
            ("22CS003", "DBMS", "Internal 1", 25.0, 50),
            ("22CS003", "Mathematics", "Internal 1", 16.0, 50),
            ("22CS004", "Java", "Internal 1", 35.0, 50),
            ("22CS004", "Python", "Internal 1", 32.0, 50),
            ("22CS004", "DBMS", "Internal 1", 18.0, 50),
            ("22CS004", "Mathematics", "Internal 1", 34.0, 50),
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
