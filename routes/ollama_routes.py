"""
Ollama API routes blueprint.
"""
from flask import Blueprint, jsonify, request
import json
import re
import os
import glob
import sqlite3
from services.job_service import get_job_by_id
from utils.config_utils import load_config
from utils.pdf_utils import read_pdf

# Create blueprint
ollama_bp = Blueprint('ollama', __name__)

# Load config
config = load_config('config.json')


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


def call_ollama(prompt, base_url, model):
    """Generic function to call Ollama API"""
    import requests
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


@ollama_bp.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    """Fetch available Ollama models"""
    try:
        import requests
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


@ollama_bp.route('/api/ollama/structured-job', methods=['POST'])
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


@ollama_bp.route('/api/ollama/structured-resume', methods=['POST'])
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


@ollama_bp.route('/api/ollama/resume-analysis', methods=['POST'])
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


@ollama_bp.route('/api/ollama/resume-improvement', methods=['POST'])
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


@ollama_bp.route('/api/save-analysis', methods=['POST'])
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


@ollama_bp.route('/api/analysis-history/<int:job_id>', methods=['GET'])
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


@ollama_bp.route('/api/list-resumes', methods=['GET'])
def list_resumes():
    """API endpoint to list all PDF files in the root folder"""
    try:
        root_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(root_dir)  # Go up from routes/ to project root
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


@ollama_bp.route('/api/run-full-analysis', methods=['POST'])
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

