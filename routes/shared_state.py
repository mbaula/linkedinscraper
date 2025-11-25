"""
Shared state for blueprints (global variables that need to be shared).
"""
# Global variable to track search status
search_status = {"running": False, "message": "", "completed": False, "completed_at": None, "stop_requested": False}
search_process = None  # Track the subprocess so we can stop it

# Global variable to track cover letter generation status
cover_letter_status = {"running": False, "message": "", "job_id": None, "completed": False}


def update_cover_letter_status(message, job_id=None, completed=False):
    """Update cover letter generation status"""
    global cover_letter_status
    cover_letter_status["message"] = message
    cover_letter_status["running"] = not completed
    cover_letter_status["completed"] = completed
    if job_id:
        cover_letter_status["job_id"] = job_id

