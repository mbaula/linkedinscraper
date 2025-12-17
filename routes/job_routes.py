"""
Job-related routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request, current_app, Response
from services.job_service import (
    get_all_jobs as get_all_jobs_service,
    get_job_by_id,
    update_job_status,
    read_jobs_from_db,
    delete_jobs_older_than_date
)
import csv
import io
from datetime import datetime

# Create blueprint
job_bp = Blueprint('job', __name__)


@job_bp.route('/')
def home():
    """Home page - displays list of jobs"""
    # Check if user wants to see hidden jobs (from query parameter or default to False)
    include_hidden = request.args.get('include_hidden', 'false').lower() == 'true'
    jobs = read_jobs_from_db(include_hidden=include_hidden)
    return render_template('jobs.html', jobs=jobs, include_hidden=include_hidden)


@job_bp.route('/job/<int:job_id>')
def job(job_id):
    """Display individual job details page"""
    # Include hidden jobs when viewing a specific job
    jobs = read_jobs_from_db(include_hidden=True)
    # Find job by ID in the filtered list
    job = next((j for j in jobs if j.get('id') == job_id), None)
    if job:
        return render_template('./templates/job_description.html', job=job)
    else:
        return render_template('./templates/job_description.html', job=None)


@job_bp.route('/get_all_jobs')
def get_all_jobs():
    """Get all jobs as JSON"""
    config = current_app.config['CONFIG']
    # Check if user wants to see hidden jobs
    include_hidden = request.args.get('include_hidden', 'false').lower() == 'true'
    if include_hidden:
        jobs = read_jobs_from_db(include_hidden=include_hidden)
    else:
        jobs = get_all_jobs_service(config)
    return jsonify(jobs)


@job_bp.route('/job_details/<int:job_id>')
def job_details(job_id):
    """Get job details by ID"""
    config = current_app.config['CONFIG']
    job = get_job_by_id(job_id, config)
    if job:
        return jsonify(job)
    else:
        return jsonify({"error": "Job not found"}), 404


@job_bp.route('/hide_job/<int:job_id>', methods=['POST'])
def hide_job(job_id):
    """Hide a job"""
    config = current_app.config['CONFIG']
    update_job_status(job_id, 'hidden', 1, config)
    return jsonify({"success": "Job marked as hidden"}), 200


@job_bp.route('/unhide_job/<int:job_id>', methods=['POST'])
def unhide_job(job_id):
    """Unhide a job"""
    config = current_app.config['CONFIG']
    update_job_status(job_id, 'hidden', 0, config)
    return jsonify({"success": "Job unhidden"}), 200


@job_bp.route('/mark_applied/<int:job_id>', methods=['POST'])
def mark_applied(job_id):
    """Mark a job as applied and create application entry"""
    from datetime import datetime
    from services.application_service import (
        create_application as create_application_service,
        check_application_exists
    )
    from services.job_service import get_job_details_for_application
    
    config = current_app.config['CONFIG']
    print("Applied clicked!")
    
    # Update jobs table
    print(f'Updating job_id: {job_id} to applied')
    update_job_status(job_id, 'applied', 1, config)
    
    # Get job details to auto-populate application
    job = get_job_details_for_application(job_id, config)
    
    if job:
        title, company, job_url, job_date = job
        
        # Check if application already exists for this job
        if not check_application_exists(job_id, config):
            # Create new application entry
            date_submitted = datetime.now().strftime("%Y-%m-%d")
            create_application_service({
                'job_id': job_id,
                'company_name': company,
                'application_status': 'Applied',
                'role': title,
                'date_submitted': date_submitted,
                'link_to_job_req': job_url
            }, config)
            print(f"Created application entry for job_id: {job_id}")
    
    return jsonify({"success": "Job marked as applied"}), 200


@job_bp.route('/unmark_applied/<int:job_id>', methods=['POST'])
def unmark_applied(job_id):
    """Unmark a job as applied"""
    config = current_app.config['CONFIG']
    update_job_status(job_id, 'applied', 0, config)
    return jsonify({"success": "Job unmarked as applied"}), 200


@job_bp.route('/mark_saved/<int:job_id>', methods=['POST'])
def mark_saved(job_id):
    """Mark a job as saved"""
    config = current_app.config['CONFIG']
    print("Saved clicked!")
    print(f'Updating job_id: {job_id} to saved')
    update_job_status(job_id, 'saved', 1, config)
    return jsonify({"success": "Job marked as saved"}), 200


@job_bp.route('/unmark_saved/<int:job_id>', methods=['POST'])
def unmark_saved(job_id):
    """Unmark a job as saved"""
    config = current_app.config['CONFIG']
    print("Unsave clicked!")
    print(f'Updating job_id: {job_id} to unsaved')
    update_job_status(job_id, 'saved', 0, config)
    return jsonify({"success": "Job unmarked as saved"}), 200


@job_bp.route('/mark_interview/<int:job_id>', methods=['POST'])
def mark_interview(job_id):
    """Mark a job as interview"""
    config = current_app.config['CONFIG']
    print("Interview clicked!")
    print(f'Updating job_id: {job_id} to interview')
    update_job_status(job_id, 'interview', 1, config)
    return jsonify({"success": "Job marked as interview"}), 200


@job_bp.route('/mark_rejected/<int:job_id>', methods=['POST'])
def mark_rejected(job_id):
    """Mark a job as rejected"""
    config = current_app.config['CONFIG']
    print("Rejected clicked!")
    print(f'Updating job_id: {job_id} to rejected')
    update_job_status(job_id, 'rejected', 1, config)
    return jsonify({"success": "Job marked as rejected"}), 200


@job_bp.route('/unmark_rejected/<int:job_id>', methods=['POST'])
def unmark_rejected(job_id):
    """Unmark a job as rejected"""
    config = current_app.config['CONFIG']
    print("Unmark rejected clicked!")
    print(f'Updating job_id: {job_id} to unmark rejected')
    update_job_status(job_id, 'rejected', 0, config)
    return jsonify({"success": "Job unmarked as rejected"}), 200


@job_bp.route('/unmark_interview/<int:job_id>', methods=['POST'])
def unmark_interview(job_id):
    """Unmark a job as interview"""
    config = current_app.config['CONFIG']
    print("Unmark interview clicked!")
    print(f'Updating job_id: {job_id} to unmark interview')
    update_job_status(job_id, 'interview', 0, config)
    return jsonify({"success": "Job unmarked as interview"}), 200


@job_bp.route('/projects/<int:job_id>')
def view_projects(job_id):
    """Display project ideas for a job"""
    import sqlite3
    config = current_app.config['CONFIG']
    
    # Get job details
    job = get_job_by_id(job_id, config)
    if not job:
        return "Job not found", 404
    
    # Get project ideas from database
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT project_ideas_text, created_at, updated_at FROM project_ideas WHERE job_id = ?", (job_id,))
    result = cursor.fetchone()
    conn.close()
    
    project_ideas = None
    created_at = None
    updated_at = None
    
    if result:
        project_ideas = result[0]
        created_at = result[1]
        updated_at = result[2]
    
    return render_template('projects.html', job=job, project_ideas=project_ideas, created_at=created_at, updated_at=updated_at)


@job_bp.route('/projects/history')
def projects_history():
    """Display all project ideas history"""
    import sqlite3
    config = current_app.config['CONFIG']
    
    # Get all project ideas with job information
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            pi.id,
            pi.job_id,
            pi.project_ideas_text,
            pi.created_at,
            pi.updated_at,
            j.title,
            j.company,
            j.location,
            j.job_description
        FROM project_ideas pi
        LEFT JOIN jobs j ON pi.job_id = j.id
        ORDER BY pi.created_at DESC
    """)
    results = cursor.fetchall()
    conn.close()
    
    # Format the results
    projects = []
    for row in results:
        projects.append({
            'id': row[0],
            'job_id': row[1],
            'project_ideas_text': row[2],
            'created_at': row[3],
            'updated_at': row[4],
            'job_title': row[5] or 'Unknown',
            'company': row[6] or 'Unknown',
            'location': row[7] or '',
            'job_description': row[8] or ''
        })
    
    return render_template('projects_history.html', projects=projects)


