"""
Database schema service layer.
"""
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
                job_description_hash TEXT NOT NULL UNIQUE,
                job_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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
    finally:
        close_db_connection(conn)

