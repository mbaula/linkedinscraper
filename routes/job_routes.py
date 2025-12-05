"""
Job-related routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request, current_app
from services.job_service import (
    get_all_jobs as get_all_jobs_service,
    get_job_by_id,
    update_job_status,
    read_jobs_from_db
)

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