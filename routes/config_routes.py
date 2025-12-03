"""
Configuration routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request, current_app
import json
import sqlite3

# Create blueprint
config_bp = Blueprint('config', __name__)


@config_bp.route('/search_config')
def search_config():
    """Search configuration page"""
    return render_template('search_config.html')


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        new_config = request.json
        with open('config.json', 'w') as f:
            json.dump(new_config, f, indent=4)
        # Reload config in app context
        from utils.config_utils import load_config
        current_app.config['CONFIG'] = load_config('config.json')
        return jsonify({"success": True, "message": "Configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/clear-job-cache', methods=['POST'])
def clear_job_cache():
    """Clear the job cache"""
    try:
        config = current_app.config['CONFIG']
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute("DELETE FROM job_cache")
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Job cache cleared successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/clear-resume-cache', methods=['POST'])
def clear_resume_cache():
    """Clear the resume cache"""
    try:
        config = current_app.config['CONFIG']
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute("DELETE FROM resume_cache")
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Resume cache cleared successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