@job_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project idea entry"""
    import sqlite3
    config = current_app.config['CONFIG']
    try:
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_ideas WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Project idea deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@job_bp.route('/delete_old_jobs')
def delete_old_jobs_page():
    """Display the delete old jobs page"""
    return render_template('delete_old_jobs.html')


@job_bp.route('/api/jobs/delete_older_than', methods=['POST'])
def delete_jobs_older_than():
    """Delete jobs older than the specified date from the database"""
    config = current_app.config['CONFIG']
    
    try:
        data = request.get_json()
        cutoff_date = data.get('cutoff_date')
        
        if not cutoff_date:
            return jsonify({"error": "cutoff_date is required"}), 400
        
        deleted_count, error = delete_jobs_older_than_date(cutoff_date, config)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "success": True,
            "message": f"Permanently deleted {deleted_count} job(s) older than {cutoff_date} from the database",
            "deleted_count": deleted_count
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def apply_ui_filters(jobs, filters):
    """
    Apply UI filters to jobs list (matching frontend filter logic).
    
    Args:
        jobs (list): List of job dictionaries
        filters (dict): Filter parameters from UI
        
    Returns:
        list: Filtered list of job dictionaries
    """
    filtered_jobs = jobs.copy()
    
    # Search filter
    search_term = filters.get('search', '').strip().lower()
    if search_term:
        filtered_jobs = [
            job for job in filtered_jobs
            if search_term in (job.get('title', '') or '').lower() or
               search_term in (job.get('company', '') or '').lower() or
               search_term in (job.get('location', '') or '').lower()
        ]
    
    # City filter
    cities = filters.get('cities', [])
    if cities:
        cities_lower = [c.lower() for c in cities]
        filtered_jobs = [
            job for job in filtered_jobs
            if (job.get('location') or '').lower() in cities_lower
        ]
    
    # Title filter
    titles = filters.get('titles', [])
    if titles:
        titles_lower = [t.lower() for t in titles]
        filtered_jobs = [
            job for job in filtered_jobs
            if (job.get('title') or '').lower() in titles_lower
        ]
    
    # Company filter
    companies = filters.get('companies', [])
    if companies:
        companies_lower = [c.lower() for c in companies]
        filtered_jobs = [
            job for job in filtered_jobs
            if (job.get('company') or '').lower() in companies_lower
        ]
    
    # Country filter (extract country from location - matching frontend logic)
    countries = filters.get('countries', [])
    if countries:
        countries_lower = [c.lower() for c in countries]
        
        def extract_country(location):
            """Extract country from location string (matching frontend extractCountry function)"""
            if not location:
                return ''
            
            location_lower = location.lower()
            
            # Handle special cases for Canadian cities
            canadian_cities = ['greater montreal', 'montreal', 'greater vancouver', 'vancouver',
                             'greater toronto', 'gta', 'ottawa', 'calgary', 'edmonton', 'winnipeg']
            if any(city in location_lower for city in canadian_cities):
                return 'canada'
            
            parts = [p.strip() for p in location.split(',')]
            
            # US state abbreviations
            us_states = ['al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 
                        'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md', 
                        'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj', 
                        'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc', 
                        'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy']
            
            for part in parts:
                if part.upper() in [s.upper() for s in us_states]:
                    return 'united states'
            
            # Canadian provinces
            canadian_provinces = ['ab', 'bc', 'mb', 'nb', 'nl', 'ns', 'nt', 'nu', 'on', 'pe', 'qc', 'sk', 'yt']
            canadian_province_names = ['ontario', 'quebec', 'british columbia', 'alberta', 'manitoba', 
                                      'saskatchewan', 'nova scotia', 'new brunswick', 'newfoundland', 
                                      'prince edward island', 'northwest territories', 'yukon', 'nunavut']
            
            for part in parts:
                part_upper = part.upper()
                part_lower = part.lower()
                if part_upper in canadian_provinces or any(name in part_lower for name in canadian_province_names):
                    return 'canada'
            
            # Check for country names in location parts
            for part in parts:
                part_lower = part.lower()
                for country in countries_lower:
                    if country in part_lower or part_lower in country:
                        return country
                
                # Common variations
                if 'united states' in part_lower or 'usa' in part_lower or part_lower in ['us', 'u.s.']:
                    return 'united states'
                if 'united kingdom' in part_lower or part_lower in ['uk', 'u.k.', 'great britain']:
                    return 'united kingdom'
            
            return ''
        
        filtered_jobs = [
            job for job in filtered_jobs
            if extract_country(job.get('location', '')).lower() in countries_lower
        ]
    
    # Status filters (AND logic - job must have ALL selected statuses)
    statuses = filters.get('statuses', [])
    if statuses:
        def job_matches_all_statuses(job):
            for status in statuses:
                if status == 'saved' and job.get('saved') != 1:
                    return False
                elif status == 'applied' and job.get('applied') != 1:
                    return False
                elif status == 'interview' and job.get('interview') != 1:
                    return False
                elif status == 'rejected' and job.get('rejected') != 1:
                    return False
                elif status == 'hidden' and job.get('hidden') != 1:
                    return False
            return True
        
        filtered_jobs = [job for job in filtered_jobs if job_matches_all_statuses(job)]
    
    # Date filter
    date_filter = filters.get('date', '')
    if date_filter:
        from datetime import datetime, timedelta
        now = datetime.now()
        
        def is_date_in_range(job_date_str, range_type):
            if not job_date_str:
                return True
            try:
                # Try to parse the date (format: YYYY-MM-DD)
                job_date = datetime.strptime(job_date_str.split('T')[0], '%Y-%m-%d')
                days_diff = (now - job_date).days
                
                if range_type == '24h':
                    return days_diff <= 1
                elif range_type == '3d':
                    return days_diff <= 3
                elif range_type == '1w':
                    return days_diff <= 7
                elif range_type == '2w':
                    return days_diff <= 14
                elif range_type == '1m':
                    return days_diff <= 30
                return True
            except:
                return True
        
        filtered_jobs = [
            job for job in filtered_jobs
            if is_date_in_range(job.get('date'), date_filter)
        ]
    
    # Sort
    sort_by = filters.get('sort', 'date-desc')
    if sort_by == 'date-desc':
        filtered_jobs.sort(key=lambda x: x.get('id', 0), reverse=True)
    elif sort_by == 'date-asc':
        filtered_jobs.sort(key=lambda x: x.get('id', 0))
    elif sort_by == 'title-asc':
        filtered_jobs.sort(key=lambda x: (x.get('title') or '').lower())
    elif sort_by == 'title-desc':
        filtered_jobs.sort(key=lambda x: (x.get('title') or '').lower(), reverse=True)
    elif sort_by == 'company-asc':
        filtered_jobs.sort(key=lambda x: (x.get('company') or '').lower())
    elif sort_by == 'company-desc':
        filtered_jobs.sort(key=lambda x: (x.get('company') or '').lower(), reverse=True)
    elif sort_by == 'city-asc':
        filtered_jobs.sort(key=lambda x: (x.get('location') or '').lower())
    elif sort_by == 'city-desc':
        filtered_jobs.sort(key=lambda x: (x.get('location') or '').lower(), reverse=True)
    
    return filtered_jobs


@job_bp.route('/api/jobs/export_csv', methods=['POST'])
def export_jobs_csv():
    """Export filtered jobs to CSV"""
    config = current_app.config['CONFIG']
    
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        include_hidden = filters.get('include_hidden', False)
        
        # Get all jobs from database
        if include_hidden:
            jobs = read_jobs_from_db(include_hidden=True)
        else:
            jobs = get_all_jobs_service(config)
        
        # Apply UI filters
        filtered_jobs = apply_ui_filters(jobs, filters)
        
        # Create CSV in memory
        output = io.StringIO()
        
        # Define CSV columns
        fieldnames = [
            'id', 'title', 'company', 'location', 'date', 'job_url',
            'applied', 'saved', 'interview', 'rejected', 'hidden',
            'job_description'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for job in filtered_jobs:
            # Clean up the row data
            row = {}
            for field in fieldnames:
                value = job.get(field, '')
                # Convert boolean/integer fields
                if field in ['applied', 'saved', 'interview', 'rejected', 'hidden']:
                    row[field] = 'Yes' if value == 1 else 'No'
                else:
                    row[field] = str(value) if value is not None else ''
            writer.writerow(row)
        
        # Prepare response
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'jobs_export_{timestamp}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500