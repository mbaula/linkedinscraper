import json
import sqlite3
import sys
import io
from sqlite3 import Error
import time as tm
from itertools import groupby
from datetime import datetime, timedelta, time
import pandas as pd
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from scrapers.linkedin_scraper import LinkedInScraper

# Set UTF-8 encoding for stdout on Windows to handle Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except AttributeError:
        # If stdout.buffer doesn't exist, fall back to safe_print
        pass


def load_config(file_name):
    # Load the config file
    with open(file_name, 'r', encoding='utf-8') as f:
        return json.load(f)

# LinkedIn-specific functions moved to scrapers/linkedin_scraper.py
# Using modular scraper structure

def safe_detect(text):
    try:
        return detect(text)
    except LangDetectException:
        return 'en'

def safe_print(text, end='\n', flush=False):
    """Safely print text, handling Unicode encoding errors on Windows."""
    try:
        print(text, end=end, flush=flush)
    except UnicodeEncodeError:
        # Replace problematic characters with safe alternatives
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text, end=end, flush=flush)

def remove_irrelevant_jobs(joblist, config):
    #Filter out jobs based on description, title, and language. Set up in config.json.
    new_joblist = [job for job in joblist if not any(word.lower() in job['job_description'].lower() for word in config['desc_words'])]   
    new_joblist = [job for job in new_joblist if not any(word.lower() in job['title'].lower() for word in config['title_exclude'])] if len(config['title_exclude']) > 0 else new_joblist
    new_joblist = [job for job in new_joblist if any(word.lower() in job['title'].lower() for word in config['title_include'])] if len(config['title_include']) > 0 else new_joblist
    new_joblist = [job for job in new_joblist if safe_detect(job['job_description']) in config['languages']] if len(config['languages']) > 0 else new_joblist
    new_joblist = [job for job in new_joblist if not any(word.lower() in job['company'].lower() for word in config['company_exclude'])] if len(config['company_exclude']) > 0 else new_joblist

    return new_joblist

def remove_duplicates(joblist, config):
    # Remove duplicate jobs in the joblist. Duplicate is defined as having the same title and company.
    joblist.sort(key=lambda x: (x['title'], x['company']))
    joblist = [next(g) for k, g in groupby(joblist, key=lambda x: (x['title'], x['company']))]
    return joblist

def convert_date_format(date_string):
    """
    Converts a date string to a date object. 
    
    Args:
        date_string (str): The date in string format.

    Returns:
        date: The converted date object, or None if conversion failed.
    """
    date_format = "%Y-%m-%d"
    try:
        job_date = datetime.strptime(date_string, date_format).date()
        return job_date
    except ValueError:
        print(f"Error: The date for job {date_string} - is not in the correct format.")
        return None

def create_connection(config):
    # Create a database connection to a SQLite database
    conn = None
    path = config['db_path']
    try:
        conn = sqlite3.connect(path) # creates a SQL database in the 'data' directory
        #print(sqlite3.version)
    except Error as e:
        print(e)

    return conn

