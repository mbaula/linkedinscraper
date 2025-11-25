"""
Application tracker routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request, current_app
from services.application_service import (
    get_all_applications,
    create_application as create_application_service,
    update_application as update_application_service,
    delete_application as delete_application_service,
    export_applications_csv
)

# Create blueprint
application_bp = Blueprint('application', __name__)


@application_bp.route('/application_tracker')
def application_tracker():
    """Application tracker page"""
    return render_template('application_tracker.html')


@application_bp.route('/api/applications', methods=['GET'])
def get_applications():
    """Get all applications"""
    config = current_app.config['CONFIG']
    try:
        applications = get_all_applications(config)
        return jsonify(applications)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@application_bp.route('/api/applications', methods=['POST'])
def create_application():
    """Create a new application"""
    config = current_app.config['CONFIG']
    try:
        data = request.json
        app_id = create_application_service(data, config)
        return jsonify({"success": True, "id": app_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@application_bp.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    """Update an application"""
    config = current_app.config['CONFIG']
    try:
        data = request.json
        update_application_service(app_id, data, config)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@application_bp.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    """Delete an application and unmark the job as applied"""
    config = current_app.config['CONFIG']
    try:
        job_id = delete_application_service(app_id, config)
        return jsonify({"success": True, "job_id": job_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@application_bp.route('/api/applications/export', methods=['GET'])
def export_applications_csv():
    """Export all applications to CSV"""
    config = current_app.config['CONFIG']
    try:
        return export_applications_csv(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

