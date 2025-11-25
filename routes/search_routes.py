"""
Search/scraping execution routes blueprint.
"""
from flask import Blueprint, jsonify
import subprocess
import sys
import os
import threading
from datetime import datetime
import routes.shared_state as shared_state

# Create blueprint
search_bp = Blueprint('search', __name__)


@search_bp.route('/api/search/status', methods=['GET'])
def get_search_status():
    """Get current search execution status"""
    return jsonify(shared_state.search_status)


@search_bp.route('/api/search/execute', methods=['POST'])
def execute_search():
    """Execute the search/scraping process"""
    if shared_state.search_status["running"]:
        return jsonify({"error": "Search is already running"}), 400
    
    def run_search():
        shared_state.search_status["running"] = True
        shared_state.search_status["message"] = "Search starting...\nInitializing scraper..."
        shared_state.search_status["stop_requested"] = False
        shared_state.search_status["completed"] = False
        
        try:
            # Set environment to ensure unbuffered output
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            # Run the main.py script with real-time output capture
            # Use -u flag for unbuffered Python output
            shared_state.search_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py', 'config.json'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,  # Unbuffered
                universal_newlines=True,
                cwd=os.getcwd(),
                env=env
            )
            
            # Read output line by line and update status
            output_lines = []
            for line in iter(shared_state.search_process.stdout.readline, ''):
                if shared_state.search_status["stop_requested"]:
                    shared_state.search_process.terminate()
                    shared_state.search_status["message"] = "\n".join(output_lines[-30:]) + "\n\n[WARNING] Search stopped by user"
                    break
                
                if line:
                    line = line.strip()
                    if line:
                        output_lines.append(line)
                        # Keep only last 50 lines to avoid huge messages
                        if len(output_lines) > 50:
                            output_lines.pop(0)
                        # Update status with latest output (show last 30 lines for better visibility)
                        shared_state.search_status["message"] = "\n".join(output_lines[-30:])
            
            # Wait for process to complete
            shared_state.search_process.wait()
            
            # If stop was requested but process already finished, update message
            if shared_state.search_status["stop_requested"] and shared_state.search_process.returncode != -15:  # -15 is SIGTERM
                # Process finished before we could stop it
                pass
            
            # Check final status
            if shared_state.search_status["stop_requested"]:
                if not shared_state.search_status["message"].endswith("[WARNING] Search stopped by user"):
                    shared_state.search_status["message"] = "\n".join(output_lines[-30:]) + "\n\n[WARNING] Search stopped by user"
            elif shared_state.search_process.returncode == 0:
                shared_state.search_status["message"] = "\n".join(output_lines[-30:]) + "\n\n[OK] Search completed successfully"
                shared_state.search_status["completed"] = True
                shared_state.search_status["completed_at"] = datetime.now().isoformat()
            else:
                shared_state.search_status["message"] = "\n".join(output_lines[-30:]) + f"\n\n[ERROR] Search completed with errors (exit code: {shared_state.search_process.returncode})"
                shared_state.search_status["completed"] = True
                shared_state.search_status["completed_at"] = datetime.now().isoformat()
        except Exception as e:
            shared_state.search_status["message"] = f"Error executing search: {str(e)}"
            shared_state.search_status["completed"] = True
            shared_state.search_status["completed_at"] = datetime.now().isoformat()
        finally:
            shared_state.search_status["running"] = False
            shared_state.search_process = None
    
    # Run search in a separate thread
    thread = threading.Thread(target=run_search)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Search started"})


@search_bp.route('/api/search/stop', methods=['POST'])
def stop_search():
    """Stop the currently running search"""
    if not shared_state.search_status["running"]:
        return jsonify({"error": "No search is currently running"}), 400
    
    shared_state.search_status["stop_requested"] = True
    
    if shared_state.search_process:
        try:
            shared_state.search_process.terminate()
            # Give it a moment to terminate gracefully
            import time
            time.sleep(1)
            if shared_state.search_process.poll() is None:
                # If still running, force kill
                shared_state.search_process.kill()
        except Exception as e:
            return jsonify({"error": f"Error stopping search: {str(e)}"}), 500
    
    return jsonify({"success": True, "message": "Stop request sent"})

