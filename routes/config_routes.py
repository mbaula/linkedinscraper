"""
Configuration routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request
import json
from utils.config_utils import load_config

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
        # Reload config
        from app import config as app_config
        app_config.update(new_config)
        return jsonify({"success": True, "message": "Configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

