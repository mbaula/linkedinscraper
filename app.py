from flask import Flask, render_template, jsonify, request, Response
import pandas as pd
import sqlite3
import json
import openai
from pdfminer.high_level import extract_text
from flask_cors import CORS
import threading
import subprocess
import os
import sys
import csv
import io
import requests
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT
from datetime import datetime

def load_config(file_name):
    # Load the config file
    with open(file_name) as f:
        return json.load(f)

config = load_config('config.json')
app = Flask(__name__)
CORS(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True

def read_pdf(file_path):
    try:
        text = extract_text(file_path)
        return text
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the PDF: {e}")
        return None

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
    return render_template('./templates/job_description.html', job=jobs[job_id])

@app.route('/get_all_jobs')
def get_all_jobs():
    conn = sqlite3.connect(config["db_path"])
    query = "SELECT * FROM jobs"
    df = pd.read_sql_query(query, conn)
    df = df.sort_values(by='id', ascending=False)
    df.reset_index(drop=True, inplace=True)
    jobs = df.to_dict('records')
    return jsonify(jobs)

@app.route('/job_details/<int:job_id>')
def job_details(job_id):
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job_tuple = cursor.fetchone()
    conn.close()
    if job_tuple is not None:
        # Get the column names from the cursor description
        column_names = [column[0] for column in cursor.description]
        # Create a dictionary mapping column names to row values
        job = dict(zip(column_names, job_tuple))
        return jsonify(job)
    else:
        return jsonify({"error": "Job not found"}), 404

@app.route('/hide_job/<int:job_id>', methods=['POST'])
def hide_job(job_id):
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET hidden = 1 WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": "Job marked as hidden"}), 200


@app.route('/mark_applied/<int:job_id>', methods=['POST'])
def mark_applied(job_id):
    print("Applied clicked!")
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    
    # Update jobs table
    query = "UPDATE jobs SET applied = 1 WHERE id = ?"
    print(f'Executing query: {query} with job_id: {job_id}')
    cursor.execute(query, (job_id,))
    
    # Get job details to auto-populate application
    cursor.execute("SELECT title, company, job_url, date FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    
    if job:
        title, company, job_url, job_date = job
        from datetime import datetime
        
        # Check if application already exists for this job
        cursor.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
        existing = cursor.fetchone()
        
        if not existing:
            # Create new application entry
            date_submitted = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO applications (job_id, company_name, application_status, role, date_submitted, link_to_job_req)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (job_id, company, 'Applied', title, date_submitted, job_url))
            print(f"Created application entry for job_id: {job_id}")
    
    conn.commit()
    conn.close()
    return jsonify({"success": "Job marked as applied"}), 200

@app.route('/unmark_applied/<int:job_id>', methods=['POST'])
def unmark_applied(job_id):
    """Unmark a job as applied"""
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    query = "UPDATE jobs SET applied = 0 WHERE id = ?"
    cursor.execute(query, (job_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": "Job unmarked as applied"}), 200

@app.route('/mark_interview/<int:job_id>', methods=['POST'])
def mark_interview(job_id):
    print("Interview clicked!")
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    query = "UPDATE jobs SET interview = 1 WHERE id = ?"
    print(f'Executing query: {query} with job_id: {job_id}')
    cursor.execute(query, (job_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": "Job marked as interview"}), 200

@app.route('/mark_rejected/<int:job_id>', methods=['POST'])
def mark_rejected(job_id):
    print("Rejected clicked!")
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    query = "UPDATE jobs SET rejected = 1 WHERE id = ?"
    print(f'Executing query: {query} with job_id: {job_id}')
    cursor.execute(query, (job_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": "Job marked as rejected"}), 200

@app.route('/get_cover_letter/<int:job_id>')
def get_cover_letter(job_id):
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT cover_letter FROM jobs WHERE id = ?", (job_id,))
    cover_letter = cursor.fetchone()
    conn.close()
    if cover_letter is not None:
        return jsonify({"cover_letter": cover_letter[0]})
    else:
        return jsonify({"error": "Cover letter not found"}), 404

@app.route('/get_resume/<int:job_id>', methods=['POST'])
def get_resume(job_id):
    print("Resume clicked!")
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT job_description, title, company FROM jobs WHERE id = ?", (job_id,))
    job_tuple = cursor.fetchone()
    if job_tuple is not None:
        # Get the column names from the cursor description
        column_names = [column[0] for column in cursor.description]
        # Create a dictionary mapping column names to row values
        job = dict(zip(column_names, job_tuple))
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

    query = "UPDATE jobs SET resume = ? WHERE id = ?"
    print(f'Executing query: {query} with job_id: {job_id} and resume: {response}')
    cursor.execute(query, (response, job_id))
    conn.commit()
    conn.close()
    return jsonify({"resume": response}), 200

def generate_cover_letter_with_ollama(prompt, base_url, model):
    """Generate cover letter using Ollama (free, local LLM)"""
    try:
        url = f"{base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        print(f"Calling Ollama API: {url} with model: {model}")
        response = requests.post(url, json=payload, timeout=180)
        if response.status_code == 200:
            result = response.json()
            if "response" in result:
                return result.get("response", "")
            else:
                print(f"Ollama response missing 'response' field: {result}")
                return None
        else:
            error_msg = f"Ollama API error: {response.status_code} - {response.text}"
            print(error_msg)
            # If model not found, suggest pulling it
            if response.status_code == 404:
                print(f"Model '{model}' not found. Try running: ollama pull {model}")
            return None
    except requests.exceptions.ConnectionError as e:
        print(f"Error connecting to Ollama at {base_url}. Make sure Ollama is running.")
        return None
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        return None

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

def format_cover_letter_for_latex(cover_letter_text):
    """
    Format cover letter text for LaTeX insertion.
    Extracts body paragraphs and formats them with \noindent and \vspace{1em}
    """
    if not cover_letter_text:
        return ""
    
    # Split into paragraphs (double newlines)
    paragraphs = cover_letter_text.split('\n\n')
    
    # Filter out empty paragraphs and common headers/footers
    body_paragraphs = []
    skip_patterns = [
        r'^Dear\s+',
        r'^Sincerely',
        r'^Best regards',
        r'^Regards',
        r'^Thank you for considering',
        r'^I look forward to',
        r'^Please feel free to contact',
        r'^Mark Baula$',
        r'^[A-Z][a-z]+\s+[A-Z][a-z]+$',  # Name signatures
    ]
    
    import re
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Skip if it matches a header/footer pattern
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, para, re.IGNORECASE):
                should_skip = True
                break
        
        if not should_skip and len(para) > 20:  # Only include substantial paragraphs
            # Escape LaTeX special characters
            para = para.replace('\\', '\\textbackslash{}')
            para = para.replace('&', '\\&')
            para = para.replace('%', '\\%')
            para = para.replace('$', '\\$')
            para = para.replace('#', '\\#')
            para = para.replace('^', '\\textasciicircum{}')
            para = para.replace('_', '\\_')
            para = para.replace('{', '\\{')
            para = para.replace('}', '\\}')
            para = para.replace('~', '\\textasciitilde{}')
            
            body_paragraphs.append(para)
    
    # Format for LaTeX
    latex_formatted = ""
    for para in body_paragraphs:
        latex_formatted += f"\\noindent {para} \\vspace{{1em}}\n\n"
    
    return latex_formatted.strip()

@app.route('/api/cover-letter/latex/<int:job_id>', methods=['GET'])
def get_cover_letter_latex(job_id):
    """Get LaTeX-formatted cover letter body for insertion into LaTeX document"""
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT cover_letter FROM jobs WHERE id = ?", (job_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return jsonify({"error": "Cover letter not found"}), 404
    
    cover_letter_text = result[0]
    latex_formatted = format_cover_letter_for_latex(cover_letter_text)
    
    return jsonify({"latex": latex_formatted, "full_text": cover_letter_text})

def escape_xml_text(text):
    """
    Escape special characters for XML/HTML (used by ReportLab Paragraph).
    Handles dashes, quotes, and other special characters properly.
    ReportLab's Paragraph uses XML/HTML markup, so we need to escape properly.
    """
    if not text:
        return ""
    
    # First, handle dashes - convert Unicode dashes to HTML entities or regular hyphens
    # Em dash (—) U+2014 -> HTML entity or regular hyphen
    text = text.replace('—', '-')  # Em dash to regular hyphen
    text = text.replace('–', '-')  # En dash to regular hyphen
    # Keep regular hyphens (-) as is
    
    # Escape XML/HTML special characters (must escape & first!)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    return text

@app.route('/api/cover-letter/pdf/<int:job_id>', methods=['GET'])
def generate_cover_letter_pdf(job_id):
    """Generate PDF of cover letter"""
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT cover_letter, title, company FROM jobs WHERE id = ?", (job_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return jsonify({"error": "Cover letter not found"}), 404
    
    cover_letter_text = result[0]
    job_title = result[1]
    company = result[2]
    
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

@app.route('/get_CoverLetter/<int:job_id>', methods=['POST'])
def get_CoverLetter(job_id):
    global cover_letter_status
    
    if cover_letter_status["running"]:
        return jsonify({"error": "Cover letter generation is already in progress"}), 400
    
    print("CoverLetter clicked!")
    update_cover_letter_status("Starting cover letter generation...", job_id, False)
    
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()

    cursor.execute("SELECT job_description, title, company FROM jobs WHERE id = ?", (job_id,))
    job_tuple = cursor.fetchone()
    if job_tuple is not None:
        column_names = [column[0] for column in cursor.description]
        job = dict(zip(column_names, job_tuple))
    else:
        conn.close()
        update_cover_letter_status("Error: Job not found", job_id, True)
        return jsonify({"error": "Job not found"}), 404
    
    update_cover_letter_status("Reading resume from PDF...", job_id, False)
    resume = read_pdf(config["resume_path"])

    # Check if resume is None
    if resume is None:
        conn.close()
        print("Error: Resume not found or couldn't be read.")
        update_cover_letter_status("Error: Resume not found or couldn't be read.", job_id, True)
        return jsonify({"error": "Resume not found or couldn't be read."}), 400

    provider = config.get("cover_letter_provider", "template").lower()
    consideration = ""
    
    update_cover_letter_status(f"Using {provider.upper()} provider to generate cover letter...", job_id, False)
    
    # Build the prompt with strict instructions to only use resume information
    user_prompt = ("CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume. If something is not in the resume, do not mention it.\n\nYou are a career coach helping a candidate write a cover letter. Write a cover letter for the position below using ONLY the information from the resume. Approach this in three steps:\n\nStep 1. Identify main challenges someone in this position would face based on the job description.\n\nStep 2. Write an attention-grabbing hook (100 words or less) that highlights ONLY the candidate's actual experience and qualifications from the resume. Use specific examples ONLY if they are mentioned in the resume. Do not invent examples or achievements.\n\nStep 3. Complete the cover letter (total 250 words) using ONLY information from the resume. Match the candidate's actual skills and experiences to the job requirements. Do not add any information not present in the resume.\n\nREMEMBER: Every skill, experience, achievement, and qualification you mention MUST be explicitly stated in the resume. If it's not in the resume, do not include it.\n\nJob Description: " + job['job_description'] + "\n\nCompany: " + job['company'] + "\n\nJob Title: " + job['title'] + "\n\nResume:\n" + resume)
    if consideration:
        user_prompt += "\nConsider incorporating that " + consideration

    response = None
    
    # Try to generate cover letter based on provider
    if provider == "ollama":
        ollama_url = config.get("ollama_base_url", "http://localhost:11434")
        ollama_model = config.get("ollama_model", "gpt-oss")
        print(f"Using Ollama provider with model {ollama_model}")
        update_cover_letter_status(f"Generating initial draft with Ollama ({ollama_model})...", job_id, False)
        response = generate_cover_letter_with_ollama(user_prompt, ollama_url, ollama_model)
        
        if response:
            update_cover_letter_status("Initial draft generated. Refining cover letter...", job_id, False)
            # Refinement step
            user_prompt2 = ("CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume.\n\nYou are helping improve a cover letter. Review the draft below and improve it while ensuring EVERY claim is backed by information in the resume.\n\nStep 1. Set formality: 1 = conversational, current draft = 10. Target formality = 7.\n\nStep 2. Identify 3-5 improvements, ensuring all examples come from the resume.\n\nStep 3. Rewrite the cover letter with formality = 7, using ONLY information from the resume. Remove any claims not supported by the resume. Avoid subjective qualifiers like 'drastic' or 'transformational'. Keep within 250 words.\n\nJob Description: " + job['job_description'] + "\n\nResume:\n" + resume + "\n\nCurrent Cover Letter Draft:\n" + response + "\n\nRespond with the improved cover letter only, ensuring all information comes from the resume.")
            refined = generate_cover_letter_with_ollama(user_prompt2, ollama_url, ollama_model)
            if refined:
                response = refined
                update_cover_letter_status("Cover letter refined successfully!", job_id, False)
                
    elif provider == "groq":
        groq_key = config.get("groq_api_key", "")
        if not groq_key:
            conn.close()
            update_cover_letter_status("Error: Groq API key not configured", job_id, True)
            return jsonify({"error": "Groq API key is not configured. Please add 'groq_api_key' to config.json or get a free key from https://console.groq.com"}), 400
        print("Using Groq provider")
        update_cover_letter_status("Generating initial draft with Groq...", job_id, False)
        response = generate_cover_letter_with_groq(user_prompt, groq_key)
        
        if response:
            update_cover_letter_status("Initial draft generated. Refining cover letter...", job_id, False)
            # Refinement step
            user_prompt2 = ("CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume.\n\nYou are helping improve a cover letter. Review the draft below and improve it while ensuring EVERY claim is backed by information in the resume.\n\nStep 1. Set formality: 1 = conversational, current draft = 10. Target formality = 7.\n\nStep 2. Identify 3-5 improvements, ensuring all examples come from the resume.\n\nStep 3. Rewrite the cover letter with formality = 7, using ONLY information from the resume. Remove any claims not supported by the resume. Avoid subjective qualifiers like 'drastic' or 'transformational'. Keep within 250 words.\n\nJob Description: " + job['job_description'] + "\n\nResume:\n" + resume + "\n\nCurrent Cover Letter Draft:\n" + response + "\n\nRespond with the improved cover letter only, ensuring all information comes from the resume.")
            refined = generate_cover_letter_with_groq(user_prompt2, groq_key)
            if refined:
                response = refined
                update_cover_letter_status("Cover letter refined successfully!", job_id, False)
                
    elif provider == "openai":
        openai_key = config.get("OpenAI_API_KEY", "")
        openai_model = config.get("OpenAI_Model", "gpt-3.5-turbo")
        if not openai_key:
            conn.close()
            update_cover_letter_status("Error: OpenAI API key is empty", job_id, True)
            return jsonify({"error": "OpenAI API key is empty."}), 400
        print("Using OpenAI provider")
        update_cover_letter_status(f"Generating initial draft with OpenAI ({openai_model})...", job_id, False)
        response = generate_cover_letter_with_openai(user_prompt, openai_key, openai_model)
        
        if response:
            update_cover_letter_status("Initial draft generated. Refining cover letter...", job_id, False)
            # Refinement step
            user_prompt2 = ("CRITICAL: You must ONLY use information that is explicitly stated in the resume provided below. DO NOT make up, invent, or assume any skills, experiences, achievements, or qualifications that are not directly mentioned in the resume.\n\nYou are helping improve a cover letter. Review the draft below and improve it while ensuring EVERY claim is backed by information in the resume.\n\nStep 1. Set formality: 1 = conversational, current draft = 10. Target formality = 7.\n\nStep 2. Identify 3-5 improvements, ensuring all examples come from the resume.\n\nStep 3. Rewrite the cover letter with formality = 7, using ONLY information from the resume. Remove any claims not supported by the resume. Avoid subjective qualifiers like 'drastic' or 'transformational'. Keep within 250 words.\n\nJob Description: " + job['job_description'] + "\n\nResume:\n" + resume + "\n\nCurrent Cover Letter Draft:\n" + response + "\n\nRespond with the improved cover letter only, ensuring all information comes from the resume.")
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
        conn.close()
        update_cover_letter_status(f"Error: Failed to generate cover letter using {provider} provider", job_id, True)
        return jsonify({"error": f"Failed to generate cover letter using {provider} provider."}), 500

    update_cover_letter_status("Saving cover letter to database...", job_id, False)
    query = "UPDATE jobs SET cover_letter = ? WHERE id = ?"
    print(f'Executing query: {query} with job_id: {job_id} and cover letter: {response}')
    cursor.execute(query, (response, job_id))
    conn.commit()
    conn.close()
    
    update_cover_letter_status("Cover letter generated successfully!", job_id, True)
    return jsonify({"cover_letter": response}), 200

def filter_jobs_by_config(jobs_list, config):
    """Apply config filters to jobs list (for existing jobs in database)"""
    filtered_jobs = jobs_list.copy()
    
    # Filter by title_exclude (case insensitive)
    title_exclude = config.get('title_exclude', [])
    if title_exclude and len(title_exclude) > 0:
        title_exclude = [word.strip().lower() for word in title_exclude if word and word.strip()]
        if title_exclude:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('title') and not any(
                    exclude_word in (job.get('title', '') or '').lower() 
                    for exclude_word in title_exclude
                )
            ]
    
    # Filter by title_include (case insensitive)
    title_include = config.get('title_include', [])
    if title_include and len(title_include) > 0:
        title_include = [word.strip().lower() for word in title_include if word and word.strip()]
        if title_include:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('title') and any(
                    include_word in (job.get('title', '') or '').lower() 
                    for include_word in title_include
                )
            ]
    
    # Filter by desc_words (case insensitive)
    desc_words = config.get('desc_words', [])
    if desc_words and len(desc_words) > 0:
        desc_words = [word.strip().lower() for word in desc_words if word and word.strip()]
        if desc_words:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('job_description') and not any(
                    desc_word in (job.get('job_description', '') or '').lower() 
                    for desc_word in desc_words
                )
            ]
    
    # Filter by company_exclude (case insensitive)
    company_exclude = config.get('company_exclude', [])
    if company_exclude and len(company_exclude) > 0:
        company_exclude = [word.strip().lower() for word in company_exclude if word and word.strip()]
        if company_exclude:
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('company') and not any(
                    company_word in (job.get('company', '') or '').lower() 
                    for company_word in company_exclude
                )
            ]
    
    return filtered_jobs

def read_jobs_from_db():
    # Reload config to get latest filter settings
    current_config = load_config('config.json')
    
    conn = sqlite3.connect(current_config["db_path"])
    query = "SELECT * FROM jobs WHERE hidden = 0"
    df = pd.read_sql_query(query, conn)
    df = df.sort_values(by='id', ascending=False)
    # df.reset_index(drop=True, inplace=True)
    jobs = df.to_dict('records')
    
    # Apply current config filters to existing jobs
    jobs = filter_jobs_by_config(jobs, current_config)
    
    return jobs

def verify_db_schema():
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()

    # Get the table information
    cursor.execute("PRAGMA table_info(jobs)")
    table_info = cursor.fetchall()
    column_names = [column[1] for column in table_info]

    # Check if the "cover_letter" column exists
    if "cover_letter" not in column_names:
        # If it doesn't exist, add it
        cursor.execute("ALTER TABLE jobs ADD COLUMN cover_letter TEXT")
        print("Added cover_letter column to jobs table")

    if "resume" not in column_names:
        # If it doesn't exist, add it
        cursor.execute("ALTER TABLE jobs ADD COLUMN resume TEXT")
        print("Added resume column to jobs table")

    # Check if the "source" column exists (for multi-source support)
    if "source" not in column_names:
        # If it doesn't exist, add it
        cursor.execute("ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'linkedin'")
        print("Added source column to jobs table")

    # Create applications table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            company_name TEXT NOT NULL,
            application_status TEXT DEFAULT 'Applied',
            role TEXT NOT NULL,
            salary TEXT,
            date_submitted TEXT,
            link_to_job_req TEXT,
            rejection_reason TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    conn.commit()
    print("Verified applications table exists")
    conn.close()

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
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, job_id, company_name, application_status, role, salary, 
                   date_submitted, link_to_job_req, rejection_reason, notes
            FROM applications
            ORDER BY date_submitted DESC, id DESC
        """)
        
        columns = [description[0] for description in cursor.description]
        applications = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return jsonify(applications)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications', methods=['POST'])
def create_application():
    """Create a new application"""
    try:
        data = request.json
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO applications (job_id, company_name, application_status, role, salary, 
                                     date_submitted, link_to_job_req, rejection_reason, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('job_id'),
            data.get('company_name', ''),
            data.get('application_status', 'Applied'),
            data.get('role', ''),
            data.get('salary', ''),
            data.get('date_submitted', ''),
            data.get('link_to_job_req', ''),
            data.get('rejection_reason', ''),
            data.get('notes', '')
        ))
        conn.commit()
        app_id = cursor.lastrowid
        conn.close()
        return jsonify({"success": True, "id": app_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    """Update an application"""
    try:
        data = request.json
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        
        from datetime import datetime
        cursor.execute("""
            UPDATE applications 
            SET company_name = ?, application_status = ?, role = ?, salary = ?,
                date_submitted = ?, link_to_job_req = ?, rejection_reason = ?, 
                notes = ?, updated_at = ?
            WHERE id = ?
        """, (
            data.get('company_name', ''),
            data.get('application_status', 'Applied'),
            data.get('role', ''),
            data.get('salary', ''),
            data.get('date_submitted', ''),
            data.get('link_to_job_req', ''),
            data.get('rejection_reason', ''),
            data.get('notes', ''),
            datetime.now().isoformat(),
            app_id
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    """Delete an application and unmark the job as applied"""
    try:
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        
        # Get the job_id before deleting
        cursor.execute("SELECT job_id FROM applications WHERE id = ?", (app_id,))
        result = cursor.fetchone()
        job_id = result[0] if result else None
        
        # Delete the application
        cursor.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        
        # Unmark the job as applied if it has a job_id
        if job_id:
            cursor.execute("UPDATE jobs SET applied = 0 WHERE id = ?", (job_id,))
        
        conn.commit()
        conn.close()
        return jsonify({"success": True, "job_id": job_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/applications/export', methods=['GET'])
def export_applications_csv():
    """Export all applications to CSV"""
    try:
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT company_name, application_status, role, salary, 
                   date_submitted, link_to_job_req, rejection_reason, notes
            FROM applications
            ORDER BY date_submitted DESC, id DESC
        """)
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Company Name', 'Application Status', 'Role', 'Salary',
            'Date Submitted', 'Link to Job Req', 'Rejection Reason', 'Notes'
        ])
        
        # Write data
        for row in cursor.fetchall():
            writer.writerow(row)
        
        conn.close()
        
        # Create response with CSV data
        output.seek(0)
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=applications_export.csv'
            }
        )
        return response
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

if __name__ == "__main__":
    import sys
    verify_db_schema()  # Verify the DB schema before running the app
    app.run(debug=True, port=5001)
