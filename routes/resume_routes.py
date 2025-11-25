"""
Resume-related routes blueprint.
"""
from flask import Blueprint, jsonify
import openai
from services.job_service import get_job_by_id, update_job_field
from utils.config_utils import load_config
from utils.pdf_utils import read_pdf

# Create blueprint
resume_bp = Blueprint('resume', __name__)

# Load config
config = load_config('config.json')


@resume_bp.route('/get_resume/<int:job_id>', methods=['POST'])
def get_resume(job_id):
    """Generate tailored resume for a job"""
    print("Resume clicked!")
    job = get_job_by_id(job_id, config)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    
    resume = read_pdf(config["resume_path"])

    # Check if OpenAI API key is empty
    if not config["OpenAI_API_KEY"]:
        print("Error: OpenAI API key is empty.")
        return jsonify({"error": "OpenAI API key is empty."}), 400

    openai.api_key = config["OpenAI_API_KEY"]
    consideration = ""
    user_prompt = ("You are a career coach with a client that is applying for a job as a " 
                   + job['title'] + " at " + job['company'] 
                   + ". They have a resume that you need to review and suggest how to tailor it for the job. "
                   "Approach this task in the following steps: \n 1. Highlight three to five most important responsibilities for this role based on the job description. "
                   "\n2. Based on these most important responsibilities from the job description, please tailor the resume for this role. Do not make information up. "
                   "Respond with the final resume only. \n\n Here is the job description: " 
                   + job['job_description'] + "\n\n Here is the resume: " + resume)
    if consideration:
        user_prompt += "\nConsider incorporating that " + consideration

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        response = completion.choices[0].message.content
    except Exception as e:
        print(f"Error connecting to OpenAI: {e}")
        return jsonify({"error": f"Error connecting to OpenAI: {e}"}), 500

    print(f'Updating resume for job_id: {job_id}')
    update_job_field(job_id, 'resume', response, config)
    return jsonify({"resume": response}), 200

