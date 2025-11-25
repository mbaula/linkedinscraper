"""
Job database service layer.
"""
import sqlite3
import pandas as pd
from utils.db_utils import get_db_connection, close_db_connection
from utils.config_utils import load_config


def get_all_jobs(config_dict):
    """
    Get all jobs from the database, sorted by id descending.
    
    Args:
        config_dict (dict): Configuration dictionary
        
    Returns:
        list: List of job dictionaries
    """
    conn = get_db_connection(config_dict=config_dict)
    try:
        query = "SELECT * FROM jobs"
        df = pd.read_sql_query(query, conn)
        df = df.sort_values(by='id', ascending=False)
        df.reset_index(drop=True, inplace=True)
        jobs = df.to_dict('records')
        return jobs
    finally:
        close_db_connection(conn)


def get_job_by_id(job_id, config_dict):
    """
    Get a single job by its ID.
    
    Args:
        job_id (int): Job ID
        config_dict (dict): Configuration dictionary
        
    Returns:
        dict: Job dictionary, or None if not found
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_tuple = cursor.fetchone()
        if job_tuple is not None:
            # Get the column names from the cursor description
            column_names = [column[0] for column in cursor.description]
            # Create a dictionary mapping column names to row values
            job = dict(zip(column_names, job_tuple))
            return job
        return None
    finally:
        close_db_connection(conn)


def update_job_status(job_id, field, value, config_dict):
    """
    Update a job status field (applied, saved, interview, rejected, hidden).
    
    Args:
        job_id (int): Job ID
        field (str): Field name (applied, saved, interview, rejected, hidden)
        value: Value to set (typically 0 or 1 for boolean fields)
        config_dict (dict): Configuration dictionary
        
    Returns:
        bool: True if update was successful
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        query = f"UPDATE jobs SET {field} = ? WHERE id = ?"
        cursor.execute(query, (value, job_id))
        conn.commit()
        return True
    finally:
        close_db_connection(conn)


def update_job_field(job_id, field, value, config_dict):
    """
    Update any job field (generic updater for resume, cover_letter, etc.).
    
    Args:
        job_id (int): Job ID
        field (str): Field name
        value: Value to set
        config_dict (dict): Configuration dictionary
        
    Returns:
        bool: True if update was successful
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        query = f"UPDATE jobs SET {field} = ? WHERE id = ?"
        cursor.execute(query, (value, job_id))
        conn.commit()
        return True
    finally:
        close_db_connection(conn)


def get_job_field(job_id, field, config_dict):
    """
    Get a specific field value from a job.
    
    Args:
        job_id (int): Job ID
        field (str): Field name
        config_dict (dict): Configuration dictionary
        
    Returns:
        Value of the field, or None if not found
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT {field} FROM jobs WHERE id = ?", (job_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        close_db_connection(conn)


def get_job_details_for_application(job_id, config_dict):
    """
    Get job details needed for creating an application entry.
    
    Args:
        job_id (int): Job ID
        config_dict (dict): Configuration dictionary
        
    Returns:
        tuple: (title, company, job_url, date) or None if not found
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT title, company, job_url, date FROM jobs WHERE id = ?", (job_id,))
        return cursor.fetchone()
    finally:
        close_db_connection(conn)


def filter_jobs_by_config(jobs_list, config):
    """
    Apply config filters to jobs list (for existing jobs in database).
    
    Args:
        jobs_list (list): List of job dictionaries
        config (dict): Configuration dictionary
        
    Returns:
        list: Filtered list of job dictionaries
    """
    filtered_jobs = jobs_list.copy()
    
    # Filter by title_exclude (case insensitive)
    title_exclude = config.get('title_exclude', [])
    if title_exclude and len(title_exclude) > 0:
        title_exclude = [word.strip().lower() for word in title_exclude if word and word.strip()]
        if title_exclude:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('title') and not any(
                    exclude_word in (job.get('title', '') or '').lower() 
                    for exclude_word in title_exclude
                )
            ]
    
    # Filter by title_include (case insensitive)
    title_include = config.get('title_include', [])
    if title_include and len(title_include) > 0:
        title_include = [word.strip().lower() for word in title_include if word and word.strip()]
        if title_include:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('title') and any(
                    include_word in (job.get('title', '') or '').lower() 
                    for include_word in title_include
                )
            ]
    
    # Filter by desc_words (case insensitive)
    desc_words = config.get('desc_words', [])
    if desc_words and len(desc_words) > 0:
        desc_words = [word.strip().lower() for word in desc_words if word and word.strip()]
        if desc_words:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('job_description') and not any(
                    desc_word in (job.get('job_description', '') or '').lower() 
                    for desc_word in desc_words
                )
            ]
    
    # Filter by company_exclude (case insensitive)
    company_exclude = config.get('company_exclude', [])
    if company_exclude and len(company_exclude) > 0:
        company_exclude = [word.strip().lower() for word in company_exclude if word and word.strip()]
        if company_exclude:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('company') and not any(
                    company_word in (job.get('company', '') or '').lower() 
                    for company_word in company_exclude
                )
            ]
    
    return filtered_jobs


def read_jobs_from_db(config_path='config.json'):
    """
    Read jobs from database with filtering applied.
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        list: List of filtered job dictionaries
    """
    # Reload config to get latest filter settings
    current_config = load_config(config_path)
    
    conn = get_db_connection(config_dict=current_config)
    try:
        query = "SELECT * FROM jobs WHERE hidden = 0"
        df = pd.read_sql_query(query, conn)
        df = df.sort_values(by='id', ascending=False)
        jobs = df.to_dict('records')
        
        # Apply current config filters to existing jobs
        jobs = filter_jobs_by_config(jobs, current_config)
        
        return jobs
    finally:
        close_db_connection(conn)

