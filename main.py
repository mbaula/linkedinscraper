import json
import sqlite3
import sys
from sqlite3 import Error
import time as tm
from itertools import groupby
from datetime import datetime, timedelta, time
import pandas as pd
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from scrapers.linkedin_scraper import LinkedInScraper


def load_config(file_name):
    # Load the config file
    with open(file_name) as f:
        return json.load(f)

# LinkedIn-specific functions moved to scrapers/linkedin_scraper.py
# Using modular scraper structure

def safe_detect(text):
    try:
        return detect(text)
    except LangDetectException:
        return 'en'

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
    print(f"Total job cards after removing duplicates: {len(all_jobs)}")
    
    # Remove irrelevant jobs based on filters
    all_jobs = remove_irrelevant_jobs(all_jobs, config)
    print(f"Total job cards after removing irrelevant jobs: {len(all_jobs)}")
    
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

def main(config_file):
    start_time = tm.perf_counter()
    job_list = []

    config = load_config(config_file)
    jobs_tablename = config['jobs_tablename'] # name of the table to store the "approved" jobs
    filtered_jobs_tablename = config['filtered_jobs_tablename'] # name of the table to store the jobs that have been filtered out based on description keywords (so that in future they are not scraped again)
    
    # Initialize scraper (for now LinkedIn, but will support multiple sources later)
    linkedin_scraper = LinkedInScraper(config)
    
    #Scrape search results page and get job cards. This step might take a while based on the number of pages and search queries.
    all_jobs = get_jobcards(config)
    conn = create_connection(config)
    
    # Verify schema has source column
    verify_jobs_table_schema(conn, jobs_tablename)
    verify_jobs_table_schema(conn, filtered_jobs_tablename)
    
    #filtering out jobs that are already in the database
    all_jobs = find_new_jobs(all_jobs, conn, config)
    print ("Total new jobs found after comparing to the database: ", len(all_jobs))

    if len(all_jobs) > 0:

        for job in all_jobs:
            # Skip jobs with invalid dates
            if not job.get('date'):
                continue
                
            job_date = convert_date_format(job['date'])
            if not job_date:
                continue
                
            job_date = datetime.combine(job_date, time())
            #if job is older than a week, skip it
            if job_date < datetime.now() - timedelta(days=config['days_to_scrape']):
                continue
            print('Found new job: ', job['title'], 'at ', job['company'], job['job_url'])
            
            # Get job description using the scraper
            job['job_description'] = linkedin_scraper.get_job_description(job['job_url'])
            language = safe_detect(job['job_description'])
            if language not in config['languages']:
                print('Job description language not supported: ', language)
                #continue
            job_list.append(job)
        #Final check - removing jobs based on job description keywords words from the config file
        jobs_to_add = remove_irrelevant_jobs(job_list, config)
        print ("Total jobs to add: ", len(jobs_to_add))
        #Create a list for jobs removed based on job description keywords - they will be added to the filtered_jobs table
        filtered_list = [job for job in job_list if job not in jobs_to_add]
        df = pd.DataFrame(jobs_to_add)
        df_filtered = pd.DataFrame(filtered_list)
        df['date_loaded'] = datetime.now()
        df_filtered['date_loaded'] = datetime.now()
        df['date_loaded'] = df['date_loaded'].astype(str)
        df_filtered['date_loaded'] = df_filtered['date_loaded'].astype(str)        
        
        if conn is not None:
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
        else:
            print("Error! cannot create the database connection.")
        
        df.to_csv('linkedin_jobs.csv', index=False, encoding='utf-8')
        df_filtered.to_csv('linkedin_jobs_filtered.csv', index=False, encoding='utf-8')
    else:
        print("No jobs found")
    
    end_time = tm.perf_counter()
    print(f"Scraping finished in {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    config_file = 'config.json'  # default config file
    if len(sys.argv) == 2:
        config_file = sys.argv[1]
        
    main(config_file)