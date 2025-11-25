"""
Application database service layer.
"""
import csv
import io
from datetime import datetime
from flask import Response
from utils.db_utils import get_db_connection, close_db_connection
from services.job_service import update_job_status


def get_all_applications(config_dict):
    """
    Get all applications from the database.
    
    Args:
        config_dict (dict): Configuration dictionary
        
    Returns:
        list: List of application dictionaries
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, job_id, company_name, application_status, role, salary, 
                   date_submitted, link_to_job_req, rejection_reason, notes
            FROM applications
            ORDER BY date_submitted DESC, id DESC
        """)
        
        columns = [description[0] for description in cursor.description]
        applications = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return applications
    finally:
        close_db_connection(conn)


def create_application(data, config_dict):
    """
    Create a new application entry.
    
    Args:
        data (dict): Application data dictionary
        config_dict (dict): Configuration dictionary
        
    Returns:
        int: ID of the newly created application
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO applications (job_id, company_name, application_status, role, salary, 
                                     date_submitted, link_to_job_req, rejection_reason, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('job_id'),
            data.get('company_name', ''),
            data.get('application_status', 'Applied'),
            data.get('role', ''),
            data.get('salary', ''),
            data.get('date_submitted', ''),
            data.get('link_to_job_req', ''),
            data.get('rejection_reason', ''),
            data.get('notes', '')
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        close_db_connection(conn)


def update_application(app_id, data, config_dict):
    """
    Update an existing application.
    
    Args:
        app_id (int): Application ID
        data (dict): Updated application data
        config_dict (dict): Configuration dictionary
        
    Returns:
        bool: True if update was successful
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE applications 
            SET company_name = ?, application_status = ?, role = ?, salary = ?,
                date_submitted = ?, link_to_job_req = ?, rejection_reason = ?, 
                notes = ?, updated_at = ?
            WHERE id = ?
        """, (
            data.get('company_name', ''),
            data.get('application_status', 'Applied'),
            data.get('role', ''),
            data.get('salary', ''),
            data.get('date_submitted', ''),
            data.get('link_to_job_req', ''),
            data.get('rejection_reason', ''),
            data.get('notes', ''),
            datetime.now().isoformat(),
            app_id
        ))
        conn.commit()
        return True
    finally:
        close_db_connection(conn)


def delete_application(app_id, config_dict):
    """
    Delete an application and unmark the associated job as applied.
    
    Args:
        app_id (int): Application ID
        config_dict (dict): Configuration dictionary
        
    Returns:
        int or None: Job ID that was unmarked, or None
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        # Get the job_id before deleting
        cursor.execute("SELECT job_id FROM applications WHERE id = ?", (app_id,))
        result = cursor.fetchone()
        job_id = result[0] if result else None
        
        # Delete the application
        cursor.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        
        # Unmark the job as applied if it has a job_id
        if job_id:
            cursor.execute("UPDATE jobs SET applied = 0 WHERE id = ?", (job_id,))
        
        conn.commit()
        return job_id
    finally:
        close_db_connection(conn)


def check_application_exists(job_id, config_dict):
    """
    Check if an application already exists for a job.
    
    Args:
        job_id (int): Job ID
        config_dict (dict): Configuration dictionary
        
    Returns:
        bool: True if application exists
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
        return cursor.fetchone() is not None
    finally:
        close_db_connection(conn)


def export_applications_csv(config_dict):
    """
    Export all applications to CSV format.
    
    Args:
        config_dict (dict): Configuration dictionary
        
    Returns:
        Response: Flask Response object with CSV data
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT company_name, application_status, role, salary, 
                   date_submitted, link_to_job_req, rejection_reason, notes
            FROM applications
            ORDER BY date_submitted DESC, id DESC
        """)
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Company Name', 'Application Status', 'Role', 'Salary',
            'Date Submitted', 'Link to Job Req', 'Rejection Reason', 'Notes'
        ])
        
        # Write data
        for row in cursor.fetchall():
            writer.writerow(row)
        
        # Create response with CSV data
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=applications_export.csv'
            }
        )
    finally:
        close_db_connection(conn)

