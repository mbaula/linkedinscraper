"""
LinkedIn Job Scraper Flask Application

Main application file using the application factory pattern.
"""
from flask import Flask
from flask_cors import CORS

from utils.config_utils import load_config
from services.db_schema_service import verify_db_schema


def create_app(config_path='config.json'):
    """
    Application factory function.
    
    Creates and configures the Flask application instance.
    
    Args:
        config_path (str): Path to the configuration JSON file. Defaults to 'config.json'.
        
    Returns:
        Flask: Configured Flask application instance.
    """
    # Load configuration
    config = load_config(config_path)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Store config in app.config for access via current_app
    app.config['CONFIG'] = config
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
    
    app.register_blueprint(job_bp)
    app.register_blueprint(cover_letter_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(application_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(ollama_bp)
    
    return app


# Create app instance for direct execution
app = create_app()

if __name__ == "__main__":
    # Verify database schema on startup
    verify_db_schema(app.config['CONFIG'])
    app.run(debug=True, port=5000)
