"""
Cover letter generation and export routes blueprint.
"""
from flask import Blueprint, jsonify, Response, request, current_app
import requests
import openai
import json
from datetime import datetime
import io
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

from services.job_service import get_job_by_id, get_job_field, update_job_field
from utils.pdf_utils import read_pdf
from utils.text_utils import (
    format_cover_letter_for_latex,
    escape_xml_text,
    normalize_dashes_for_docx,
    post_process_cover_letter
)
from routes.shared_state import cover_letter_status, update_cover_letter_status

# Create blueprint
cover_letter_bp = Blueprint('cover_letter', __name__)


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


@cover_letter_bp.route('/get_cover_letter/<int:job_id>')
def get_cover_letter(job_id):
    config = current_app.config['CONFIG']
    cover_letter = get_job_field(job_id, 'cover_letter', config)
    if cover_letter is not None:
        return jsonify({"cover_letter": cover_letter})
    else:
        return jsonify({"error": "Cover letter not found"}), 404


@cover_letter_bp.route('/api/cover-letter/status', methods=['GET'])
def get_cover_letter_status():
    """Get current cover letter generation status"""
    return jsonify(cover_letter_status)


@cover_letter_bp.route('/api/cover-letter/latex/<int:job_id>', methods=['GET'])
def get_cover_letter_latex(job_id):
    """Get LaTeX-formatted cover letter body for insertion into LaTeX document"""
    config = current_app.config['CONFIG']
    cover_letter_text = get_job_field(job_id, 'cover_letter', config)
    
    if not cover_letter_text:
        return jsonify({"error": "Cover letter not found"}), 404
    
    latex_formatted = format_cover_letter_for_latex(cover_letter_text)
    
    return jsonify({"latex": latex_formatted, "full_text": cover_letter_text})


@cover_letter_bp.route('/api/cover-letter/docx/<int:job_id>', methods=['GET'])
def generate_cover_letter_docx(job_id):
    """Generate DOCX of cover letter"""
    config = current_app.config['CONFIG']
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


@cover_letter_bp.route('/api/cover-letter/pdf/<int:job_id>', methods=['GET'])
def generate_cover_letter_pdf(job_id):
    """Generate PDF of cover letter"""
    config = current_app.config['CONFIG']
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


@cover_letter_bp.route('/get_CoverLetter/<int:job_id>', methods=['POST'])
def get_CoverLetter(job_id):
    config = current_app.config['CONFIG']
    
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
            from utils.config_utils import load_config
            with open('config.json', 'r', encoding='utf-8') as f:
                current_config = json.load(f)
            current_config['ollama_model'] = selected_model
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(current_config, f, indent=4)
            # Reload config in app context
            current_app.config['CONFIG'] = load_config('config.json')
            config = current_app.config['CONFIG']
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

