"""
Ollama API routes blueprint.
"""
from flask import Blueprint, jsonify, request, current_app
import json
import re
import os
import glob
import sqlite3
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.job_service import get_job_by_id
from utils.pdf_utils import read_pdf

# Create blueprint
ollama_bp = Blueprint('ollama', __name__)


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

# Step 3 Schema - Keyword Matching Only
KEYWORD_ANALYSIS_SCHEMA = """{
  "keywords": {
    "matching": ["python", "react", "kubernetes"],
    "missing": ["docker", "aws", "terraform"]
  }
}

IMPORTANT: Replace the example values above with actual keywords from the job description and resume. The "matching" array should contain actual technical keywords that appear in BOTH the job description AND the resume. The "missing" array should contain actual important technical keywords from the job description that are NOT found in the resume. DO NOT include the word "string" or placeholder text - only include real keywords."""

# Step 4 Schema - Improvements
IMPROVEMENTS_SCHEMA = """{
  "overallFit": {
    "details": "string",
    "commentary": "string"
  },
  "improvements": [
    {
      "suggestion": "string",
      "lineNumber": "number or null",
      "section": "string or null",
      "example": "string (provide a concrete example tailored to the candidate's actual experience from their resume)"
    }
  ],
  "aspirationalImprovements": [
    {
      "suggestion": "string (what could be added if the candidate had this experience)",
      "example": "string (example of what the bullet point would look like if they had this experience)"
    }
  ]
}

CRITICAL: The "improvements" array and "aspirationalImprovements" array are SEPARATE and MUST be kept separate. Do NOT mix them together."""


