"""
Configuration routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request, current_app
import json
import os
import sqlite3

from utils.config_utils import (
    load_config,
    get_active_config_path,
    get_active_config_relative_path,
    set_active_config_relative_path,
    list_config_profiles,
    save_profile_json,
    delete_profile_json,
)
from services.search_history_service import (
    save_search_history,
    get_search_history,
    get_search_history_by_id,
    delete_search_history,
    clear_search_history
)

# Create blueprint
config_bp = Blueprint('config', __name__)


@config_bp.route('/search_config')
def search_config():
    """Search configuration page"""
    return render_template('search_config.html')


def _config_file_path():
    return current_app.config.get("CONFIG_PATH") or get_active_config_path()


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        path = _config_file_path()
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration (writes the active config file)."""
    try:
        new_config = request.json
        path = _config_file_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        current_app.config['CONFIG_PATH'] = os.path.abspath(path)
        current_app.config['CONFIG'] = load_config(path)
        return jsonify({"success": True, "message": "Configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/active', methods=['GET'])
def get_active_config_info():
    """Active config file path and saved profiles list."""
    try:
        rel = get_active_config_relative_path()
        path = get_active_config_path()
        return jsonify(
            {
                "active_relative_path": rel.replace("\\", "/"),
                "active_absolute_path": os.path.abspath(path),
                "profiles": list_config_profiles(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/profiles', methods=['POST'])
def save_config_profile():
    """
    Save the current in-memory CONFIG (or body.config) as configs/{name}.json.
    JSON body: { "name": "my-profile", "config": { ... optional full dict ... } }
    """
    try:
        data = request.json or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        cfg = data.get("config")
        if cfg is None:
            cfg = current_app.config.get("CONFIG")
        if not isinstance(cfg, dict):
            return jsonify({"error": "No configuration to save"}), 400
        rel = save_profile_json(name, cfg)
        return jsonify({"success": True, "relative_path": rel, "message": f"Saved profile as {rel}"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/profiles/activate', methods=['POST'])
def activate_config_profile():
    """Switch active config file. Body: { \"relative_path\": \"configs/foo.json\" } or { \"name\": \"foo\" }."""
    try:
        data = request.json or {}
        rel = data.get("relative_path")
        if not rel and data.get("name"):
            rel = f"configs/{data['name'].strip()}.json".replace("\\", "/")
        if not rel:
            return jsonify({"error": "relative_path or name is required"}), 400
        rel = rel.strip().replace("\\", "/")
        set_active_config_relative_path(rel)
        path = get_active_config_path()
        current_app.config["CONFIG_PATH"] = os.path.abspath(path)
        current_app.config["CONFIG"] = load_config(path)
        return jsonify(
            {
                "success": True,
                "active_relative_path": rel,
                "message": f"Active configuration is now {rel}",
            }
        )
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/profiles/<string:name>', methods=['DELETE'])
def delete_config_profile(name):
    """Delete configs/{name}.json (cannot delete root config.json)."""
    try:
        if name in ("config.json", "config", "config.json (root)"):
            return jsonify({"error": "Cannot delete root config.json via this endpoint"}), 400
        removed = delete_profile_json(name)
        if not removed:
            return jsonify({"error": "Profile not found"}), 404
        if get_active_config_relative_path() == f"configs/{name}.json".replace("\\", "/"):
            set_active_config_relative_path("config.json")
            path = get_active_config_path()
            current_app.config["CONFIG_PATH"] = os.path.abspath(path)
            current_app.config["CONFIG"] = load_config(path)
        return jsonify({"success": True, "message": f"Deleted profile {name}"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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


@config_bp.route('/api/search-history', methods=['GET'])
def get_search_history_route():
    """Get recent search history"""
    try:
        config = current_app.config['CONFIG']
        limit = request.args.get('limit', 20, type=int)
        history = get_search_history(config, limit=limit)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/search-history/<int:history_id>', methods=['GET'])
def get_search_history_by_id_route(history_id):
    """Get a specific search history entry"""
    try:
        config = current_app.config['CONFIG']
        entry = get_search_history_by_id(history_id, config)
        if entry:
            return jsonify(entry)
        else:
            return jsonify({"error": "Search history entry not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/search-history', methods=['POST'])
def save_search_history_route():
    """Save search configuration to history"""
    try:
        config = current_app.config['CONFIG']
        data = request.json
        search_name = data.get('search_name')
        
        # Merge with current config to get all necessary fields
        history_config = {
            'search_queries': data.get('search_queries', config.get('search_queries', [])),
            'desc_words': data.get('desc_words', config.get('desc_words', [])),
            'title_exclude': data.get('title_exclude', config.get('title_exclude', [])),
            'title_include': data.get('title_include', config.get('title_include', [])),
            'company_exclude': data.get('company_exclude', config.get('company_exclude', [])),
            'languages': data.get('languages', config.get('languages', [])),
            'pages_to_scrape': data.get('pages_to_scrape', config.get('pages_to_scrape', 10)),
            'rounds': data.get('rounds', config.get('rounds', 1)),
            'days_to_scrape': data.get('days_to_scrape', config.get('days_to_scrape', 10)),
            'timespan': data.get('timespan', config.get('timespan', ''))
        }
        
        history_id = save_search_history(config, search_name=search_name)
        return jsonify({"success": True, "id": history_id, "message": "Search saved to history"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/search-history/<int:history_id>', methods=['DELETE'])
def delete_search_history_route(history_id):
    """Delete a search history entry"""
    try:
        config = current_app.config['CONFIG']
        deleted = delete_search_history(history_id, config)
        if deleted:
            return jsonify({"success": True, "message": "Search history deleted"})
        else:
            return jsonify({"error": "Search history entry not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/search-history/clear', methods=['POST'])
def clear_search_history_route():
    """Clear all search history"""
    try:
        config = current_app.config['CONFIG']
        count = clear_search_history(config)
        return jsonify({"success": True, "message": f"Cleared {count} search history entries"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

