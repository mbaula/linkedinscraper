"""
Configuration routes blueprint.
"""
from flask import Blueprint, render_template, jsonify, request, current_app
import json
import sqlite3
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


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        new_config = request.json
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
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

