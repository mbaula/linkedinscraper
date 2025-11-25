from flask import Flask, render_template, jsonify, request, Response
import pandas as pd
import sqlite3
import json
import openai
from flask_cors import CORS
import threading
import subprocess
import os
import sys
import csv
import io
import requests
import re
import glob
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Import utility functions
from utils.config_utils import load_config
from utils.pdf_utils import read_pdf
from utils.text_utils import (
    format_cover_letter_for_latex,
    escape_xml_text,
    normalize_dashes_for_docx,
    post_process_cover_letter
)

# Import service layers
from services.job_service import (
    get_all_jobs as get_all_jobs_service,
    get_job_by_id,
    update_job_status,
    update_job_field,
    get_job_field,
    get_job_details_for_application,
    read_jobs_from_db,
    filter_jobs_by_config
)
from services.application_service import (
    get_all_applications,
    create_application as create_application_service,
    update_application as update_application_service,
    delete_application as delete_application_service,
    check_application_exists,
    export_applications_csv
)
from services.db_schema_service import verify_db_schema

config = load_config('config.json')
app = Flask(__name__)
CORS(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# db = load_config('config.json')['db_path']
# try:
#     api_key = load_config('config.json')['OpenAI_API_KEY']
#     print("API key found")
# except:
#     print("No OpenAI API key found. Please add one to config.json")

# try:
#     gpt_model = load_config('config.json')['OpenAI_Model']
#     print("Model found")
# except:
#     print("No OpenAI Model found or it's incorrectly specified in the config. Please add one to config.json")

@app.route('/')
def home():
    jobs = read_jobs_from_db()
    return render_template('jobs.html', jobs=jobs)

@app.route('/job/<int:job_id>')
def job(job_id):
    jobs = read_jobs_from_db()
    # Find job by ID in the filtered list
    job = next((j for j in jobs if j.get('id') == job_id), None)
    if job:
        return render_template('./templates/job_description.html', job=job)
    else:
        return render_template('./templates/job_description.html', job=None)

@app.route('/get_all_jobs')
def get_all_jobs():
    jobs = get_all_jobs_service(config)
    return jsonify(jobs)

@app.route('/job_details/<int:job_id>')
def job_details(job_id):
    job = get_job_by_id(job_id, config)
    if job:
        return jsonify(job)
    else:
        return jsonify({"error": "Job not found"}), 404

@app.route('/hide_job/<int:job_id>', methods=['POST'])
def hide_job(job_id):
    update_job_status(job_id, 'hidden', 1, config)
    return jsonify({"success": "Job marked as hidden"}), 200


@app.route('/mark_applied/<int:job_id>', methods=['POST'])
def mark_applied(job_id):
    print("Applied clicked!")
    from datetime import datetime
    
    # Update jobs table
    print(f'Updating job_id: {job_id} to applied')
    update_job_status(job_id, 'applied', 1, config)
    
    # Get job details to auto-populate application
    job = get_job_details_for_application(job_id, config)
    
    if job:
        title, company, job_url, job_date = job
        
        # Check if application already exists for this job
        if not check_application_exists(job_id, config):
            # Create new application entry
            date_submitted = datetime.now().strftime("%Y-%m-%d")
            create_application_service({
                'job_id': job_id,
                'company_name': company,
                'application_status': 'Applied',
                'role': title,
                'date_submitted': date_submitted,
                'link_to_job_req': job_url
            }, config)
            print(f"Created application entry for job_id: {job_id}")
    
    return jsonify({"success": "Job marked as applied"}), 200

@app.route('/unmark_applied/<int:job_id>', methods=['POST'])
def unmark_applied(job_id):
    """Unmark a job as applied"""
    update_job_status(job_id, 'applied', 0, config)
    return jsonify({"success": "Job unmarked as applied"}), 200

@app.route('/mark_saved/<int:job_id>', methods=['POST'])
def mark_saved(job_id):
    """Mark a job as saved"""
    print("Saved clicked!")
    print(f'Updating job_id: {job_id} to saved')
    update_job_status(job_id, 'saved', 1, config)
    return jsonify({"success": "Job marked as saved"}), 200

@app.route('/unmark_saved/<int:job_id>', methods=['POST'])
def unmark_saved(job_id):
    """Unmark a job as saved"""
    print("Unsave clicked!")
    print(f'Updating job_id: {job_id} to unsaved')
    update_job_status(job_id, 'saved', 0, config)
    return jsonify({"success": "Job unmarked as saved"}), 200

@app.route('/mark_interview/<int:job_id>', methods=['POST'])
def mark_interview(job_id):
    print("Interview clicked!")
    print(f'Updating job_id: {job_id} to interview')
    update_job_status(job_id, 'interview', 1, config)
    return jsonify({"success": "Job marked as interview"}), 200

@app.route('/mark_rejected/<int:job_id>', methods=['POST'])
def mark_rejected(job_id):
    print("Rejected clicked!")
    print(f'Updating job_id: {job_id} to rejected')
    update_job_status(job_id, 'rejected', 1, config)
    return jsonify({"success": "Job marked as rejected"}), 200

@app.route('/get_cover_letter/<int:job_id>')
def get_cover_letter(job_id):
    cover_letter = get_job_field(job_id, 'cover_letter', config)
    if cover_letter is not None:
        return jsonify({"cover_letter": cover_letter})
    else:
        return jsonify({"error": "Cover letter not found"}), 404

@app.route('/get_resume/<int:job_id>', methods=['POST'])
def get_resume(job_id):
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

def call_ollama(prompt, base_url, model):
    """Generic function to call Ollama API"""
    try:
        url = f"{base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(url, json=payload, timeout=300)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            print(f"Ollama API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        return None

def generate_cover_letter_with_ollama(prompt, base_url, model):
    """Generate cover letter using Ollama (free, local LLM)"""
    return call_ollama(prompt, base_url, model)

def generate_cover_letter_with_groq(prompt, api_key):
    """Generate cover letter using Groq (free API tier)"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant",  # Free, fast model
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"Groq API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error connecting to Groq: {e}")
        return None

def generate_cover_letter_with_template(job_description, job_title, company, resume):
    """Generate cover letter using template-based approach (no API needed)"""
    # Extract key skills from job description
    skills_keywords = ["python", "javascript", "react", "aws", "docker", "kubernetes", 
                      "sql", "api", "backend", "frontend", "devops", "cloud", "ml", 
                      "machine learning", "data", "database", "agile", "scrum"]
    
    found_skills = []
    job_desc_lower = job_description.lower()
    for skill in skills_keywords:
        if skill in job_desc_lower:
            found_skills.append(skill.title())
    
    # Extract experience from resume (simple keyword matching)
    experience_keywords = ["experience", "worked", "developed", "implemented", "designed", "built"]
    resume_sentences = resume.split('.')[:5]  # Get first few sentences
    
    # Generate template-based cover letter
    cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}. 

"""
    
    if found_skills:
        cover_letter += f"With experience in {', '.join(found_skills[:5])}, I am excited about the opportunity to contribute to your team.\n\n"
    
    cover_letter += f"""Based on the job description, I understand this role requires someone who can tackle complex technical challenges. My background aligns well with the requirements, and I am confident I can make a meaningful contribution to {company}.

"""
    
    # Add a paragraph about enthusiasm
    cover_letter += f"""I am particularly drawn to this opportunity because it combines my technical expertise with the chance to work on innovative projects. I am eager to bring my skills and passion to your team and help drive success at {company}.

Thank you for considering my application. I look forward to discussing how my experience and enthusiasm can contribute to your team.

Sincerely,
[Your Name]"""
    
    return cover_letter

def generate_cover_letter_with_openai(prompt, api_key, model):
    """Generate cover letter using OpenAI"""
    try:
        openai.api_key = api_key
        completion = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error connecting to OpenAI: {e}")
        return None

def update_cover_letter_status(message, job_id=None, completed=False):
    """Update cover letter generation status"""
    global cover_letter_status
    cover_letter_status["message"] = message
    cover_letter_status["running"] = not completed
    cover_letter_status["completed"] = completed
    if job_id:
        cover_letter_status["job_id"] = job_id

@app.route('/api/cover-letter/status', methods=['GET'])
def get_cover_letter_status():
    """Get current cover letter generation status"""
    return jsonify(cover_letter_status)


@app.route('/api/cover-letter/latex/<int:job_id>', methods=['GET'])
def get_cover_letter_latex(job_id):
    """Get LaTeX-formatted cover letter body for insertion into LaTeX document"""
    cover_letter_text = get_job_field(job_id, 'cover_letter', config)
    
    if not cover_letter_text:
        return jsonify({"error": "Cover letter not found"}), 404
    
    latex_formatted = format_cover_letter_for_latex(cover_letter_text)
    
    return jsonify({"latex": latex_formatted, "full_text": cover_letter_text})


@app.route('/api/cover-letter/docx/<int:job_id>', methods=['GET'])
def generate_cover_letter_docx(job_id):
    """Generate DOCX of cover letter"""
    job = get_job_by_id(job_id, config)
    
    if not job or not job.get('cover_letter'):
        return jsonify({"error": "Cover letter not found"}), 404
    
    cover_letter_text = job['cover_letter']
    job_title = job.get('title', '')
    company = job.get('company', '')
    
    # Create DOCX document
    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Add cover letter content
    # Split by paragraphs
    paragraphs = cover_letter_text.split('\n\n')
    for para in paragraphs:
        if para.strip():
            # Replace newlines within paragraphs with spaces
            para_clean = para.replace('\n', ' ').strip()
            if para_clean:
                # Normalize dashes
                para_clean = normalize_dashes_for_docx(para_clean)
                # Add paragraph
                p = doc.add_paragraph(para_clean)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                # Set spacing
                p.space_after = Pt(12)
    
    # Save to memory
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # Create response
    filename = f"Cover_Letter_{company}_{job_title}_{datetime.now().strftime('%Y%m%d')}.docx"
    filename = filename.replace(' ', '_').replace('/', '_')
    
    return Response(
        buffer.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )

@app.route('/api/cover-letter/pdf/<int:job_id>', methods=['GET'])
def generate_cover_letter_pdf(job_id):
    """Generate PDF of cover letter"""
    job = get_job_by_id(job_id, config)
    
    if not job or not job.get('cover_letter'):
        return jsonify({"error": "Cover letter not found"}), 404
    
    cover_letter_text = job['cover_letter']
    job_title = job.get('title', '')
    company = job.get('company', '')
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='#4CAF50',
        spaceAfter=30,
        alignment=TA_LEFT
    )
    
    # Normal style with better line spacing
    normal_style = ParagraphStyle(
        'CoverLetterNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=12
    )
    
    # Add cover letter content
    # Split by paragraphs and create Paragraph objects
    paragraphs = cover_letter_text.split('\n\n')
    for para in paragraphs:
        if para.strip():
            # Replace newlines within paragraphs with spaces
            para_clean = para.replace('\n', ' ').strip()
            if para_clean:
                # Escape XML/HTML special characters including dashes
                para_escaped = escape_xml_text(para_clean)
                p = Paragraph(para_escaped, normal_style)
                elements.append(p)
                elements.append(Spacer(1, 6))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Create response
    filename = f"Cover_Letter_{company}_{job_title}_{datetime.now().strftime('%Y%m%d')}.pdf"
    filename = filename.replace(' ', '_').replace('/', '_')
    
    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )

