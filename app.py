from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS

# Import utility functions
from utils.config_utils import load_config
from services.db_schema_service import verify_db_schema

# Import blueprints
from routes.job_routes import job_bp
from routes.cover_letter_routes import cover_letter_bp
from routes.resume_routes import resume_bp
from routes.application_routes import application_bp
from routes.config_routes import config_bp
from routes.search_routes import search_bp
from routes.ollama_routes import ollama_bp

config = load_config('config.json')
app = Flask(__name__)
CORS(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Register blueprints
app.register_blueprint(job_bp)
app.register_blueprint(cover_letter_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(application_bp)
app.register_blueprint(config_bp)
app.register_blueprint(search_bp)
app.register_blueprint(ollama_bp)

if __name__ == "__main__":
    # Verify database schema on startup
    verify_db_schema(config)
    app.run(debug=True, port=5000)
