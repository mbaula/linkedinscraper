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
    "matching": ["string (keywords that appear in both job and resume)"],
    "missing": ["string (important job keywords that are missing from resume)"]
  }
}"""

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
}"""


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
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing analysis JSON: {e}")
        print(f"Response was: {response[:500]}")
        return None


def resume_improvement_prompt(raw_job_description, job_json, resume_json, keyword_analysis, base_url, model):
    """
    STEP 4: Generate Improvements Based on Keyword Analysis
    Generates overallFit, improvements, and aspirationalImprovements based on keyword matching from Step 3.
    """
    job_description = job_json.get("description", "") if isinstance(job_json, dict) else str(job_json)
    resume_text = json.dumps(resume_json, indent=2) if isinstance(resume_json, dict) else str(resume_json)
    
    matching_keywords = keyword_analysis.get('keywords', {}).get('matching', [])
    missing_keywords = keyword_analysis.get('keywords', {}).get('missing', [])
    
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

3. OPTIONAL: Provide 3-5 "aspirationalImprovements" - suggestions for what COULD be added if the candidate had certain experience. CRITICAL REQUIREMENTS:
   - These are hypothetical improvements - things that would help IF the candidate had this experience
   - Focus on critical missing keywords that cannot be addressed by rewriting existing content
   - Each should have a "suggestion" explaining what experience would be helpful
   - Each should have an "example" showing what a bullet point would look like IF they had that experience
   - These are separate from the "improvements" array - they're aspirational, not based on existing resume content

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
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(response)
        
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
        print("run_full_analysis called")
        data = request.get_json()
        print(f"Received data: {data}")
        job_id = data.get('job_id')
        resume_path = data.get('resume_path', None)
        base_url = data.get('base_url', config.get("ollama_base_url", "http://localhost:11434"))
        model = data.get('model', config.get("ollama_model", "llama3.2:latest"))
        
        if not job_id:
            print("Error: job_id is required")
            return jsonify({"error": "job_id is required"}), 400
        
        print(f"Processing job_id: {job_id}, resume_path: {resume_path}, model: {model}")
        
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
        
        # Step 2: Extract Resume JSON (with caching)
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
        
        # Check cache first
        resume_json = get_resume_cache(resume_path, config)
        if resume_json:
            results["messages"].append("Step 2 completed: Resume JSON loaded from cache")
        else:
            # Extract from PDF if not in cache
            resume_json = structured_resume_prompt(resume_text, base_url, model)
            if not resume_json:
                return jsonify({"error": "Step 2 failed: Failed to extract resume JSON", "results": results}), 500
            # Cache the result
            set_resume_cache(resume_path, resume_json, config)
            results["messages"].append("Step 2 completed: Resume JSON extracted successfully")
        
        results["step2"] = resume_json
        
        # Step 3: Match Analysis
        results["messages"].append("Starting Step 3: Performing Match Analysis...")
        job_keywords = job_json.get('keywords', []) if isinstance(job_json, dict) else []
        resume_keywords = resume_json.get('keywords', []) if isinstance(resume_json, dict) else []
        
        # Extract keywords from job title (critical for technical roles)
        if isinstance(job_json, dict) and 'title' in job_json:
            title = job_json['title'].lower()
            # Extract technical terms from title (e.g., "Mainframe COBOL Developer" -> ["mainframe", "cobol"])
            title_words = title.split()
            for word in title_words:
                # Remove common non-technical words
                if word not in ['developer', 'engineer', 'analyst', 'specialist', 'manager', 'lead', 'senior', 'junior', 'the', 'a', 'an']:
                    if len(word) > 2:  # Skip very short words
                        job_keywords.append(word)
        
        # Also extract keywords from skills and requirements if available
        if isinstance(job_json, dict):
            if 'skills' in job_json and isinstance(job_json['skills'], list):
                job_keywords.extend([s.lower() for s in job_json['skills'] if s])
            if 'requirements' in job_json and isinstance(job_json['requirements'], list):
                job_keywords.extend([r.lower() for r in job_json['requirements'] if r])
            # Extract from description as well (look for technical terms)
            if 'description' in job_json:
                desc = job_json['description'].lower()
                # Look for common technical terms in description
                tech_terms_in_desc = ['cobol', 'mainframe', 'java', 'python', 'javascript', 'sql', 'oracle', 'db2', 'jcl', 'cics']
                for term in tech_terms_in_desc:
                    if term in desc and term not in job_keywords:
                        job_keywords.append(term)
        
        if isinstance(resume_json, dict):
            if 'additional' in resume_json and 'technicalSkills' in resume_json['additional']:
                if isinstance(resume_json['additional']['technicalSkills'], list):
                    resume_keywords.extend([s.lower() for s in resume_json['additional']['technicalSkills'] if s])
        
        # Remove duplicates and normalize
        job_keywords = list(set([k.lower().strip() for k in job_keywords if k]))
        resume_keywords = list(set([k.lower().strip() for k in resume_keywords if k]))
        
        # Let AI prioritize technical keywords - don't filter here
        
        analysis_json = resume_analysis_prompt(
            job_json, resume_json,
            job_keywords, resume_keywords,
            base_url, model
        )
        if not analysis_json:
            return jsonify({"error": "Step 3 failed: Failed to generate analysis", "results": results}), 500
        
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
            keywords_data = analysis_json.get('keywords', {})
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
        if 'keywords' in analysis_json:
            final_matching = [kw for kw in analysis_json['keywords'].get('matching', []) if not is_soft_skill(kw)]
            final_missing = [kw for kw in analysis_json['keywords'].get('missing', []) if not is_soft_skill(kw)]
            analysis_json['keywords'] = {
                'matching': final_matching[:20],
                'missing': final_missing[:20]
            }
        
        # Ensure overallFit is always present with fallback values
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
        results["messages"].append("Step 3 completed: Match analysis generated successfully")
        
        # Step 4: Generate Improvements Based on Keyword Analysis
        results["messages"].append("Starting Step 4: Generating Improvements...")
        improvements_result = resume_improvement_prompt(
            job_text, job_json, resume_json, analysis_json, base_url, model
        )
        if improvements_result:
            results["step4"] = improvements_result
            results["messages"].append("Step 4 completed: Improvements generated successfully")
        else:
            results["messages"].append("Step 4 completed with warnings: Improvements may have failed")
        
        results["messages"].append("All steps completed successfully!")
        
        # Combine Step 3 (keywords) and Step 4 (improvements) for history
        combined_analysis = {
            "keywords": analysis_json.get('keywords', {}),
            "overallFit": improvements_result.get('overallFit', {}) if improvements_result else {},
            "improvements": improvements_result.get('improvements', []) if improvements_result else [],
            "aspirationalImprovements": improvements_result.get('aspirationalImprovements', []) if improvements_result else []
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
    except Exception as e:
        print(f"Error in run_full_analysis: {e}")
        return jsonify({"error": str(e)}), 500

