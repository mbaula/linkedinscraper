"""
Database schema service layer.
"""
import sqlite3
from utils.db_utils import get_db_connection, close_db_connection


def verify_db_schema(config_dict):
    """
    Verify and update database schema to ensure all required columns and tables exist.
    
    Args:
        config_dict (dict): Configuration dictionary
        
    Returns:
        None
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()

    try:
        # Get the table information
        cursor.execute("PRAGMA table_info(jobs)")
        table_info = cursor.fetchall()
        column_names = [column[1] for column in table_info]

        # Check if the "cover_letter" column exists
        if "cover_letter" not in column_names:
            # If it doesn't exist, add it
            cursor.execute("ALTER TABLE jobs ADD COLUMN cover_letter TEXT")
            print("Added cover_letter column to jobs table")

        if "resume" not in column_names:
            # If it doesn't exist, add it
            cursor.execute("ALTER TABLE jobs ADD COLUMN resume TEXT")
            print("Added resume column to jobs table")

        # Check if the "source" column exists (for multi-source support)
        if "source" not in column_names:
            # If it doesn't exist, add it
            cursor.execute("ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'linkedin'")
            print("Added source column to jobs table")
        
        # Check if the "saved" column exists
        if "saved" not in column_names:
            # If it doesn't exist, add it
            cursor.execute("ALTER TABLE jobs ADD COLUMN saved INTEGER DEFAULT 0")
            conn.commit()
            print("Added saved column to jobs table")
        
        # Check if the "hidden" column exists
        if "hidden" not in column_names:
            # If it doesn't exist, add it
            cursor.execute("ALTER TABLE jobs ADD COLUMN hidden INTEGER DEFAULT 0")
            conn.commit()
            print("Added hidden column to jobs table")

        # Create applications table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                company_name TEXT NOT NULL,
                application_status TEXT DEFAULT 'Applied',
                role TEXT NOT NULL,
                salary TEXT,
                date_submitted TEXT,
                link_to_job_req TEXT,
                rejection_reason TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        conn.commit()
        print("Verified applications table exists")
        
        # Create analysis_history table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                analysis_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        conn.commit()
        print("Verified analysis_history table exists")
        
        # Create resume_cache table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resume_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                file_mtime REAL NOT NULL,
                resume_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Verified resume_cache table exists")
        
        # Create job_cache table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL UNIQUE,
                job_title_hash TEXT,
                job_company_hash TEXT,
                job_description_hash TEXT,
                job_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrate old schema if needed (add new columns if they don't exist)
        cursor.execute("PRAGMA table_info(job_cache)")
        table_info = cursor.fetchall()
        column_names = [column[1] for column in table_info]
        if "cache_key" not in column_names:
            # Add new columns for composite key
            try:
                cursor.execute("ALTER TABLE job_cache ADD COLUMN cache_key TEXT")
            except sqlite3.OperationalError:
                pass  # Column might already exist
            try:
                cursor.execute("ALTER TABLE job_cache ADD COLUMN job_title_hash TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE job_cache ADD COLUMN job_company_hash TEXT")
            except sqlite3.OperationalError:
                pass
            # Migrate existing data: set cache_key = job_description_hash for old entries
            cursor.execute("UPDATE job_cache SET cache_key = job_description_hash WHERE cache_key IS NULL")
            # Make cache_key unique (drop old unique constraint on job_description_hash if it exists)
            try:
                cursor.execute("DROP INDEX IF EXISTS idx_job_cache_desc_hash")
            except:
                pass
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_job_cache_key ON job_cache(cache_key)")
            conn.commit()
            print("Migrated job_cache table to use composite cache key")
        conn.commit()
        print("Verified job_cache table exists")
        
        # Create keyword_analysis_cache table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_analysis_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL UNIQUE,
                job_description_hash TEXT NOT NULL,
                resume_path_hash TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Verified keyword_analysis_cache table exists")
        
        # Create project_ideas table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                project_ideas_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        conn.commit()
        print("Verified project_ideas table exists")
    finally:
        close_db_connection(conn)