@app.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    """Fetch available Ollama models"""
    try:
        ollama_url = config.get("ollama_base_url", "http://localhost:11434")
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = [model['name'] for model in response.json().get('models', [])]
            return jsonify({"models": models}), 200
        else:
            return jsonify({"error": "Failed to fetch models", "models": []}), 500
    except Exception as e:
        print(f"Error fetching Ollama models: {e}")
        return jsonify({"error": str(e), "models": []}), 500

@app.route('/get_CoverLetter/<int:job_id>', methods=['POST'])
def get_CoverLetter(job_id):
    global cover_letter_status, config
    
    if cover_letter_status["running"]:
        return jsonify({"error": "Cover letter generation is already in progress"}), 400
    
    # Get model from request if provided (for Ollama)
    request_data = request.get_json() or {}
    selected_model = request_data.get('model', None)
    
    print("CoverLetter clicked!")
    update_cover_letter_status("Starting cover letter generation...", job_id, False)
    
    job = get_job_by_id(job_id, config)
    if job is None:
        update_cover_letter_status("Error: Job not found", job_id, True)
        return jsonify({"error": "Job not found"}), 404
    
    update_cover_letter_status("Reading resume from PDF...", job_id, False)
    resume = read_pdf(config["resume_path"])

    # Check if resume is None
    if resume is None:
        print("Error: Resume not found or couldn't be read.")
        update_cover_letter_status("Error: Resume not found or couldn't be read.", job_id, True)
        return jsonify({"error": "Resume not found or couldn't be read."}), 400

    provider = config.get("cover_letter_provider", "template").lower()
    
    # Save selected model to config if provided (for Ollama)
    if selected_model and provider == "ollama":
        try:
            with open('config.json', 'r') as f:
                current_config = json.load(f)
            current_config['ollama_model'] = selected_model
            with open('config.json', 'w') as f:
                json.dump(current_config, f, indent=4)
            # Reload global config
            config = load_config('config.json')
            print(f"Saved Ollama model to config: {selected_model}")
        except Exception as e:
            print(f"Error saving model to config: {e}")
    consideration = ""
    
    update_cover_letter_status(f"Using {provider.upper()} provider to generate cover letter...", job_id, False)
    
    # Build the prompt with strict instructions to only use resume information
    user_prompt = ("""CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume. If something is not in the resume, do not mention it.

CRITICAL - COVER LETTER FORMAT: A cover letter is a STORY, NOT a resume. It must be written in NARRATIVE PARAGRAPH form:
- Write flowing paragraphs that tell a story, NOT bullet points, lists, or numbered items
- DO NOT list accomplishments one after another like a resume
- Connect experiences together in a narrative way that shows progression
- Show how past work relates to the role they're applying for through storytelling
- Write 3-4 well-developed paragraphs (each 4-6 sentences) with clear narrative flow
- Each paragraph should have a clear purpose and flow naturally into the next
- DO NOT just copy bullet points from the resume - instead, weave the information into narrative sentences that tell a story
- Tell a story about the candidate's journey, challenges they faced, and how it relates to this opportunity
- Write like you're telling a friend about your experience, not listing resume bullets

IMPORTANT - AVOID AI TELLS: Write naturally and avoid features that make it obvious this is AI-generated:
- Use ONLY regular ASCII hyphens (-), NEVER em dashes (—), en dashes (–), or non-breaking hyphens (‑)
- Write percentages correctly: use 90% NOT 90 % (no space before % sign)
- Avoid overly formal or flowery language
- Don't use repetitive phrases or patterns
- Write in a natural, human voice
- Avoid excessive use of transition phrases like 'Furthermore', 'Moreover', 'In addition'
- Use simple, direct language
- Vary sentence structure naturally
- Don't start every sentence with 'I'

You are a career coach helping a candidate write a cover letter. Write a cover letter for the position below using ONLY the information from the resume. The cover letter MUST be in narrative paragraph form, NOT bullet points.

Step 1. Identify main challenges someone in this position would face based on the job description.

Step 2. Write an opening paragraph (4-5 sentences) that introduces the candidate and expresses genuine interest. Connect their background to why they're interested in this role. Write as flowing narrative that tells a story, NOT bullet points.

Step 3. Write 2-3 body paragraphs (total 250 words) that tell a STORY about the candidate's relevant experience. Weave together experiences from the resume into narrative paragraphs that show how their work relates to this role. Write in paragraph form with flowing sentences that connect ideas and tell a story, NOT as a list of bullet points or accomplishments. Show progression, challenges faced, and connection between experiences. Make it read like a story about their career journey, not a resume. Each paragraph should flow naturally and tell part of the story.

REMEMBER: Every skill, experience, achievement, and qualification you mention MUST be explicitly stated in the resume. If it's not in the resume, do not include it. Use ONLY regular ASCII hyphens (-), NEVER em dashes, en dashes, or non-breaking hyphens. Write in NARRATIVE PARAGRAPH form that tells a STORY, NOT bullet points, NOT lists, NOT numbered items.

Job Description: """ + job['job_description'] + """

Company: """ + job['company'] + """

Job Title: """ + job['title'] + """

Resume:
""" + resume)
    if consideration:
        user_prompt += "\nConsider incorporating that " + consideration

    response = None
    
    # Try to generate cover letter based on provider
    if provider == "ollama":
        ollama_url = config.get("ollama_base_url", "http://localhost:11434")
        # Use selected model from request, or fall back to config, or default
        ollama_model = selected_model or config.get("ollama_model", "gpt-oss")
        print(f"Using Ollama provider with model {ollama_model}")
        update_cover_letter_status(f"Generating initial draft with Ollama ({ollama_model})...", job_id, False)
        response = generate_cover_letter_with_ollama(user_prompt, ollama_url, ollama_model)
        
        if response:
            update_cover_letter_status("Initial draft generated. Refining cover letter...", job_id, False)
            # Refinement step
            user_prompt2 = ("""CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume.

CRITICAL - COVER LETTER FORMAT: The cover letter MUST be in NARRATIVE PARAGRAPH form that tells a STORY, NOT bullet points:
- If the draft has bullet points, lists, numbered items, or reads like a resume, convert ALL of it into flowing narrative paragraphs
- Write in paragraph form with complete sentences that flow together and tell a story
- Tell a story that connects experiences and shows progression, don't just list accomplishments
- Each paragraph should be 4-6 sentences that weave together related experiences into a narrative
- Make it read like a story about their career journey, not a resume listing achievements
- Show how experiences connect and build on each other
- Write like you're telling a story, not listing resume bullets

IMPORTANT - REMOVE AI TELLS: Review the draft and make it sound natural and human:
- Replace ALL em dashes (—), en dashes (–), and non-breaking hyphens (‑) with regular ASCII hyphens (-)
- Fix percentage spacing: remove spaces before % signs (write 90% NOT 90 %)
- Remove overly formal or AI-sounding phrases
- Eliminate repetitive patterns
- Make it sound like a real person wrote it, not AI
- Use simple, direct language
- Avoid excessive transition words
- Vary sentence structure naturally
- Don't start every sentence with 'I'

You are helping improve a cover letter. Review the draft below and improve it while ensuring EVERY claim is backed by information in the resume.

Step 1. Check if the draft is written as bullet points, lists, or reads like a resume. If so, convert ALL of it into narrative paragraphs that tell a story with flowing sentences.

Step 2. Set formality: 1 = conversational, current draft = 10. Target formality = 7.

Step 3. Identify 3-5 improvements, ensuring all examples come from the resume. Also identify and remove any AI tells (em dashes, non-breaking hyphens, overly formal language, repetitive patterns). Ensure it's written as narrative paragraphs that tell a story, NOT bullet points or resume-style lists.

Step 4. Rewrite the cover letter with formality = 7, using ONLY information from the resume. Write in NARRATIVE PARAGRAPH form with flowing sentences that tell a STORY, NOT bullet points, NOT lists, NOT numbered items, NOT resume-style accomplishment lists. Remove any claims not supported by the resume. Avoid subjective qualifiers like 'drastic' or 'transformational'. Use ONLY regular ASCII hyphens (-), NEVER em dashes, en dashes, or non-breaking hyphens. Write naturally, like a human wrote it, in paragraph form that tells a story. Keep within 250 words.

Job Description: """ + job['job_description'] + """

Resume:
""" + resume + """

Current Cover Letter Draft:
""" + response + """

Respond with the improved cover letter only, ensuring: (1) all information comes from the resume, (2) it sounds natural and human-written, (3) it's written in NARRATIVE PARAGRAPH form that tells a STORY (NOT bullet points, NOT lists, NOT numbered items, NOT resume-style), (4) ALL dashes are regular ASCII hyphens (-).""")
            refined = generate_cover_letter_with_ollama(user_prompt2, ollama_url, ollama_model)
            if refined:
                response = refined
                update_cover_letter_status("Cover letter refined successfully!", job_id, False)
                
    elif provider == "groq":
        groq_key = config.get("groq_api_key", "")
        if not groq_key:
            update_cover_letter_status("Error: Groq API key not configured", job_id, True)
            return jsonify({"error": "Groq API key is not configured. Please add 'groq_api_key' to config.json or get a free key from https://console.groq.com"}), 400
        print("Using Groq provider")
        update_cover_letter_status("Generating initial draft with Groq...", job_id, False)
        response = generate_cover_letter_with_groq(user_prompt, groq_key)
        
        if response:
            update_cover_letter_status("Initial draft generated. Refining cover letter...", job_id, False)
            # Refinement step
            user_prompt2 = ("""CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume.

CRITICAL - COVER LETTER FORMAT: The cover letter MUST be in NARRATIVE PARAGRAPH form that tells a STORY, NOT bullet points:
- If the draft has bullet points, lists, numbered items, or reads like a resume, convert ALL of it into flowing narrative paragraphs
- Write in paragraph form with complete sentences that flow together and tell a story
- Tell a story that connects experiences and shows progression, don't just list accomplishments
- Each paragraph should be 4-6 sentences that weave together related experiences into a narrative
- Make it read like a story about their career journey, not a resume listing achievements
- Show how experiences connect and build on each other
- Write like you're telling a story, not listing resume bullets

IMPORTANT - REMOVE AI TELLS: Review the draft and make it sound natural and human:
- Replace ALL em dashes (—), en dashes (–), and non-breaking hyphens (‑) with regular ASCII hyphens (-)
- Fix percentage spacing: remove spaces before % signs (write 90% NOT 90 %)
- Remove overly formal or AI-sounding phrases
- Eliminate repetitive patterns
- Make it sound like a real person wrote it, not AI
- Use simple, direct language
- Avoid excessive transition words
- Vary sentence structure naturally
- Don't start every sentence with 'I'

You are helping improve a cover letter. Review the draft below and improve it while ensuring EVERY claim is backed by information in the resume.

Step 1. Check if the draft is written as bullet points, lists, or reads like a resume. If so, convert ALL of it into narrative paragraphs that tell a story with flowing sentences.

Step 2. Set formality: 1 = conversational, current draft = 10. Target formality = 7.

Step 3. Identify 3-5 improvements, ensuring all examples come from the resume. Also identify and remove any AI tells (em dashes, non-breaking hyphens, overly formal language, repetitive patterns). Ensure it's written as narrative paragraphs that tell a story, NOT bullet points or resume-style lists.

Step 4. Rewrite the cover letter with formality = 7, using ONLY information from the resume. Write in NARRATIVE PARAGRAPH form with flowing sentences that tell a STORY, NOT bullet points, NOT lists, NOT numbered items, NOT resume-style accomplishment lists. Remove any claims not supported by the resume. Avoid subjective qualifiers like 'drastic' or 'transformational'. Use ONLY regular ASCII hyphens (-), NEVER em dashes, en dashes, or non-breaking hyphens. Write naturally, like a human wrote it, in paragraph form that tells a story. Keep within 250 words.

Job Description: """ + job['job_description'] + """

Resume:
""" + resume + """

Current Cover Letter Draft:
""" + response + """

Respond with the improved cover letter only, ensuring: (1) all information comes from the resume, (2) it sounds natural and human-written, (3) it's written in NARRATIVE PARAGRAPH form that tells a STORY (NOT bullet points, NOT lists, NOT numbered items, NOT resume-style), (4) ALL dashes are regular ASCII hyphens (-).""")
            refined = generate_cover_letter_with_groq(user_prompt2, groq_key)
            if refined:
                response = refined
                update_cover_letter_status("Cover letter refined successfully!", job_id, False)
                
    elif provider == "openai":
        openai_key = config.get("OpenAI_API_KEY", "")
        openai_model = config.get("OpenAI_Model", "gpt-3.5-turbo")
        if not openai_key:
            update_cover_letter_status("Error: OpenAI API key is empty", job_id, True)
            return jsonify({"error": "OpenAI API key is empty."}), 400
        print("Using OpenAI provider")
        update_cover_letter_status(f"Generating initial draft with OpenAI ({openai_model})...", job_id, False)
        response = generate_cover_letter_with_openai(user_prompt, openai_key, openai_model)
        
        if response:
            update_cover_letter_status("Initial draft generated. Refining cover letter...", job_id, False)
            # Refinement step
            user_prompt2 = ("""CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume.

CRITICAL - COVER LETTER FORMAT: The cover letter MUST be in NARRATIVE PARAGRAPH form that tells a STORY, NOT bullet points:
- If the draft has bullet points, lists, numbered items, or reads like a resume, convert ALL of it into flowing narrative paragraphs
- Write in paragraph form with complete sentences that flow together and tell a story
- Tell a story that connects experiences and shows progression, don't just list accomplishments
- Each paragraph should be 4-6 sentences that weave together related experiences into a narrative
- Make it read like a story about their career journey, not a resume listing achievements
- Show how experiences connect and build on each other
- Write like you're telling a story, not listing resume bullets

IMPORTANT - REMOVE AI TELLS: Review the draft and make it sound natural and human:
- Replace ALL em dashes (—), en dashes (–), and non-breaking hyphens (‑) with regular ASCII hyphens (-)
- Fix percentage spacing: remove spaces before % signs (write 90% NOT 90 %)
- Remove overly formal or AI-sounding phrases
- Eliminate repetitive patterns
- Make it sound like a real person wrote it, not AI
- Use simple, direct language
- Avoid excessive transition words
- Vary sentence structure naturally
- Don't start every sentence with 'I'

You are helping improve a cover letter. Review the draft below and improve it while ensuring EVERY claim is backed by information in the resume.

Step 1. Check if the draft is written as bullet points, lists, or reads like a resume. If so, convert ALL of it into narrative paragraphs that tell a story with flowing sentences.

Step 2. Set formality: 1 = conversational, current draft = 10. Target formality = 7.

Step 3. Identify 3-5 improvements, ensuring all examples come from the resume. Also identify and remove any AI tells (em dashes, non-breaking hyphens, overly formal language, repetitive patterns). Ensure it's written as narrative paragraphs that tell a story, NOT bullet points or resume-style lists.

Step 4. Rewrite the cover letter with formality = 7, using ONLY information from the resume. Write in NARRATIVE PARAGRAPH form with flowing sentences that tell a STORY, NOT bullet points, NOT lists, NOT numbered items, NOT resume-style accomplishment lists. Remove any claims not supported by the resume. Avoid subjective qualifiers like 'drastic' or 'transformational'. Use ONLY regular ASCII hyphens (-), NEVER em dashes, en dashes, or non-breaking hyphens. Write naturally, like a human wrote it, in paragraph form that tells a story. Keep within 250 words.

Job Description: """ + job['job_description'] + """

Resume:
""" + resume + """

Current Cover Letter Draft:
""" + response + """

Respond with the improved cover letter only, ensuring: (1) all information comes from the resume, (2) it sounds natural and human-written, (3) it's written in NARRATIVE PARAGRAPH form that tells a STORY (NOT bullet points, NOT lists, NOT numbered items, NOT resume-style), (4) ALL dashes are regular ASCII hyphens (-).""")
            refined = generate_cover_letter_with_openai(user_prompt2, openai_key, openai_model)
            if refined:
                response = refined
                update_cover_letter_status("Cover letter refined successfully!", job_id, False)
                
    else:  # template fallback
        print("Using template-based provider (no API needed)")
        update_cover_letter_status("Generating cover letter from template...", job_id, False)
        response = generate_cover_letter_with_template(
            job['job_description'], 
            job['title'], 
            job['company'], 
            resume
        )
        update_cover_letter_status("Template-based cover letter generated!", job_id, False)

    if response is None:
        update_cover_letter_status(f"Error: Failed to generate cover letter using {provider} provider", job_id, True)
        return jsonify({"error": f"Failed to generate cover letter using {provider} provider."}), 500

    # Post-process to clean up any remaining issues
    update_cover_letter_status("Cleaning up cover letter...", job_id, False)
    response = post_process_cover_letter(response)

    update_cover_letter_status("Saving cover letter to database...", job_id, False)
    print(f'Updating cover letter for job_id: {job_id}')
    update_job_field(job_id, 'cover_letter', response, config)
    
    update_cover_letter_status("Cover letter generated successfully!", job_id, True)
    return jsonify({"cover_letter": response}), 200



