"""
LinkedIn Job Scraper Flask Application

Main application file using the application factory pattern.
"""
from flask import Flask
from flask_cors import CORS

import os

from utils.config_utils import load_config, get_active_config_path, get_project_root
from services.db_schema_service import verify_db_schema


def create_app(config_path=None):
    """
    Application factory function.
    
    Creates and configures the Flask application instance.
    
    Args:
        config_path (str | None): Path to the configuration JSON file. If None, uses the
            active config (see active_config.txt or config.json).
        
    Returns:
        Flask: Configured Flask application instance.
    """
    if config_path is None:
        resolved = get_active_config_path()
    elif os.path.isabs(config_path):
        resolved = os.path.normpath(config_path)
    else:
        resolved = os.path.normpath(os.path.join(get_project_root(), config_path))
    config = load_config(resolved)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Store config in app.config for access via current_app
    app.config['CONFIG'] = config
    app.config['CONFIG_PATH'] = os.path.abspath(resolved)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Initialize CORS
    CORS(app)
    
    # Register blueprints
    from routes.job_routes import job_bp
    from routes.cover_letter_routes import cover_letter_bp
    from routes.resume_routes import resume_bp
    from routes.application_routes import application_bp
    from routes.config_routes import config_bp
    from routes.search_routes import search_bp
    from routes.ollama_routes import ollama_bp
    from routes.skills_insights_routes import skills_insights_bp
    
    app.register_blueprint(job_bp)
    app.register_blueprint(cover_letter_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(application_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(ollama_bp)
    app.register_blueprint(skills_insights_bp)

    verify_db_schema(config)
    return app


# Create app instance for direct execution
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