def get_resume_cache(resume_path, config):
    """
    Get cached resume JSON if it exists and file hasn't changed.
    Returns resume_json if cache is valid, None otherwise.
    """
    if not resume_path or not os.path.exists(resume_path):
        return None
    
    try:
        # Get file modification time and hash
        file_mtime = os.path.getmtime(resume_path)
        with open(resume_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT resume_json, file_mtime, file_hash FROM resume_cache WHERE resume_path = ?",
            (resume_path,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            cached_json, cached_mtime, cached_hash = row
            # Check if file hasn't changed (same hash and mtime)
            if cached_hash == file_hash and abs(cached_mtime - file_mtime) < 1.0:
                return json.loads(cached_json)
        
        return None
    except Exception as e:
        print(f"Error checking resume cache: {e}")
        return None


def set_resume_cache(resume_path, resume_json, config):
    """
    Store resume JSON in cache.
    """
    if not resume_path or not os.path.exists(resume_path):
        return
    
    try:
        # Get file modification time and hash
        file_mtime = os.path.getmtime(resume_path)
        with open(resume_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO resume_cache 
               (resume_path, file_hash, file_mtime, resume_json, updated_at) 
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (resume_path, file_hash, file_mtime, json.dumps(resume_json))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching resume: {e}")


def get_job_cache(job_description, config):
    """
    Get cached job JSON if it exists.
    Returns job_json if cache is valid, None otherwise.
    """
    if not job_description:
        return None
    
    try:
        # Create hash of job description
        job_hash = hashlib.md5(job_description.encode('utf-8')).hexdigest()
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT job_json FROM job_cache WHERE job_description_hash = ?",
            (job_hash,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        
        return None
    except Exception as e:
        print(f"Error checking job cache: {e}")
        return None


def set_job_cache(job_description, job_json, config):
    """
    Store job JSON in cache.
    """
    if not job_description:
        return
    
    try:
        # Create hash of job description
        job_hash = hashlib.md5(job_description.encode('utf-8')).hexdigest()
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO job_cache 
               (job_description_hash, job_json, updated_at) 
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (job_hash, json.dumps(job_json))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching job: {e}")


def is_soft_skill(keyword):
    """
    Check if a keyword is a soft skill or generic phrase that should be excluded.
    Returns True if it's a soft skill, False if it's technical.
    """
    if not keyword:
        return True
    
    kw_lower = keyword.lower().strip()
    
    # Soft skill patterns to exclude
    soft_skill_patterns = [
        'proactive', 'self-starter', 'self starter', 'accountability', 'accountable',
        'continuous improvement', 'embracing change', 'mentorship', 'mentoring',
        'risk management', 'risk appetite', 'culture', 'attitude', 'desire to learn',
        'learn and contribute', 'best practices', 'guiding', 'leading', 'collaboration',
        'teamwork', 'communication', 'problem solving', 'critical thinking',
        'adaptability', 'flexibility', 'initiative', 'creativity', 'innovation',
        'results-driven', 'results driven', 'purpose driven', 'high-performing',
        'inclusive', 'thrive on challenges', 'eager to learn', 'show initiative',
        'application support', 'pager rotation', '24x7', '24/7', 'participating in',
        'system implementation', 'implementing new systems', 'production support',
        'inclusive environment', 'contributing to', 'taking accountability'
    ]
    
    # Check if it matches any soft skill pattern
    return any(pattern in kw_lower for pattern in soft_skill_patterns)


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
    prompt = f"""You are a JSON-extraction engine. Extract REAL data from the job posting below and convert it into JSON.

CRITICAL REQUIREMENTS:
1. Extract ACTUAL values from the job posting - DO NOT use placeholder text like "string", "example", or schema descriptions
2. If a field is not found in the job posting, use an empty string "" or empty array [] (NOT the word "string")
3. Extract the real job title, company name, location, description, requirements, and skills from the text
4. Do not add any extra fields or prose
5. Use "YYYY-MM-DD" for all dates
6. Ensure any URLs (website, applyLink) conform to URI format
7. Output ONLY valid JSON - no Markdown formatting, no code blocks, no explanations

Schema:
```json
{JOB_SCHEMA}
```

IMPORTANT: The schema shows "string" as a TYPE description. You must replace "string" with ACTUAL extracted text from the job posting. For example:
- If the job title is "Software Engineer", use "Software Engineer" not "string"
- If the company is "Google", use "Google" not "string"
- If a field is missing, use "" (empty string) not "string"

Job Posting:
{raw_job_text}

Output ONLY the JSON object with real extracted values, no other text."""

    response = call_ollama(prompt, base_url, model)
    if not response:
        return None
    
    # Try to extract JSON from response (in case there's any markdown formatting)
    # First try to find JSON wrapped in code blocks
    code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response
    
    try:
        parsed_json = json.loads(json_str)
        # Validate that we got a dict with at least some content
        if not isinstance(parsed_json, dict):
            print(f"Error: Parsed JSON is not a dict, type: {type(parsed_json)}")
            return None
        
        # Clean up placeholder "string" values - replace with empty string or actual extracted data
        cleaned_json = {}
        for key, value in parsed_json.items():
            if isinstance(value, str) and value.lower().strip() == "string":
                # Replace placeholder "string" with empty string
                cleaned_json[key] = ""
            elif isinstance(value, list):
                # Clean list items
                cleaned_list = []
                for item in value:
                    if isinstance(item, str) and item.lower().strip() == "string":
                        continue  # Skip placeholder items
                    cleaned_list.append(item)
                cleaned_json[key] = cleaned_list
            else:
                cleaned_json[key] = value
        
        # Check if we have any meaningful data (not all empty/placeholder)
        has_data = any(
            (isinstance(v, str) and v.strip() and v.lower() != "string") or
            (isinstance(v, list) and len(v) > 0) or
            (not isinstance(v, (str, list)) and v)
            for v in cleaned_json.values()
        )
        
        if not has_data:
            print(f"Warning: Extracted job JSON contains only placeholder values")
            print(f"Raw JSON: {json.dumps(parsed_json, indent=2)[:500]}")
        
        # Log what we extracted for debugging
        print(f"Extracted job JSON - Title: '{cleaned_json.get('title', 'N/A')}', Company: '{cleaned_json.get('company', 'N/A')}'")
        return cleaned_json
    except json.JSONDecodeError as e:
        print(f"Error parsing job JSON: {e}")
        print(f"Response was: {response[:500]}")
        print(f"Attempted to parse: {json_str[:200]}")
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


def resume_analysis_prompt(job_json, resume_json, job_keywords, resume_keywords, base_url, model):
    """
    STEP 3: Job JSON + Resume JSON → Keyword Analysis
    Identifies matching and missing keywords between job and resume.
    """
    job_description = job_json.get("description", "") if isinstance(job_json, dict) else str(job_json)
    resume_text = json.dumps(resume_json, indent=2) if isinstance(resume_json, dict) else str(resume_json)
    job_keywords_str = ", ".join(job_keywords) if isinstance(job_keywords, list) else str(job_keywords)
    resume_keywords_str = ", ".join(resume_keywords) if isinstance(resume_keywords, list) else str(resume_keywords)
    
    prompt = f"""You are a keyword matching engine. Your ONLY task is to identify which technical keywords from the job description appear in the resume, and which important job keywords are missing.

CRITICAL REQUIREMENTS: 
- ONLY include technical skills, tools, technologies, programming languages, frameworks, methodologies, platforms, and domain-specific terms
- DO NOT include soft skills, behavioral traits, or generic phrases in the matching/missing lists
- EXCLUDE phrases like "proactive attitude", "self-starter", "continuous improvement", "mentorship", "risk management", "application support", "24x7", "pager rotation", "system implementation", "inclusive environment", etc.
- Focus EXCLUSIVELY on concrete technical terms like "COBOL", "Mainframe", "Java", "Python", "React", "Kubernetes", "Azure", "SQL", "Docker", etc.
- Include both exact matches and close variations (e.g., "React" matches "React.js", "Python" matches "Python 3")
- If the job title contains specific technologies (e.g., "COBOL Developer", "React Engineer"), those technologies MUST be included in the keyword analysis
- The matching and missing arrays should contain ONLY technical terms, not behavioral or operational phrases
- Prioritize the most critical/required keywords first in the missing array

STRICTLY emit JSON that matches the schema below with no extra keys, prose, or markdown.

CRITICAL: The "matching" and "missing" arrays must contain ACTUAL KEYWORDS (like "Python", "React", "Docker", "AWS"), NOT the literal word "string" or placeholder text. Replace the example values in the schema with real keywords from the job description and resume.

Schema:

{KEYWORD_ANALYSIS_SCHEMA}

Context:
Job Description:

{job_description}

Extracted Job Keywords:

{job_keywords_str}

Resume Keywords:

{resume_keywords_str}

Original Resume (JSON):

{resume_text}"""

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
        parsed = json.loads(json_str)
        # Ensure we return a dict, not a string or other type
        if not isinstance(parsed, dict):
            print(f"Error: Parsed JSON is not a dict, type: {type(parsed)}")
            print(f"Response was: {response[:500]}")
            return None
        return parsed
    except json.JSONDecodeError as e:
        print(f"Error parsing analysis JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None
    except Exception as e:
        print(f"Unexpected error parsing analysis JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None


def resume_improvement_prompt(raw_job_description, job_json, resume_json, keyword_analysis, base_url, model):
    """
    STEP 4: Generate Improvements Based on Keyword Analysis
    Generates overallFit, improvements, and aspirationalImprovements based on keyword matching from Step 3.
    """
    job_description = job_json.get("description", "") if isinstance(job_json, dict) else str(job_json)
    resume_text = json.dumps(resume_json, indent=2) if isinstance(resume_json, dict) else str(resume_json)
    
    # Validate keyword_analysis is a dict
    if not isinstance(keyword_analysis, dict):
        print(f"Error: keyword_analysis is not a dict, type: {type(keyword_analysis)}")
        if isinstance(keyword_analysis, str):
            try:
                keyword_analysis = json.loads(keyword_analysis)
            except:
                keyword_analysis = {'keywords': {'matching': [], 'missing': []}}
        else:
            keyword_analysis = {'keywords': {'matching': [], 'missing': []}}
    
    keywords_section = keyword_analysis.get('keywords', {}) if isinstance(keyword_analysis, dict) else {}
    if not isinstance(keywords_section, dict):
        keywords_section = {}
    
    matching_keywords = keywords_section.get('matching', []) if isinstance(keywords_section, dict) else []
    missing_keywords = keywords_section.get('missing', []) if isinstance(keywords_section, dict) else []
    
    matching_str = ", ".join(matching_keywords[:20]) if matching_keywords else "None identified"
    missing_str = ", ".join(missing_keywords[:20]) if missing_keywords else "None"
    
    prompt = f"""You are an ATS-focused resume analyst. Based on the keyword analysis below, provide comprehensive improvement recommendations.

Instructions:

1. REQUIRED: Summarize the overall fit in two short paragraphs (THIS IS MANDATORY - DO NOT SKIP):
   - details: Analyze the keyword match and explain what this means for the candidate's fit. Mention the biggest gaps and strengths.
   - commentary: Strategic advice on further improvements or positioning. This field is REQUIRED and must not be empty.
   The overallFit object is MANDATORY and must always be included in your response.

2. REQUIRED: Provide 5-8 highly specific, actionable improvement suggestions in the "improvements" array. CRITICAL REQUIREMENTS:
   - DO NOT suggest adding or modifying a summary/career summary section. Focus on work experience, projects, skills, and education only.
   - Each suggestion MUST ONLY reference SPECIFIC existing bullet points, projects, or experiences that ACTUALLY EXIST in the resume JSON
   - NEVER invent, fabricate, or suggest adding experience, technologies, tools, or achievements that are NOT explicitly mentioned in the resume JSON
   - Be extremely specific: mention the exact company, role, date, and bullet point number/position from their resume
   - MANDATORY: Each suggestion MUST include a complete "example" field with a fully rewritten bullet point that the candidate can copy and paste directly into their resume
   - The example must be a complete, polished bullet point that incorporates job-relevant keywords naturally, especially from the missing keywords list
   - Focus on incorporating missing keywords into existing bullet points where possible
   - ONLY suggest rewording or rephrasing existing content - NEVER suggest adding new experiences, tools, or technologies that don't appear in the resume
   - If a job requirement is missing from the resume, DO NOT suggest adding it in this section - save it for "aspirationalImprovements"
   - NEVER provide vague suggestions like "re-phrase X to emphasize Y" - you MUST provide the actual rewritten text in the example field
   - The "improvements" array is MANDATORY and must contain at least 5 suggestions - do not skip this section
   - CRITICAL: Put ONLY realistic improvements based on existing resume content in the "improvements" array

3. REQUIRED: Provide 3-5 "aspirationalImprovements" - suggestions for what COULD be added if the candidate had certain experience. CRITICAL REQUIREMENTS:
   - These are hypothetical improvements - things that would help IF the candidate had this experience
   - Focus on critical missing keywords that cannot be addressed by rewriting existing content
   - Each should have a "suggestion" explaining what experience would be helpful
   - Each should have an "example" showing what a bullet point would look like IF they had that experience
   - These are SEPARATE from the "improvements" array - they're aspirational, not based on existing resume content
   - CRITICAL: Put ONLY hypothetical/aspirational improvements in the "aspirationalImprovements" array
   - DO NOT put improvements based on existing resume content in this array - those belong in "improvements"
   - This array is for things the candidate DOESN'T have but WOULD help if they did

IMPORTANT: 
- Never suggest changes to summary, career summary, or personal summary sections. Focus exclusively on work experience bullets, projects, skills sections, and education.
- NEVER invent experience, tools, technologies, or achievements. Only work with what exists in the resume JSON.
- If a job requirement cannot be addressed by existing resume content, do not suggest adding it in "improvements" - use "aspirationalImprovements" instead.

CRITICAL: You MUST include ALL required fields in the JSON response:
- overallFit object with details and commentary - THIS IS MANDATORY AND MUST NEVER BE EMPTY OR OMITTED
- improvements array with at least 5-8 suggestions (ONLY based on existing resume content) - THIS IS MANDATORY, DO NOT SKIP OR LEAVE EMPTY
- aspirationalImprovements array (0-5 suggestions for hypothetical additions) - This is OPTIONAL

STRICTLY emit JSON that matches the schema below with no extra keys, prose, or markdown.

Schema:

{IMPROVEMENTS_SCHEMA}

Context:
Job Description:

{job_description}

Keyword Analysis:
- Matching Keywords (found in both job and resume): {matching_str}
- Missing Keywords (in job but not in resume): {missing_str}

Original Resume (JSON - use this to create tailored examples based on actual experience):

{resume_text}"""

    response = call_ollama(prompt, base_url, model)
    if not response:
        return None
    
        # Parse JSON response
    try:
        # Try to extract JSON from response
        import re
        # First try to find JSON wrapped in code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response
        
        result = json.loads(json_str)
        
        # Ensure result is a dict
        if not isinstance(result, dict):
            print(f"Error: Parsed JSON is not a dict, type: {type(result)}")
            print(f"Response was: {response[:500]}")
            return None
        
        # Ensure improvements and aspirationalImprovements are separate arrays
        if 'improvements' not in result:
            result['improvements'] = []
        if 'aspirationalImprovements' not in result:
            result['aspirationalImprovements'] = []
        
        # Validate that improvements is an array
        if not isinstance(result.get('improvements'), list):
            print(f"Warning: improvements is not a list, type: {type(result.get('improvements'))}")
            result['improvements'] = []
        
        # Validate that aspirationalImprovements is an array
        if not isinstance(result.get('aspirationalImprovements'), list):
            print(f"Warning: aspirationalImprovements is not a list, type: {type(result.get('aspirationalImprovements'))}")
            result['aspirationalImprovements'] = []
        
        # Log the structure for debugging
        improvements_count = len(result.get('improvements', []))
        aspirational_count = len(result.get('aspirationalImprovements', []))
        print(f"Step 4 result - Improvements: {improvements_count}, Aspirational: {aspirational_count}")
        
        # Ensure overallFit is always present
        if 'overallFit' not in result or not result.get('overallFit'):
            result['overallFit'] = {
                'details': 'Overall fit assessment is being generated. Please review the keyword analysis and improvements below.',
                'commentary': 'Continue reviewing the suggested improvements to enhance your resume alignment with this position.'
            }
        else:
            # Ensure both fields exist and are not empty
            if not result['overallFit'].get('details') or not str(result['overallFit'].get('details', '')).strip():
                result['overallFit']['details'] = 'The candidate shows alignment with some job requirements. Review the keyword analysis and improvements for specific areas to enhance.'
            if not result['overallFit'].get('commentary') or not str(result['overallFit'].get('commentary', '')).strip():
                result['overallFit']['commentary'] = 'Focus on implementing the suggested improvements to strengthen your application.'
        
        return result
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from resume_improvement_prompt: {e}")
        print(f"Response was: {response[:500]}")
        return None


@ollama_bp.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    """Fetch available Ollama models"""
    config = current_app.config['CONFIG']
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
    config = current_app.config['CONFIG']
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
    config = current_app.config['CONFIG']
    try:
        data = request.get_json()
        resume_text = data.get('resume_text', '')
        resume_path = data.get('resume_path', None)
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        # If resume_path provided, load from file; otherwise use resume_text
        if resume_path and not resume_text:
            # Check cache first
            cached_result = get_resume_cache(resume_path, config)
            if cached_result:
                return jsonify({"resume_json": cached_result, "cached": True}), 200
            
            resume_text = read_pdf(resume_path)
            if not resume_text:
                return jsonify({"error": f"Failed to read resume from {resume_path}"}), 400
        elif not resume_text:
            # Try to use default resume path from config
            resume_path = config.get("resume_path", "")
            if resume_path:
                # Check cache first
                cached_result = get_resume_cache(resume_path, config)
                if cached_result:
                    return jsonify({"resume_json": cached_result, "cached": True}), 200
                
                resume_text = read_pdf(resume_path)
                if not resume_text:
                    return jsonify({"error": f"Failed to read resume from {resume_path}"}), 400
            else:
                return jsonify({"error": "resume_text or resume_path is required"}), 400
        
        result = structured_resume_prompt(resume_text, base_url, model)
        if result is None:
            return jsonify({"error": "Failed to extract resume JSON from Ollama"}), 500
        
        # Cache the result if we have a resume_path
        if resume_path:
            set_resume_cache(resume_path, result, config)
        
        return jsonify({"resume_json": result, "cached": False}), 200
    except Exception as e:
        print(f"Error in structured_resume_prompt API: {e}")
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/ollama/resume-analysis', methods=['POST'])
def api_resume_analysis():
    """API endpoint for STEP 3: Job JSON + Resume JSON → Match Analysis JSON"""
    config = current_app.config['CONFIG']
    try:
        data = request.get_json()
        job_json = data.get('job_json', {})
        resume_json = data.get('resume_json', {})
        job_keywords = data.get('job_keywords', [])
        resume_keywords = data.get('resume_keywords', [])
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        if not job_json or not resume_json:
            return jsonify({"error": "job_json and resume_json are required"}), 400
        
        result = resume_analysis_prompt(
            job_json, resume_json,
            job_keywords, resume_keywords,
            base_url, model
        )
        if result is None:
            return jsonify({"error": "Failed to generate analysis from Ollama"}), 500
        
        # Ensure keywords section exists and is valid (validate/correct AI output)
        if 'keywords' not in result or not result.get('keywords'):
            # Calculate matching and missing keywords
            matching = []
            missing = []
            
            for job_kw in job_keywords:
                # Skip soft skills
                if is_soft_skill(job_kw):
                    continue
                    
                found = False
                for resume_kw in resume_keywords:
                    # Check for exact match or if one contains the other
                    if job_kw == resume_kw or job_kw in resume_kw or resume_kw in job_kw:
                        matching.append(job_kw)
                        found = True
                        break
                if not found:
                    missing.append(job_kw)
            
            result['keywords'] = {
                'matching': matching[:20],  # Limit to top 20
                'missing': missing[:20]     # Limit to top 20
            }
        else:
            # Validate that missing keywords are actually from the job, not the resume
            keywords_data = result.get('keywords', {})
            missing_from_ai = keywords_data.get('missing', [])
            matching_from_ai = keywords_data.get('matching', [])
            
            # Normalize job and resume keywords for comparison
            job_keywords_normalized = [k.lower().strip() for k in job_keywords]
            resume_keywords_normalized = [k.lower().strip() for k in resume_keywords]
            
            # Validate missing keywords - they should be from job, not resume, and NOT soft skills
            validated_missing = []
            for kw in missing_from_ai:
                # Skip soft skills
                if is_soft_skill(kw):
                    continue
                    
                kw_normalized = kw.lower().strip()
                # Check if this keyword is actually from the job
                is_from_job = any(job_kw == kw_normalized or job_kw in kw_normalized or kw_normalized in job_kw 
                                 for job_kw in job_keywords_normalized)
                # Check if it's NOT in the resume
                is_in_resume = any(resume_kw == kw_normalized or resume_kw in kw_normalized or kw_normalized in resume_kw 
                                  for resume_kw in resume_keywords_normalized)
                
                if is_from_job and not is_in_resume:
                    validated_missing.append(kw)
            
            # Validate matching keywords - they should be in both job and resume, and NOT soft skills
            validated_matching = []
            for kw in matching_from_ai:
                # Skip soft skills
                if is_soft_skill(kw):
                    continue
                    
                kw_normalized = kw.lower().strip()
                # Check if this keyword is in both job and resume
                is_in_job = any(job_kw == kw_normalized or job_kw in kw_normalized or kw_normalized in job_kw 
                               for job_kw in job_keywords_normalized)
                is_in_resume = any(resume_kw == kw_normalized or resume_kw in kw_normalized or kw_normalized in resume_kw 
                                  for resume_kw in resume_keywords_normalized)
                
                if is_in_job and is_in_resume:
                    validated_matching.append(kw)
            
            # If validation found issues, recalculate from scratch
            if len(validated_missing) < len(missing_from_ai) * 0.5 or len(validated_matching) < len(matching_from_ai) * 0.5:
                # AI data is incorrect, recalculate
                matching = []
                missing = []
                
                for job_kw in job_keywords:
                    found = False
                    for resume_kw in resume_keywords:
                        # Check for exact match or if one contains the other
                        if job_kw == resume_kw or job_kw in resume_kw or resume_kw in job_kw:
                            matching.append(job_kw)
                            found = True
                            break
                    if not found:
                        missing.append(job_kw)
                
                result['keywords'] = {
                    'matching': matching[:20],  # Limit to top 20
                    'missing': missing[:20]     # Limit to top 20
                }
            else:
                # Use validated data
                result['keywords'] = {
                    'matching': validated_matching[:20],
                    'missing': validated_missing[:20]
                }
        
        # Final pass: filter out any remaining soft skills that might have slipped through
        if 'keywords' in result:
            final_matching = [kw for kw in result['keywords'].get('matching', []) if not is_soft_skill(kw)]
            final_missing = [kw for kw in result['keywords'].get('missing', []) if not is_soft_skill(kw)]
            result['keywords'] = {
                'matching': final_matching[:20],
                'missing': final_missing[:20]
            }
        
        return jsonify({"analysis_json": result}), 200
    except Exception as e:
        print(f"Error in resume_analysis_prompt API: {e}")
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/ollama/resume-improvement', methods=['POST'])
def api_resume_improvement():
    """API endpoint for STEP 4: Resume Rewriter"""
    config = current_app.config['CONFIG']
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
        
        # Get job_json, resume_json, and keyword_analysis (from Steps 1, 2, 3)
        job_json = data.get('job_json', {})
        resume_json = data.get('resume_json', {})
        keyword_analysis = data.get('keyword_analysis', {})
        
        if not job_json or not resume_json or not keyword_analysis:
            return jsonify({"error": "job_json, resume_json, and keyword_analysis are required"}), 400
        
        result = resume_improvement_prompt(
            raw_job_description, job_json, resume_json, keyword_analysis, base_url, model
        )
        if result is None:
            return jsonify({"error": "Failed to generate improvements from Ollama"}), 500
        
        return jsonify({"improvements": result}), 200
    except Exception as e:
        print(f"Error in resume_improvement_prompt API: {e}")
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/save-analysis', methods=['POST'])
def save_analysis():
    """API endpoint to save analysis to history"""
    config = current_app.config['CONFIG']
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
    config = current_app.config['CONFIG']
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
    config = current_app.config['CONFIG']
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
    config = current_app.config['CONFIG']
    try:
        import traceback
        print("run_full_analysis called")
        
        # Validate config is a dict
        if not isinstance(config, dict):
            print(f"Error: config is not a dict, type: {type(config)}")
            return jsonify({"error": "Invalid configuration"}), 500
        
        data = request.get_json()
        if not isinstance(data, dict):
            print(f"Error: request.get_json() returned non-dict, type: {type(data)}")
            return jsonify({"error": "Invalid request data"}), 400
        
        print(f"Received data: {data}")
        job_id = data.get('job_id') if isinstance(data, dict) else None
        resume_path = data.get('resume_path', None) if isinstance(data, dict) else None
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434")) if isinstance(data, dict) and isinstance(config, dict) else "http://localhost:11434"
        model = data.get('model', config.get("ollama_model", "llama3.2:latest")) if isinstance(data, dict) and isinstance(config, dict) else "llama3.2:latest"
        
        if not job_id:
            print("Error: job_id is required")
            return jsonify({"error": "job_id is required"}), 400
        
        print(f"Processing job_id: {job_id}, resume_path: {resume_path}, model: {model}")
        
        # Start timing
        analysis_start_time = time.time()
        
        # Get job description
        job = get_job_by_id(job_id, config)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        # Validate job is a dict
        if isinstance(job, str):
            print(f"Error: get_job_by_id returned a string, not a dict. Value: {job[:200]}")
            return jsonify({"error": "Invalid job data format"}), 500
        
        if not isinstance(job, dict):
            print(f"Error: get_job_by_id returned non-dict, type: {type(job)}")
            return jsonify({"error": "Invalid job data format"}), 500
        
        job_text = job.get('job_description', '') if isinstance(job, dict) else ''
        if not job_text or not job_text.strip():
            return jsonify({"error": "Job description is empty"}), 400
        
        results = {
            "step1": None,
            "step2": None,
            "step3": None,
            "step4": None,
            "messages": [],
            "timings": {}
        }
        
        # Get faster model for extraction steps (Steps 1-2)
        # Use smaller/faster model for extraction, keep main model for analysis
        extraction_model = config.get("ollama_extraction_model", None)  # e.g., "llama3.2:1b" or "llama3.2:3b"
        if not extraction_model:
            # Fallback: use main model if no extraction model specified
            extraction_model = model
        
        # Determine resume path
        if not resume_path:
            resume_path = config.get("resume_path", "")
            if not resume_path:
                return jsonify({"error": "Step 2 failed: No resume path provided", "results": results}), 400
        
        # Helper functions for parallel execution
        def extract_job_json():
            """Extract job JSON with caching"""
            try:
                msg = "Starting Step 1: Extracting Job JSON..."
                # Check cache first
                job_json = get_job_cache(job_text, config)
                if job_json and isinstance(job_json, dict):
                    # Validate cached job JSON has meaningful content (not placeholder "string" values)
                    title = (job_json.get('title') or '').strip()
                    company = (job_json.get('company') or '').strip()
                    description = (job_json.get('description') or '').strip()
                    
                    # Check if values are actual data (not empty and not "string" placeholder)
                    has_real_data = (
                        (title and title.lower() != 'string') or
                        (company and company.lower() != 'string') or
                        (description and description.lower() != 'string')
                    )
                    
                    if has_real_data:
                        return job_json, True, "Step 1 completed: Job JSON loaded from cache"
                    else:
                        # Cached version is empty or has placeholder values, clear it and re-extract
                        print("Warning: Cached job JSON is empty or contains placeholder values, re-extracting...")
                        # Clear the cache
                        job_hash = hashlib.md5(job_text.encode('utf-8')).hexdigest()
                        conn = sqlite3.connect(config["db_path"])
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM job_cache WHERE job_description_hash = ?", (job_hash,))
                        conn.commit()
                        conn.close()
                
                # Extract from job text if not in cache
                job_json = structured_job_prompt(job_text, base_url, extraction_model)
                if not job_json:
                    return None, False, "Step 1 failed: Failed to extract job JSON"
                if not isinstance(job_json, dict):
                    print(f"Error: structured_job_prompt returned non-dict: {type(job_json)}")
                    return None, False, "Step 1 failed: Invalid job JSON format"
                
                # Validate extracted job JSON has meaningful content (not just placeholder "string" values)
                title = job_json.get('title', '').strip() if job_json.get('title') else ''
                company = job_json.get('company', '').strip() if job_json.get('company') else ''
                description = job_json.get('description', '').strip() if job_json.get('description') else ''
                
                # Check if values are actual data (not empty and not "string" placeholder)
                has_real_data = (
                    (title and title.lower() != 'string') or
                    (company and company.lower() != 'string') or
                    (description and description.lower() != 'string')
                )
                
                if not has_real_data:
                    print(f"Warning: Extracted job JSON appears to contain only placeholder values")
                    print(f"Title: '{title}', Company: '{company}', Description length: {len(description)}")
                    # Don't cache placeholder results
                    return job_json, False, "Step 1 completed: Job JSON extracted (may contain placeholder values - check extraction)"
                
                # Log the extracted job JSON for debugging
                print(f"Extracted job JSON - Title: {job_json.get('title', 'N/A')}, Company: {job_json.get('company', 'N/A')}")
                
                # Cache the result
                set_job_cache(job_text, job_json, config)
                return job_json, False, "Step 1 completed: Job JSON extracted successfully"
            except Exception as e:
                print(f"Error in extract_job_json: {e}")
                import traceback
                traceback.print_exc()
                return None, False, f"Step 1 failed: {str(e)}"
        
        def extract_resume_json():
            """Extract resume JSON with caching"""
            try:
                msg = "Starting Step 2: Extracting Resume JSON..."
                # Read PDF
                resume_text = read_pdf(resume_path)
                if not resume_text:
                    return None, False, "Step 2 failed: Failed to read resume PDF"
                
                # Check cache first
                resume_json = get_resume_cache(resume_path, config)
                if resume_json and isinstance(resume_json, dict):
                    return resume_json, True, "Step 2 completed: Resume JSON loaded from cache"
                
                # Extract from PDF if not in cache
                resume_json = structured_resume_prompt(resume_text, base_url, extraction_model)
                if not resume_json:
                    return None, False, "Step 2 failed: Failed to extract resume JSON"
                if not isinstance(resume_json, dict):
                    print(f"Error: structured_resume_prompt returned non-dict: {type(resume_json)}")
                    return None, False, "Step 2 failed: Invalid resume JSON format"
                # Cache the result
                set_resume_cache(resume_path, resume_json, config)
                return resume_json, False, "Step 2 completed: Resume JSON extracted successfully"
            except Exception as e:
                print(f"Error in extract_resume_json: {e}")
                import traceback
                traceback.print_exc()
                return None, False, f"Step 2 failed: {str(e)}"
        
        # Run Steps 1 and 2 in parallel
        results["messages"].append("Running Steps 1 and 2 in parallel...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            job_future = executor.submit(extract_job_json)
            resume_future = executor.submit(extract_resume_json)
            
            # Wait for both to complete
            job_result = job_future.result()
            resume_result = resume_future.result()
            
            # Unpack results
            if len(job_result) == 3:
                job_json, job_cached, job_msg = job_result
            else:
                # Fallback for old format
                job_json, job_cached = job_result
                job_msg = "Step 1 completed" if job_json else "Step 1 failed"
            
            if len(resume_result) == 3:
                resume_json, resume_cached, resume_msg = resume_result
            else:
                # Fallback for old format
                resume_json, resume_cached = resume_result
                resume_msg = "Step 2 completed" if resume_json else "Step 2 failed"
            
            # Add messages after parallel execution completes (thread-safe)
            results["messages"].append("Starting Step 1: Extracting Job JSON...")
            results["messages"].append(job_msg)
            # Extract step1 timing from message if available
            if job_cached:
                results["timings"]["step1"] = 0.01  # Cache hit is nearly instant
            else:
                # Try to extract time from message
                time_match = re.search(r'\((\d+\.\d+)s\)', job_msg)
                if time_match:
                    results["timings"]["step1"] = float(time_match.group(1))
            
            results["messages"].append("Starting Step 2: Extracting Resume JSON...")
            results["messages"].append(resume_msg)
            # Extract step2 timing from message if available
            if resume_cached:
                results["timings"]["step2"] = 0.01  # Cache hit is nearly instant
            else:
                # Try to extract time from message
                time_match = re.search(r'\((\d+\.\d+)s\)', resume_msg)
                if time_match:
                    results["timings"]["step2"] = float(time_match.group(1))
        
        # Check for errors and validate types
        if not job_json:
            return jsonify({"error": "Step 1 failed: Failed to extract job JSON", "results": results}), 500
        if not resume_json:
            return jsonify({"error": "Step 2 failed: Failed to extract resume JSON", "results": results}), 500
        
        # Validate that we got dictionaries, not strings
        if isinstance(job_json, str):
            print(f"Error: job_json is a string, not a dict. Value: {job_json[:200]}")
            return jsonify({"error": "Step 1 failed: Invalid job JSON format", "results": results}), 500
        if isinstance(resume_json, str):
            print(f"Error: resume_json is a string, not a dict. Value: {resume_json[:200]}")
            return jsonify({"error": "Step 2 failed: Invalid resume JSON format", "results": results}), 500
        
        if not isinstance(job_json, dict):
            print(f"Error: job_json is not a dict, type: {type(job_json)}")
            return jsonify({"error": "Step 1 failed: Invalid job JSON format", "results": results}), 500
        if not isinstance(resume_json, dict):
            print(f"Error: resume_json is not a dict, type: {type(resume_json)}")
            return jsonify({"error": "Step 2 failed: Invalid resume JSON format", "results": results}), 500
        
        results["step1"] = job_json
        results["step2"] = resume_json
        
        # Step 3: Keyword Analysis
        step3_start = time.time()
        results["messages"].append("Starting Step 3: Performing Keyword Analysis...")
        
        # CRITICAL: Double-check types before any .get() calls
        if not isinstance(job_json, dict):
            print(f"CRITICAL ERROR: job_json is not a dict at Step 3 start, type: {type(job_json)}, value: {str(job_json)[:200]}")
            return jsonify({"error": "Step 3 failed: Invalid job JSON format", "results": results}), 500
        if not isinstance(resume_json, dict):
            print(f"CRITICAL ERROR: resume_json is not a dict at Step 3 start, type: {type(resume_json)}, value: {str(resume_json)[:200]}")
            return jsonify({"error": "Step 3 failed: Invalid resume JSON format", "results": results}), 500
        
        job_keywords = job_json.get('keywords', []) if isinstance(job_json, dict) else []
        resume_keywords = resume_json.get('keywords', []) if isinstance(resume_json, dict) else []
        
        # Extract keywords from job title (critical for technical roles)
        if isinstance(job_json, dict) and 'title' in job_json:
            title_value = job_json.get('title', '')
            if not isinstance(title_value, str):
                title_value = str(title_value)
            title = title_value.lower()
            # Extract technical terms from title (e.g., "Mainframe COBOL Developer" -> ["mainframe", "cobol"])
            title_words = title.split()
            for word in title_words:
                # Remove common non-technical words
                if word not in ['developer', 'engineer', 'analyst', 'specialist', 'manager', 'lead', 'senior', 'junior', 'the', 'a', 'an']:
                    if len(word) > 2:  # Skip very short words
                        job_keywords.append(word)
        
        # Also extract keywords from skills and requirements if available
        if isinstance(job_json, dict):
            if 'skills' in job_json and isinstance(job_json.get('skills'), list):
                job_keywords.extend([s.lower() for s in job_json['skills'] if s])
            if 'requirements' in job_json and isinstance(job_json.get('requirements'), list):
                job_keywords.extend([r.lower() for r in job_json['requirements'] if r])
            # Extract from description as well (look for technical terms)
            if 'description' in job_json:
                desc = job_json.get('description', '')
                if not isinstance(desc, str):
                    desc = str(desc)
                desc = desc.lower()
                # Look for common technical terms in description
                tech_terms_in_desc = ['cobol', 'mainframe', 'java', 'python', 'javascript', 'sql', 'oracle', 'db2', 'jcl', 'cics']
                for term in tech_terms_in_desc:
                    if term in desc and term not in job_keywords:
                        job_keywords.append(term)
        
        if isinstance(resume_json, dict):
            additional = resume_json.get('additional', {})
            if isinstance(additional, dict) and 'technicalSkills' in additional:
                tech_skills = additional.get('technicalSkills', [])
                if isinstance(tech_skills, list):
                    resume_keywords.extend([s.lower() for s in tech_skills if s])
        
        # Remove duplicates and normalize
        job_keywords = list(set([k.lower().strip() for k in job_keywords if k]))
        resume_keywords = list(set([k.lower().strip() for k in resume_keywords if k]))
        
        # Let AI prioritize technical keywords - don't filter here
        
        analysis_json = resume_analysis_prompt(
            job_json, resume_json,
            job_keywords, resume_keywords,
            base_url, model
        )
        step3_time = time.time() - step3_start
        
        # Validate analysis_json is a dict
        if not analysis_json:
            return jsonify({"error": f"Step 3 failed: Failed to generate analysis ({step3_time:.2f}s)", "results": results}), 500
        
        if isinstance(analysis_json, str):
            print(f"Error: analysis_json is a string, not a dict. Value: {analysis_json[:200]}")
            return jsonify({"error": f"Step 3 failed: Invalid analysis JSON format ({step3_time:.2f}s)", "results": results}), 500
        
        if not isinstance(analysis_json, dict):
            print(f"Error: analysis_json is not a dict, type: {type(analysis_json)}")
            return jsonify({"error": f"Step 3 failed: Invalid analysis JSON format ({step3_time:.2f}s)", "results": results}), 500
        
        results["timings"]["step3"] = step3_time
        
        # Ensure keywords section exists and is valid (fallback if AI doesn't provide it or provides incorrect data)
        if 'keywords' not in analysis_json or not analysis_json['keywords']:
            # Calculate matching and missing keywords
            matching = []
            missing = []
            
            for job_kw in job_keywords:
                # Skip soft skills
                if is_soft_skill(job_kw):
                    continue
                    
                found = False
                for resume_kw in resume_keywords:
                    # Check for exact match or if one contains the other
                    if job_kw == resume_kw or job_kw in resume_kw or resume_kw in job_kw:
                        matching.append(job_kw)
                        found = True
                        break
                if not found:
                    missing.append(job_kw)
            
            analysis_json['keywords'] = {
                'matching': matching[:20],  # Limit to top 20
                'missing': missing[:20]     # Limit to top 20
            }
        else:
            # Validate that missing keywords are actually from the job, not the resume
            # If AI returned incorrect data, recalculate
            keywords_data = analysis_json.get('keywords', {}) if isinstance(analysis_json, dict) else {}
            if not isinstance(keywords_data, dict):
                keywords_data = {}
            missing_from_ai = keywords_data.get('missing', []) if isinstance(keywords_data, dict) else []
            matching_from_ai = keywords_data.get('matching', []) if isinstance(keywords_data, dict) else []
            
            # Filter out placeholder strings like "string", "string (description)", etc.
            def is_valid_keyword(kw):
                if not isinstance(kw, str):
                    return False
                kw_lower = kw.lower().strip()
                # Filter out placeholder text
                if kw_lower in ['string', 'string (description)', 'string (keywords)', 'example', 'placeholder']:
                    return False
                # Filter out strings that are clearly schema descriptions
                if 'string (' in kw_lower or '(string' in kw_lower:
                    return False
                # Must be a real keyword (at least 2 characters, not just whitespace)
                return len(kw_lower) >= 2
            
            missing_from_ai = [kw for kw in missing_from_ai if is_valid_keyword(kw)]
            matching_from_ai = [kw for kw in matching_from_ai if is_valid_keyword(kw)]
            
            # Normalize job and resume keywords for comparison
            job_keywords_normalized = [k.lower().strip() for k in job_keywords]
            resume_keywords_normalized = [k.lower().strip() for k in resume_keywords]
            
            # Validate missing keywords - they should be from job, not resume, and NOT soft skills
            validated_missing = []
            for kw in missing_from_ai:
                # Skip soft skills
                if is_soft_skill(kw):
                    continue
                    
                kw_normalized = kw.lower().strip()
                # Check if this keyword is actually from the job
                is_from_job = any(job_kw == kw_normalized or job_kw in kw_normalized or kw_normalized in job_kw 
                                 for job_kw in job_keywords_normalized)
                # Check if it's NOT in the resume
                is_in_resume = any(resume_kw == kw_normalized or resume_kw in kw_normalized or kw_normalized in resume_kw 
                                  for resume_kw in resume_keywords_normalized)
                
                if is_from_job and not is_in_resume:
                    validated_missing.append(kw)
            
            # Validate matching keywords - they should be in both job and resume, and NOT soft skills
            validated_matching = []
            for kw in matching_from_ai:
                # Skip soft skills
                if is_soft_skill(kw):
                    continue
                    
                kw_normalized = kw.lower().strip()
                # Check if this keyword is in both job and resume
                is_in_job = any(job_kw == kw_normalized or job_kw in kw_normalized or kw_normalized in job_kw 
                               for job_kw in job_keywords_normalized)
                is_in_resume = any(resume_kw == kw_normalized or resume_kw in kw_normalized or kw_normalized in resume_kw 
                                  for resume_kw in resume_keywords_normalized)
                
                if is_in_job and is_in_resume:
                    validated_matching.append(kw)
            
            # If validation found issues, recalculate from scratch
            if len(validated_missing) < len(missing_from_ai) * 0.5 or len(validated_matching) < len(matching_from_ai) * 0.5:
                # AI data is incorrect, recalculate
                matching = []
                missing = []
                
                for job_kw in job_keywords:
                    # Skip soft skills
                    if is_soft_skill(job_kw):
                        continue
                        
                    found = False
                    for resume_kw in resume_keywords:
                        # Check for exact match or if one contains the other
                        if job_kw == resume_kw or job_kw in resume_kw or resume_kw in job_kw:
                            matching.append(job_kw)
                            found = True
                            break
                    if not found:
                        missing.append(job_kw)
                
                analysis_json['keywords'] = {
                    'matching': matching[:20],  # Limit to top 20
                    'missing': missing[:20]     # Limit to top 20
                }
            else:
                # Use validated data (already filtered for soft skills)
                analysis_json['keywords'] = {
                    'matching': validated_matching[:20],
                    'missing': validated_missing[:20]
                }
        
        # Final pass: filter out any remaining soft skills that might have slipped through
        if isinstance(analysis_json, dict) and 'keywords' in analysis_json:
            keywords_section = analysis_json['keywords']
            if isinstance(keywords_section, dict):
                final_matching = [kw for kw in keywords_section.get('matching', []) if not is_soft_skill(kw)]
                final_missing = [kw for kw in keywords_section.get('missing', []) if not is_soft_skill(kw)]
                analysis_json['keywords'] = {
                    'matching': final_matching[:20],
                    'missing': final_missing[:20]
                }
        
        # Ensure overallFit is always present with fallback values
        if not isinstance(analysis_json, dict):
            analysis_json = {'keywords': {'matching': [], 'missing': []}, 'overallFit': {}}
        
        if 'overallFit' not in analysis_json or not analysis_json.get('overallFit'):
            analysis_json['overallFit'] = {
                'details': 'Overall fit assessment is being generated. Please review the keyword analysis and improvements below.',
                'commentary': 'Continue reviewing the suggested improvements to enhance your resume alignment with this position.'
            }
        else:
            # Ensure both fields exist and are not empty
            if not analysis_json['overallFit'].get('details') or not str(analysis_json['overallFit'].get('details', '')).strip():
                analysis_json['overallFit']['details'] = 'The candidate shows alignment with some job requirements. Review the keyword analysis and improvements for specific areas to enhance.'
            if not analysis_json['overallFit'].get('commentary') or not str(analysis_json['overallFit'].get('commentary', '')).strip():
                analysis_json['overallFit']['commentary'] = 'Focus on implementing the suggested improvements to strengthen your application.'
        
        results["step3"] = analysis_json
        results["messages"].append(f"Step 3 completed: Keyword analysis generated successfully ({step3_time:.2f}s)")
        
        # Step 4: Generate Improvements Based on Keyword Analysis
        step4_start = time.time()
        results["messages"].append("Starting Step 4: Generating Improvements...")
        improvements_result = resume_improvement_prompt(
            job_text, job_json, resume_json, analysis_json, base_url, model
        )
        step4_time = time.time() - step4_start
        
        # Validate improvements_result is a dict if it exists
        if improvements_result:
            if isinstance(improvements_result, str):
                print(f"Error: improvements_result is a string, not a dict. Value: {improvements_result[:200]}")
                improvements_result = None  # Treat as failed
            elif not isinstance(improvements_result, dict):
                print(f"Error: improvements_result is not a dict, type: {type(improvements_result)}")
                improvements_result = None  # Treat as failed
        
        results["timings"]["step4"] = step4_time
        if improvements_result and isinstance(improvements_result, dict):
            results["step4"] = improvements_result
            results["messages"].append(f"Step 4 completed: Improvements generated successfully ({step4_time:.2f}s)")
        else:
            results["messages"].append(f"Step 4 completed with warnings: Improvements may have failed ({step4_time:.2f}s)")
        
        # Calculate total time
        total_time = time.time() - analysis_start_time
        results["timings"]["total"] = total_time
        results["messages"].append(f"All steps completed successfully! Total time: {total_time:.2f}s")
        print(f"Analysis completed in {total_time:.2f}s (Step 1: {results['timings'].get('step1', 'N/A')}s, Step 2: {results['timings'].get('step2', 'N/A')}s, Step 3: {step3_time:.2f}s, Step 4: {step4_time:.2f}s)")
        
        # Combine Step 3 (keywords) and Step 4 (improvements) for history
        # Ensure all values are safe to access
        keywords_section = analysis_json.get('keywords', {}) if isinstance(analysis_json, dict) else {}
        overall_fit = {}
        improvements_list = []
        aspirational_improvements = []
        
        if improvements_result and isinstance(improvements_result, dict):
            overall_fit = improvements_result.get('overallFit', {}) if isinstance(improvements_result.get('overallFit'), dict) else {}
            improvements_list = improvements_result.get('improvements', []) if isinstance(improvements_result.get('improvements'), list) else []
            aspirational_improvements = improvements_result.get('aspirationalImprovements', []) if isinstance(improvements_result.get('aspirationalImprovements'), list) else []
        
        combined_analysis = {
            "keywords": keywords_section if isinstance(keywords_section, dict) else {},
            "overallFit": overall_fit,
            "improvements": improvements_list,
            "aspirationalImprovements": aspirational_improvements
        }
        
        # Save analysis to history
        try:
            conn = sqlite3.connect(config["db_path"])
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO analysis_history (job_id, analysis_data) VALUES (?, ?)",
                (job_id, json.dumps(combined_analysis))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to save analysis to history: {e}")
        
        return jsonify({"success": True, "results": results}), 200
    except AttributeError as e:
        if "'str' object has no attribute 'get'" in str(e) or "'str' object has no attribute" in str(e):
            print(f"CRITICAL ERROR in run_full_analysis: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Type error: Attempted to call .get() on a string. This should never happen. Full error: {str(e)}"}), 500
        raise
    except Exception as e:
        print(f"Error in run_full_analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