# Global variable to track search status
search_status = {"running": False, "message": "", "completed": False, "completed_at": None, "stop_requested": False}
search_process = None  # Track the subprocess so we can stop it

# Global variable to track cover letter generation status
cover_letter_status = {"running": False, "message": "", "job_id": None, "completed": False}

@app.route('/search_config')
def search_config():
    return render_template('search_config.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        new_config = request.json
        with open('config.json', 'w') as f:
            json.dump(new_config, f, indent=4)
        # Reload config
        global config
        config = load_config('config.json')
        return jsonify({"success": True, "message": "Configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search/status', methods=['GET'])
def get_search_status():
    """Get current search execution status"""
    return jsonify(search_status)

@app.route('/application_tracker')
def application_tracker():
    return render_template('application_tracker.html')

@app.route('/api/applications', methods=['GET'])
def get_applications():
    """Get all applications"""
    try:
        applications = get_all_applications(config)
        return jsonify(applications)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications', methods=['POST'])
def create_application():
    """Create a new application"""
    try:
        data = request.json
        app_id = create_application_service(data, config)
        return jsonify({"success": True, "id": app_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    """Update an application"""
    try:
        data = request.json
        update_application_service(app_id, data, config)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    """Delete an application and unmark the job as applied"""
    try:
        job_id = delete_application_service(app_id, config)
        return jsonify({"success": True, "job_id": job_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications/export', methods=['GET'])
def export_applications_csv():
    """Export all applications to CSV"""
    try:
        return export_applications_csv(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search/execute', methods=['POST'])
def execute_search():
    """Execute the search/scraping process"""
    global search_status, search_process
    
    if search_status["running"]:
        return jsonify({"error": "Search is already running"}), 400
    
    def run_search():
        global search_status, search_process
        from datetime import datetime
        search_status["running"] = True
        search_status["message"] = "Search starting...\nInitializing scraper..."
        search_status["stop_requested"] = False
        search_status["completed"] = False
        
        try:
            # Set environment to ensure unbuffered output
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            # Run the main.py script with real-time output capture
            # Use -u flag for unbuffered Python output
            search_process = subprocess.Popen(
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
            for line in iter(search_process.stdout.readline, ''):
                if search_status["stop_requested"]:
                    search_process.terminate()
                    search_status["message"] = "\n".join(output_lines[-30:]) + "\n\n[WARNING] Search stopped by user"
                    break
                
                if line:
                    line = line.strip()
                    if line:
                        output_lines.append(line)
                        # Keep only last 50 lines to avoid huge messages
                        if len(output_lines) > 50:
                            output_lines.pop(0)
                        # Update status with latest output (show last 30 lines for better visibility)
                        search_status["message"] = "\n".join(output_lines[-30:])
            
            # Wait for process to complete
            search_process.wait()
            
            # If stop was requested but process already finished, update message
            if search_status["stop_requested"] and search_process.returncode != -15:  # -15 is SIGTERM
                # Process finished before we could stop it
                pass
            
            # Check final status
            if search_status["stop_requested"]:
                if not search_status["message"].endswith("[WARNING] Search stopped by user"):
                    search_status["message"] = "\n".join(output_lines[-30:]) + "\n\n[WARNING] Search stopped by user"
            elif search_process.returncode == 0:
                search_status["message"] = "\n".join(output_lines[-30:]) + "\n\n[OK] Search completed successfully"
                search_status["completed"] = True
                search_status["completed_at"] = datetime.now().isoformat()
            else:
                search_status["message"] = "\n".join(output_lines[-30:]) + f"\n\n[ERROR] Search completed with errors (exit code: {search_process.returncode})"
                search_status["completed"] = True
                search_status["completed_at"] = datetime.now().isoformat()
        except Exception as e:
            search_status["message"] = f"Error executing search: {str(e)}"
            search_status["completed"] = True
            search_status["completed_at"] = datetime.now().isoformat()
        finally:
            search_status["running"] = False
            search_process = None
    
    # Run search in a separate thread
    thread = threading.Thread(target=run_search)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Search started"})

@app.route('/api/search/stop', methods=['POST'])
def stop_search():
    """Stop the currently running search"""
    global search_status, search_process
    
    if not search_status["running"]:
        return jsonify({"error": "No search is currently running"}), 400
    
    search_status["stop_requested"] = True
    
    if search_process:
        try:
            search_process.terminate()
            # Give it a moment to terminate gracefully
            import time
            time.sleep(1)
            if search_process.poll() is None:
                # If still running, force kill
                search_process.kill()
        except Exception as e:
            return jsonify({"error": f"Error stopping search: {str(e)}"}), 500
    
    return jsonify({"success": True, "message": "Stop request sent"})

# ============================================================================
# OLLAMA PIPELINE FUNCTIONS
# ============================================================================

# JSON Schemas
JOB_SCHEMA = """{
  "title": "string",
  "company": "string",
  "location": "string",
  "datePosted": "YYYY-MM-DD",
  "description": "string",
  "requirements": ["string"],
  "skills": ["string"],
  "experience": "string",
  "education": "string",
  "employmentType": "string",
  "salary": "string",
  "website": "URI",
  "applyLink": "URI"
}"""

RESUME_SCHEMA = """{
  "personalInfo": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string",
    "linkedin": "string",
    "github": "string",
    "website": "string"
  },
  "summary": "string",
  "workExperience": [
    {
      "title": "string",
      "company": "string",
      "location": "string",
      "startDate": "YYYY-MM-DD",
      "endDate": "YYYY-MM-DD or 'Present'",
      "description": ["string"]
    }
  ],
  "education": [
    {
      "degree": "string",
      "institution": "string",
      "location": "string",
      "startDate": "YYYY-MM-DD",
      "endDate": "YYYY-MM-DD or 'Present'",
      "gpa": "string"
    }
  ],
  "projects": [
    {
      "name": "string",
      "description": "string",
      "technologies": ["string"],
      "url": "string"
    }
  ],
  "additional": {
    "technicalSkills": ["string"],
    "languages": ["string"],
    "certifications": ["string"],
    "awards": ["string"]
  }
}"""

ANALYSIS_SCHEMA = """{
  "overallFit": {
    "details": "string",
    "commentary": "string"
  },
  "improvements": [
    {
      "suggestion": "string",
      "lineNumber": "number or null",
      "section": "string or null"
    }
  ]
}"""

def structured_job_prompt(raw_job_text, base_url, model):
    """
    STEP 1: Job Posting → Job JSON
    Converts raw job posting text into structured JSON using Ollama.
    """
    prompt = f"""You are a JSON-extraction engine. Convert the following raw job posting text into exactly the JSON schema below:
— Do not add any extra fields or prose.
— Use "YYYY-MM-DD" for all dates.
— Ensure any URLs (website, applyLink) conform to URI format.
— Do not change the structure or key names; output only valid JSON matching the schema.
— Do not format the response in Markdown or any other format. Just output raw JSON.

Schema:
```json
{JOB_SCHEMA}
```

Job Posting:
{raw_job_text}

Note: Please output only a valid JSON matching the EXACT schema with no surrounding commentary."""

    response = call_ollama(prompt, base_url, model)
    if not response:
        return None
    
    # Try to extract JSON from response (in case there's any markdown formatting)
    import re
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
    else:
        json_str = response
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing job JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None

def structured_resume_prompt(resume_text, base_url, model):
    """
    STEP 2: Resume Text → Resume JSON
    Converts resume text into structured JSON using Ollama.
    """
    prompt = f"""You are a JSON extraction engine. Convert the following resume text into precisely the JSON schema specified below.

Map each resume section to the schema without inventing information.

If a field is missing in the source text, use an empty string or empty list as appropriate.

Preserve bullet points in the description arrays using short factual sentences.

Use "Present" if an end date is ongoing and prefer YYYY-MM-DD where dates are available.

Keep the additional section organised: list technical skills, languages, certifications/training, and awards exactly as they appear.

Do not compose any extra fields or commentary and output raw JSON only (no Markdown, no prose).

Schema:

{RESUME_SCHEMA}

Resume:

{resume_text}

NOTE: Please output only a valid JSON matching the EXACT schema."""

    response = call_ollama(prompt, base_url, model)
    if not response:
        return None
    
    # Try to extract JSON from response
    import re
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
    else:
        json_str = response
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing resume JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None

def resume_analysis_prompt(job_json, resume_json, improved_resume_text, job_keywords, resume_keywords, old_sim, new_sim, base_url, model):
    """
    STEP 3: Job JSON + Resume JSON → Match Analysis JSON
    Analyzes how well the resume matches the job using Ollama.
    """
    job_description = job_json.get("description", "") if isinstance(job_json, dict) else str(job_json)
    resume_text = json.dumps(resume_json, indent=2) if isinstance(resume_json, dict) else str(resume_json)
    job_keywords_str = ", ".join(job_keywords) if isinstance(job_keywords, list) else str(job_keywords)
    resume_keywords_str = ", ".join(resume_keywords) if isinstance(resume_keywords, list) else str(resume_keywords)
    
    prompt = f"""You are an ATS-focused resume analyst. Compare the original resume with the improved resume against the job description and extracted keywords.
Return a concise analysis that explains the resume's strengths, gaps, and next steps.

Instructions:

Study the job description, keyword lists, and both resume versions.

Summarize the overall fit in two short paragraphs:

details: What changed and why it matters (mention the biggest gaps filled or still open).

commentary: Strategic advice on further improvements or positioning.

Provide improvements as 3-5 actionable bullet points. Each suggestion should be specific; include a lineNumber or section name when relevant, otherwise set it to null.

Use direct, professional wording. Avoid repeating the job description verbatim and do not invent experience that does not appear in either resume.

STRICTLY emit JSON that matches the schema below with no extra keys, prose, or markdown.

Schema:

{ANALYSIS_SCHEMA}

Context:
Job Description:

{job_description}

Extracted Job Keywords:

{job_keywords_str}

Original Resume:

{resume_text}

Extracted Resume Keywords:

{resume_keywords_str}

Improved Resume:

{improved_resume_text}

Original Cosine Similarity: {old_sim:.4f}
New Cosine Similarity: {new_sim:.4f}"""

    response = call_ollama(prompt, base_url, model)
    if not response:
        return None
    
    # Try to extract JSON from response
    import re
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
    else:
        json_str = response
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing analysis JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None

def resume_improvement_prompt(raw_job_description, extracted_job_keywords, raw_resume, extracted_resume_keywords, ats_recommendations, skill_priority_text, current_cosine_similarity, base_url, model):
    """
    STEP 4 (Optional): Resume Rewriter
    Improves resume to better match job description using Ollama.
    """
    job_keywords_str = ", ".join(extracted_job_keywords) if isinstance(extracted_job_keywords, list) else str(extracted_job_keywords)
    resume_keywords_str = ", ".join(extracted_resume_keywords) if isinstance(extracted_resume_keywords, list) else str(extracted_resume_keywords)
    
    prompt = f"""You are an expert resume editor and talent acquisition specialist. Your task is to revise the following resume so that it aligns as closely as possible with the provided job description and extracted job keywords, in order to maximize the cosine similarity between the resume and the job keywords.

Instructions:

Carefully review the job description and the list of extracted job keywords.

Use the ATS guidance below to address structural or keyword gaps before rewriting bullets:

ATS Recommendations:
{ats_recommendations}

Priority keywords ranked by job emphasis:
{skill_priority_text}

Update the candidate's resume by rephrasing and reordering existing content so it highlights the most relevant evidence:

Emphasize and naturally weave job-aligned keywords by rewriting existing bullets, sentences, and headings. You may combine or split bullets, reorder content, and surface tools/methods that are already mentioned or clearly implied.

Do NOT invent new jobs, projects, technologies, certifications, or accomplishments that are not present in the original resume text.

Preserve the core section structure: Education, Work Experience, Personal Projects, Additional (Technical Skills, Languages, Certifications & Training, Awards). You may add a concise "Summary" or "Professional Summary" section at the top if it is missing.

When a requirement is missing, do not fabricate experience. Instead, highlight adjacent or transferable elements already in the resume.

Maintain a natural, professional tone and avoid keyword stuffing.

The current cosine similarity score is {current_cosine_similarity:.4f}. Revise the resume using the above constraints to increase this score.

ONLY output the improved updated resume. Do not include any explanations, commentary, or formatting outside of the resume itself.

Job Description:

{raw_job_description}

Extracted Job Keywords:

{job_keywords_str}

Original Resume:

{raw_resume}

Extracted Resume Keywords:

{resume_keywords_str}

NOTE: ONLY OUTPUT THE IMPROVED UPDATED RESUME IN MARKDOWN FORMAT."""

    response = call_ollama(prompt, base_url, model)
    return response

# ============================================================================
# API ENDPOINTS FOR OLLAMA PIPELINE
# ============================================================================

@app.route('/api/ollama/structured-job', methods=['POST'])
def api_structured_job():
    """API endpoint for STEP 1: Job Posting → Job JSON"""
    try:
        data = request.get_json()
        raw_job_text = data.get('job_text', '')
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        if not raw_job_text:
            return jsonify({"error": "job_text is required"}), 400
        
        result = structured_job_prompt(raw_job_text, base_url, model)
        if result is None:
            return jsonify({"error": "Failed to extract job JSON from Ollama"}), 500
        
        return jsonify({"job_json": result}), 200
    except Exception as e:
        print(f"Error in structured_job_prompt API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ollama/structured-resume', methods=['POST'])
def api_structured_resume():
    """API endpoint for STEP 2: Resume Text → Resume JSON"""
    try:
        data = request.get_json()
        resume_text = data.get('resume_text', '')
        resume_path = data.get('resume_path', None)
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        # If resume_path provided, load from file; otherwise use resume_text
        if resume_path and not resume_text:
            resume_text = read_pdf(resume_path)
            if not resume_text:
                return jsonify({"error": f"Failed to read resume from {resume_path}"}), 400
        elif not resume_text:
            # Try to use default resume path from config
            resume_path = config.get("resume_path", "")
            if resume_path:
                resume_text = read_pdf(resume_path)
                if not resume_text:
                    return jsonify({"error": f"Failed to read resume from {resume_path}"}), 400
            else:
                return jsonify({"error": "resume_text or resume_path is required"}), 400
        
        result = structured_resume_prompt(resume_text, base_url, model)
        if result is None:
            return jsonify({"error": "Failed to extract resume JSON from Ollama"}), 500
        
        return jsonify({"resume_json": result}), 200
    except Exception as e:
        print(f"Error in structured_resume_prompt API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ollama/resume-analysis', methods=['POST'])
def api_resume_analysis():
    """API endpoint for STEP 3: Job JSON + Resume JSON → Match Analysis JSON"""
    try:
        data = request.get_json()
        job_json = data.get('job_json', {})
        resume_json = data.get('resume_json', {})
        improved_resume_text = data.get('improved_resume', '')
        job_keywords = data.get('job_keywords', [])
        resume_keywords = data.get('resume_keywords', [])
        old_sim = data.get('old_sim', 0.0)
        new_sim = data.get('new_sim', 0.0)
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        if not job_json or not resume_json:
            return jsonify({"error": "job_json and resume_json are required"}), 400
        
        result = resume_analysis_prompt(
            job_json, resume_json, improved_resume_text,
            job_keywords, resume_keywords, old_sim, new_sim,
            base_url, model
        )
        if result is None:
            return jsonify({"error": "Failed to generate analysis from Ollama"}), 500
        
        return jsonify({"analysis_json": result}), 200
    except Exception as e:
        print(f"Error in resume_analysis_prompt API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ollama/resume-improvement', methods=['POST'])
def api_resume_improvement():
    """API endpoint for STEP 4: Resume Rewriter"""
    try:
        data = request.get_json()
        raw_job_description = data.get('job_description', '')
        extracted_job_keywords = data.get('job_keywords', [])
        raw_resume = data.get('resume', '')
        resume_path = data.get('resume_path', None)
        extracted_resume_keywords = data.get('resume_keywords', [])
        ats_recommendations = data.get('ats_recommendations', '')
        skill_priority_text = data.get('skill_priority_text', '')
        current_cosine_similarity = data.get('current_cosine_similarity', 0.0)
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        # If resume_path provided, load from file; otherwise use raw_resume
        if resume_path and not raw_resume:
            raw_resume = read_pdf(resume_path)
            if not raw_resume:
                return jsonify({"error": f"Failed to read resume from {resume_path}"}), 400
        elif not raw_resume:
            # Try to use default resume path from config
            resume_path = config.get("resume_path", "")
            if resume_path:
                raw_resume = read_pdf(resume_path)
                if not raw_resume:
                    return jsonify({"error": f"Failed to read resume from {resume_path}"}), 400
            else:
                return jsonify({"error": "resume or resume_path is required"}), 400
        
        if not raw_job_description:
            return jsonify({"error": "job_description is required"}), 400
        
        result = resume_improvement_prompt(
            raw_job_description, extracted_job_keywords, raw_resume,
            extracted_resume_keywords, ats_recommendations, skill_priority_text,
            current_cosine_similarity, base_url, model
        )
        if result is None:
            return jsonify({"error": "Failed to improve resume from Ollama"}), 500
        
        return jsonify({"improved_resume": result}), 200
    except Exception as e:
        print(f"Error in resume_improvement_prompt API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/save-analysis', methods=['POST'])
def save_analysis():
    """API endpoint to save analysis to history"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        analysis_data = data.get('analysis_data')
        
        if not job_id or not analysis_data:
            return jsonify({"error": "job_id and analysis_data are required"}), 400
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO analysis_history (job_id, analysis_data) VALUES (?, ?)",
            (job_id, analysis_data)
        )
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Analysis saved successfully"}), 200
    except Exception as e:
        print(f"Error saving analysis: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis-history/<int:job_id>', methods=['GET'])
def get_analysis_history(job_id):
    """API endpoint to get analysis history for a job"""
    try:
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, job_id, analysis_data, created_at FROM analysis_history WHERE job_id = ? ORDER BY created_at DESC",
            (job_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        analyses = []
        for row in rows:
            analyses.append({
                "id": row[0],
                "job_id": row[1],
                "analysis_data": row[2],
                "created_at": row[3]
            })
        
        return jsonify({"analyses": analyses}), 200
    except Exception as e:
        print(f"Error fetching analysis history: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/list-resumes', methods=['GET'])
def list_resumes():
    """API endpoint to list all PDF files in the root folder"""
    try:
        root_dir = os.path.dirname(os.path.abspath(__file__))
        pdf_files = glob.glob(os.path.join(root_dir, "*.pdf"))
        
        resumes = []
        for pdf_path in pdf_files:
            resumes.append({
                "name": os.path.basename(pdf_path),
                "path": pdf_path
            })
        
        # Also check if there's a resume_path in config
        if config.get("resume_path") and os.path.exists(config.get("resume_path")):
            config_resume = {
                "name": os.path.basename(config.get("resume_path")),
                "path": config.get("resume_path")
            }
            # Add if not already in list
            if config_resume not in resumes:
                resumes.append(config_resume)
        
        return jsonify({"resumes": resumes}), 200
    except Exception as e:
        print(f"Error listing resumes: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-full-analysis', methods=['POST'])
def run_full_analysis():
    """API endpoint to run all analysis steps sequentially"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        resume_path = data.get('resume_path', None)
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400
        
        # Get job description
        job = get_job_by_id(job_id, config)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        job_text = job.get('job_description', '')
        results = {
            "step1": None,
            "step2": None,
            "step3": None,
            "step4": None,
            "messages": []
        }
        
        # Step 1: Extract Job JSON
        results["messages"].append("Starting Step 1: Extracting Job JSON...")
        job_json = structured_job_prompt(job_text, base_url, model)
        if not job_json:
            return jsonify({"error": "Step 1 failed: Failed to extract job JSON", "results": results}), 500
        results["step1"] = job_json
        results["messages"].append("Step 1 completed: Job JSON extracted successfully")
        
        # Step 2: Extract Resume JSON
        results["messages"].append("Starting Step 2: Extracting Resume JSON...")
        if resume_path:
            resume_text = read_pdf(resume_path)
            if not resume_text:
                return jsonify({"error": f"Step 2 failed: Failed to read resume from {resume_path}", "results": results}), 400
        else:
            resume_path = config.get("resume_path", "")
            if resume_path:
                resume_text = read_pdf(resume_path)
                if not resume_text:
                    return jsonify({"error": f"Step 2 failed: Failed to read resume from {resume_path}", "results": results}), 400
            else:
                return jsonify({"error": "Step 2 failed: No resume path provided", "results": results}), 400
        
        resume_json = structured_resume_prompt(resume_text, base_url, model)
        if not resume_json:
            return jsonify({"error": "Step 2 failed: Failed to extract resume JSON", "results": results}), 500
        results["step2"] = resume_json
        results["messages"].append("Step 2 completed: Resume JSON extracted successfully")
        
        # Step 3: Match Analysis
        results["messages"].append("Starting Step 3: Performing Match Analysis...")
        job_keywords = job_json.get('keywords', []) if isinstance(job_json, dict) else []
        resume_keywords = resume_json.get('keywords', []) if isinstance(resume_json, dict) else []
        
        analysis_json = resume_analysis_prompt(
            job_json, resume_json, '',
            job_keywords, resume_keywords, 0.0, 0.0,
            base_url, model
        )
        if not analysis_json:
            return jsonify({"error": "Step 3 failed: Failed to generate analysis", "results": results}), 500
        results["step3"] = analysis_json
        results["messages"].append("Step 3 completed: Match analysis generated successfully")
        
        # Step 4: Resume Improvement (Optional)
        results["messages"].append("Starting Step 4: Improving Resume...")
        improved_resume = resume_improvement_prompt(
            job_text, job_keywords, resume_text,
            resume_keywords, '', '', 0.0,
            base_url, model
        )
        if improved_resume:
            results["step4"] = improved_resume
            results["messages"].append("Step 4 completed: Resume improvement generated successfully")
        else:
            results["messages"].append("Step 4 completed with warnings: Resume improvement may have failed")
        
        results["messages"].append("All steps completed successfully!")
        
        # Save analysis to history
        try:
            conn = sqlite3.connect(config["db_path"])
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO analysis_history (job_id, analysis_data) VALUES (?, ?)",
                (job_id, json.dumps(analysis_json))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to save analysis to history: {e}")
        
        return jsonify({"success": True, "results": results}), 200
    except Exception as e:
        print(f"Error in run_full_analysis: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    import sys
    verify_db_schema(config)  # Verify the DB schema before running the app
    app.run(debug=True, port=5001)
