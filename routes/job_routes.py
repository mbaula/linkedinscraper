"""
Job-related routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request
from services.job_service import (
    get_all_jobs as get_all_jobs_service,
    get_job_by_id,
    update_job_status,
    read_jobs_from_db
)
from utils.config_utils import load_config

# Create blueprint
job_bp = Blueprint('job', __name__)

# Load config (will be passed from app.py, but we can also load it here as fallback)
config = load_config('config.json')


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
    # Check if user wants to see hidden jobs
    include_hidden = request.args.get('include_hidden', 'false').lower() == 'true'
    if include_hidden:
        jobs = read_jobs_from_db(include_hidden=True)
    else:
        jobs = get_all_jobs_service(config)
    return jsonify(jobs)


@job_bp.route('/job_details/<int:job_id>')
def job_details(job_id):
    """Get job details by ID"""
    job = get_job_by_id(job_id, config)
    if job:
        return jsonify(job)
    else:
        return jsonify({"error": "Job not found"}), 404


@job_bp.route('/hide_job/<int:job_id>', methods=['POST'])
def hide_job(job_id):
    """Hide a job"""
    update_job_status(job_id, 'hidden', 1, config)
    return jsonify({"success": "Job marked as hidden"}), 200


@job_bp.route('/unhide_job/<int:job_id>', methods=['POST'])
def unhide_job(job_id):
    """Unhide a job"""
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
    update_job_status(job_id, 'applied', 0, config)
    return jsonify({"success": "Job unmarked as applied"}), 200


@job_bp.route('/mark_saved/<int:job_id>', methods=['POST'])
def mark_saved(job_id):
    """Mark a job as saved"""
    print("Saved clicked!")
    print(f'Updating job_id: {job_id} to saved')
    update_job_status(job_id, 'saved', 1, config)
    return jsonify({"success": "Job marked as saved"}), 200


@job_bp.route('/unmark_saved/<int:job_id>', methods=['POST'])
def unmark_saved(job_id):
    """Unmark a job as saved"""
    print("Unsave clicked!")
    print(f'Updating job_id: {job_id} to unsaved')
    update_job_status(job_id, 'saved', 0, config)
    return jsonify({"success": "Job unmarked as saved"}), 200


@job_bp.route('/mark_interview/<int:job_id>', methods=['POST'])
def mark_interview(job_id):
    """Mark a job as interview"""
    print("Interview clicked!")
    print(f'Updating job_id: {job_id} to interview')
    update_job_status(job_id, 'interview', 1, config)
    return jsonify({"success": "Job marked as interview"}), 200


@job_bp.route('/mark_rejected/<int:job_id>', methods=['POST'])
def mark_rejected(job_id):
    """Mark a job as rejected"""
    print("Rejected clicked!")
    print(f'Updating job_id: {job_id} to rejected')
    update_job_status(job_id, 'rejected', 1, config)
    return jsonify({"success": "Job marked as rejected"}), 200