def create_table(conn, df, table_name):
    ''''
    # Create a new table with the data from the dataframe
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    print (f"Created the {table_name} table and added {len(df)} records")
    '''
    # Create a new table with the data from the DataFrame
    # Prepare data types mapping from pandas to SQLite
    type_mapping = {
        'int64': 'INTEGER',
        'float64': 'REAL',
        'datetime64[ns]': 'TIMESTAMP',
        'object': 'TEXT',
        'bool': 'INTEGER'
    }
    
    # Prepare a string with column names and their types
    columns_with_types = ', '.join(
        f'"{column}" {type_mapping[str(df.dtypes[column])]}'
        for column in df.columns
    )
    
    # Prepare SQL query to create a new table
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {columns_with_types}
        );
    """
    
    # Execute SQL query
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    
    # Commit the transaction
    conn.commit()

    # Insert DataFrame records one by one
    insert_sql = f"""
        INSERT INTO "{table_name}" ({', '.join(f'"{column}"' for column in df.columns)})
        VALUES ({', '.join(['?' for _ in df.columns])})
    """
    for record in df.to_dict(orient='records'):
        cursor.execute(insert_sql, list(record.values()))
    
    # Commit the transaction
    conn.commit()

    print(f"Created the {table_name} table and added {len(df)} records")

def update_table(conn, df, table_name):
    # Update the existing table with new records.
    df_existing = pd.read_sql(f'select * from {table_name}', conn)

    # Create a dataframe with unique records in df that are not in df_existing
    df_new_records = pd.concat([df, df_existing, df_existing]).drop_duplicates(['title', 'company', 'date'], keep=False)

    # If there are new records, append them to the existing table
    if len(df_new_records) > 0:
        df_new_records.to_sql(table_name, conn, if_exists='append', index=False)
        print (f"Added {len(df_new_records)} new records to the {table_name} table")
    else:
        print (f"No new records to add to the {table_name} table")

def table_exists(conn, table_name):
    # Check if the table already exists in the database
    cur = conn.cursor()
    cur.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    if cur.fetchone()[0]==1 :
        return True
    return False

def job_exists(df, job):
    # Check if the job already exists in the dataframe
    if df.empty:
        return False
    #return ((df['title'] == job['title']) & (df['company'] == job['company']) & (df['date'] == job['date'])).any()
    #The job exists if there's already a job in the database that has the same URL
    return ((df['job_url'] == job['job_url']).any() | (((df['title'] == job['title']) & (df['company'] == job['company']) & (df['date'] == job['date'])).any()))

def get_jobcards(config):
    """
    Get job cards using the modular scraper system.
    Currently uses LinkedIn scraper, but can be extended to support multiple sources.
    """
    # Initialize LinkedIn scraper
    linkedin_scraper = LinkedInScraper(config)
    
    # Get job cards from LinkedIn
    all_jobs = linkedin_scraper.get_job_cards()
    
    # Normalize jobs (add source field, ensure consistent format)
    all_jobs = [linkedin_scraper.normalize_job(job) for job in all_jobs]
    
    # Remove duplicates
    all_jobs = remove_duplicates(all_jobs, config)
    print(f"Total job cards after removing duplicates: {len(all_jobs)}", flush=True)
    
    # Remove irrelevant jobs based on filters
    all_jobs = remove_irrelevant_jobs(all_jobs, config)
    print(f"Total job cards after removing irrelevant jobs: {len(all_jobs)}", flush=True)
    
    return all_jobs

def find_new_jobs(all_jobs, conn, config):
    # From all_jobs, find the jobs that are not already in the database. Function checks both the jobs and filtered_jobs tables.
    jobs_tablename = config['jobs_tablename']
    filtered_jobs_tablename = config['filtered_jobs_tablename']
    jobs_db = pd.DataFrame()
    filtered_jobs_db = pd.DataFrame()    
    if conn is not None:
        if table_exists(conn, jobs_tablename):
            query = f"SELECT * FROM {jobs_tablename}"
            jobs_db = pd.read_sql_query(query, conn)
        if table_exists(conn, filtered_jobs_tablename):
            query = f"SELECT * FROM {filtered_jobs_tablename}"
            filtered_jobs_db = pd.read_sql_query(query, conn)

    new_joblist = [job for job in all_jobs if not job_exists(jobs_db, job) and not job_exists(filtered_jobs_db, job)]
    return new_joblist

def verify_jobs_table_schema(conn, table_name):
    """Ensure the jobs table has the source column for multi-source support."""
    if conn is None:
        return
    
    cursor = conn.cursor()
    try:
        # Check if table exists
        cursor.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone()[0] == 1:
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add source column if it doesn't exist
            if 'source' not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN source TEXT DEFAULT 'linkedin'")
                conn.commit()
                print(f"Added source column to {table_name} table")
    except Exception as e:
        print(f"Error verifying table schema: {e}")

def hide_old_unapplied_jobs(conn, config):
    """
    Hide jobs that haven't been applied to within the specified number of days.
    Jobs are hidden (hidden = 1) instead of deleted so they can be recovered.
    
    Args:
        conn: Database connection
        config: Configuration dictionary
        
    Returns:
        int: Number of jobs hidden
    """
    if conn is None:
        return 0
    
    days_threshold = config.get('delete_unapplied_jobs_after_days', 0)
    
    # If set to 0 or not set, don't hide anything
    if days_threshold <= 0:
        return 0
    
    try:
        cursor = conn.cursor()
        jobs_tablename = config.get('jobs_tablename', 'jobs')
        
        # Check if date_loaded column exists
        cursor.execute(f"PRAGMA table_info({jobs_tablename})")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'date_loaded' not in columns:
            print(f"  [WARNING] date_loaded column not found in {jobs_tablename} table. Skipping cleanup.", flush=True)
            return 0
        
        # Calculate the cutoff date (as datetime object for comparison)
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # Get all unapplied and unsaved jobs with date_loaded that are not already hidden
        # Check if saved column exists
        cursor.execute(f"PRAGMA table_info({jobs_tablename})")
        columns = [column[1] for column in cursor.fetchall()]
        has_saved_column = 'saved' in columns
        
        if has_saved_column:
            cursor.execute(f"""
                SELECT id, date_loaded FROM {jobs_tablename}
                WHERE applied = 0 
                AND saved = 0
                AND (hidden = 0 OR hidden IS NULL)
                AND date_loaded IS NOT NULL
                AND date_loaded != ''
            """)
        else:
            cursor.execute(f"""
                SELECT id, date_loaded FROM {jobs_tablename}
                WHERE applied = 0 
                AND (hidden = 0 OR hidden IS NULL)
                AND date_loaded IS NOT NULL
                AND date_loaded != ''
            """)
        
        jobs_to_hide = []
        for row in cursor.fetchall():
            job_id, date_loaded_str = row
            try:
                # Try to parse the date_loaded string
                # It might be in different formats, so try a few common ones
                date_loaded = None
                for date_format in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"]:
                    try:
                        date_loaded = datetime.strptime(date_loaded_str, date_format)
                        break
                    except ValueError:
                        continue
                
                # If we couldn't parse it, skip this job
                if date_loaded is None:
                    continue
                
                # Check if the job is older than the threshold
                if date_loaded < cutoff_date:
                    jobs_to_hide.append(job_id)
            except Exception as e:
                # Skip jobs with invalid date formats
                continue
        
        if jobs_to_hide:
            # Hide the jobs instead of deleting them
            placeholders = ','.join(['?' for _ in jobs_to_hide])
            cursor.execute(f"""
                UPDATE {jobs_tablename}
                SET hidden = 1
                WHERE id IN ({placeholders})
            """, jobs_to_hide)
            
            conn.commit()
            print(f"  [OK] Hidden {len(jobs_to_hide)} unapplied job(s) older than {days_threshold} days", flush=True)
            return len(jobs_to_hide)
        else:
            print(f"  [OK] No unapplied jobs older than {days_threshold} days to hide", flush=True)
            return 0
            
    except Exception as e:
        print(f"  [ERROR] Error hiding old unapplied jobs: {e}", flush=True)
        return 0

def main(config_file):
    start_time = tm.perf_counter()
    job_list = []

    print("=" * 80, flush=True)
    print("JOB SEARCH STARTED", flush=True)
    print("=" * 80, flush=True)
    
    print(f"\n[STEP 1/7] Loading configuration from {config_file}...", flush=True)
    config = load_config(config_file)
    print(f"[OK] Configuration loaded successfully", flush=True)
    print(f"  - Pages to scrape: {config.get('pages_to_scrape', 10)}", flush=True)
    print(f"  - Rounds: {config.get('rounds', 1)}", flush=True)
    print(f"  - Search queries: {len(config.get('search_queries', []))}", flush=True)
    print(f"  - Days to scrape: {config.get('days_to_scrape', 10)}", flush=True)
    
    jobs_tablename = config['jobs_tablename'] # name of the table to store the "approved" jobs
    filtered_jobs_tablename = config['filtered_jobs_tablename'] # name of the table to store the jobs that have been filtered out based on description keywords (so that in future they are not scraped again)
    
    print(f"\n[STEP 2/7] Initializing LinkedIn scraper...", flush=True)
    # Initialize scraper (for now LinkedIn, but will support multiple sources later)
    linkedin_scraper = LinkedInScraper(config)
    print(f"[OK] LinkedIn scraper initialized", flush=True)
    
    print(f"\n[STEP 3/7] Scraping job cards from search results...", flush=True)
    print(f"  This step may take a while based on the number of pages and search queries.", flush=True)
    #Scrape search results page and get job cards. This step might take a while based on the number of pages and search queries.
    try:
        all_jobs = get_jobcards(config)
        print(f"[OK] Job card scraping completed", flush=True)
    except Exception as e:
        safe_print(f"[ERROR] Failed to scrape job cards: {str(e)}", flush=True)
        safe_print(f"[ERROR] Search cannot continue without job cards. Exiting.", flush=True)
        return
    
    print(f"\n[STEP 4/7] Connecting to database...", flush=True)
    conn = create_connection(config)
    if conn:
        print(f"[OK] Database connection established: {config['db_path']}", flush=True)
    else:
        print(f"[ERROR] Failed to connect to database", flush=True)
        return
    
    # Verify schema has source column
    print(f"\n[STEP 5/7] Verifying database schema...", flush=True)
    verify_jobs_table_schema(conn, jobs_tablename)
    verify_jobs_table_schema(conn, filtered_jobs_tablename)
    print(f"[OK] Database schema verified", flush=True)
    
    #filtering out jobs that are already in the database
    print(f"\n[STEP 6/7] Filtering out jobs that already exist in database...", flush=True)
    all_jobs = find_new_jobs(all_jobs, conn, config)
    print(f"[OK] Filtering completed", flush=True)
    print(f"  - Total new jobs found after comparing to the database: {len(all_jobs)}", flush=True)

    if len(all_jobs) > 0:
        print(f"\n[STEP 7/7] Processing {len(all_jobs)} new jobs...", flush=True)
        print(f"  - Fetching job descriptions and applying filters...", flush=True)
        
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, job in enumerate(all_jobs, 1):
            try:
                # Skip jobs with invalid dates
                if not job.get('date'):
                    skipped_count += 1
                    continue
                    
                job_date = convert_date_format(job['date'])
                if not job_date:
                    skipped_count += 1
                    continue
                    
                job_date = datetime.combine(job_date, time())
                #if job is older than a week, skip it
                if job_date < datetime.now() - timedelta(days=config['days_to_scrape']):
                    skipped_count += 1
                    continue
                
                safe_print(f"  [{idx}/{len(all_jobs)}] Processing: {job['title']} at {job['company']}", flush=True)
                safe_print(f"      URL: {job['job_url']}", flush=True)
                
                # Get job description using the scraper
                safe_print(f"      -> Fetching job description...", flush=True)
                try:
                    job['job_description'] = linkedin_scraper.get_job_description(job['job_url'])
                except Exception as e:
                    safe_print(f"      [ERROR] Failed to fetch job description: {str(e)}", flush=True)
                    error_count += 1
                    continue
                
                # Validate job description was fetched
                if not job.get('job_description') or job['job_description'] == "Could not fetch job description":
                    safe_print(f"      [WARNING] Job description not available, skipping...", flush=True)
                    skipped_count += 1
                    continue
                
                try:
                    language = safe_detect(job['job_description'])
                    if language not in config['languages']:
                        safe_print(f"      [WARNING] Job description language not supported: {language}", flush=True)
                        #continue
                except Exception as e:
                    safe_print(f"      [WARNING] Could not detect language: {str(e)}", flush=True)
                    # Continue anyway, language detection is not critical
                
                job_list.append(job)
                processed_count += 1
                
            except Exception as e:
                # Catch any other unexpected errors and continue with next job
                safe_print(f"  [{idx}/{len(all_jobs)}] [ERROR] Failed to process job: {str(e)}", flush=True)
                safe_print(f"      URL: {job.get('job_url', 'Unknown')}", flush=True)
                error_count += 1
                continue
        
        print(f"\n  [OK] Job processing completed", flush=True)
        print(f"    - Processed: {processed_count}", flush=True)
        print(f"    - Skipped: {skipped_count}", flush=True)
        if error_count > 0:
            print(f"    - Errors: {error_count}", flush=True)
        
        #Final check - removing jobs based on job description keywords words from the config file
        print(f"\n  -> Applying final filters based on job description keywords...", flush=True)
        try:
            jobs_to_add = remove_irrelevant_jobs(job_list, config)
            print(f"  [OK] Final filtering completed", flush=True)
            print(f"    - Total jobs to add to database: {len(jobs_to_add)}", flush=True)
            print(f"    - Jobs filtered out: {len(job_list) - len(jobs_to_add)}", flush=True)
        except Exception as e:
            safe_print(f"  [ERROR] Failed to apply final filters: {str(e)}", flush=True)
            safe_print(f"  [WARNING] Continuing with all processed jobs...", flush=True)
            jobs_to_add = job_list
        
        #Create a list for jobs removed based on job description keywords - they will be added to the filtered_jobs table
        try:
            filtered_list = [job for job in job_list if job not in jobs_to_add]
            df = pd.DataFrame(jobs_to_add)
            df_filtered = pd.DataFrame(filtered_list)
            df['date_loaded'] = datetime.now()
            df_filtered['date_loaded'] = datetime.now()
            df['date_loaded'] = df['date_loaded'].astype(str)
            df_filtered['date_loaded'] = df_filtered['date_loaded'].astype(str)
        except Exception as e:
            safe_print(f"  [ERROR] Failed to create dataframes: {str(e)}", flush=True)
            safe_print(f"  [WARNING] Skipping database and CSV export...", flush=True)
            df = None
            df_filtered = None
        
        if df is not None and conn is not None:
            print(f"\n  -> Saving jobs to database...", flush=True)
            try:
                #Update or Create the database table for the job list
                if table_exists(conn, jobs_tablename):
                    update_table(conn, df, jobs_tablename)
                else:
                    create_table(conn, df, jobs_tablename)
                    
                #Update or Create the database table for the filtered out jobs
                if table_exists(conn, filtered_jobs_tablename):
                    update_table(conn, df_filtered, filtered_jobs_tablename)
                else:
                    create_table(conn, df_filtered, filtered_jobs_tablename)
                print(f"  [OK] Database updated successfully", flush=True)
            except Exception as e:
                safe_print(f"  [ERROR] Failed to save jobs to database: {str(e)}", flush=True)
                safe_print(f"  [WARNING] Continuing with CSV export...", flush=True)
        elif conn is None:
            print("  [WARNING] Database connection not available, skipping database save.", flush=True)
        
        if df is not None:
            print(f"\n  -> Exporting to CSV files...", flush=True)
            try:
                df.to_csv('linkedin_jobs.csv', index=False, encoding='utf-8')
                df_filtered.to_csv('linkedin_jobs_filtered.csv', index=False, encoding='utf-8')
                print(f"  [OK] CSV files exported", flush=True)
            except Exception as e:
                safe_print(f"  [ERROR] Failed to export CSV files: {str(e)}", flush=True)
                safe_print(f"  [WARNING] Jobs were processed but not exported to CSV.", flush=True)
    else:
        print(f"\n[STEP 7/7] No new jobs found to process", flush=True)
    
    # Cleanup old unapplied jobs if configured (hide instead of delete)
    delete_days = config.get('delete_unapplied_jobs_after_days', 0)
    if delete_days > 0 and conn is not None:
        print(f"\n[CLEANUP] Hiding unapplied jobs older than {delete_days} days...", flush=True)
        hidden_count = hide_old_unapplied_jobs(conn, config)
        if hidden_count > 0:
            print(f"  -> Hidden {hidden_count} old unapplied job(s) (can be viewed via filter)", flush=True)
    
    end_time = tm.perf_counter()
    print("\n" + "=" * 80, flush=True)
    print(f"JOB SEARCH COMPLETED", flush=True)
    print(f"Total time: {end_time - start_time:.2f} seconds", flush=True)
    print("=" * 80, flush=True)


if __name__ == "__main__":
    config_file = 'config.json'  # default config file
    if len(sys.argv) == 2:
        config_file = sys.argv[1]
        
    main(config_file)