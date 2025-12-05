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

# Combined Step 3+4 Schema - Keywords + Improvements
IMPROVEMENTS_SCHEMA = """{
  "keywords": {
    "matching": ["python", "react", "kubernetes"],
    "missing": ["docker", "aws", "terraform"]
  },
  "overallFit": {
    "details": "The candidate demonstrates strong alignment through Python and React experience, but lacks Docker and AWS which are critical for this role.",
    "commentary": "Focus on incorporating Docker and AWS keywords into existing bullet points. Consider highlighting any cloud or containerization experience."
  },
  "improvements": [
    {
      "suggestion": "Add Docker to the CIBC DevOps role description",
      "lineNumber": null,
      "section": "workExperience",
      "example": "Reduced loading times by 90% for the centralized microservice portal using Docker containerization, removing legacy NAS and database logging configurations across 30+ microservices"
    }
  ],
  "aspirationalImprovements": [
    {
      "suggestion": "If you had AWS experience, add: 'Deployed microservices to AWS ECS using Docker containers'",
      "example": "Deployed and managed 30+ microservices on AWS ECS using Docker containers, reducing infrastructure costs by 40% through auto-scaling and load balancing"
    }
  ]
}

IMPORTANT: Replace ALL example values with actual data from the job and resume. The "example" field in improvements MUST be a complete rewritten bullet point, not just a suggestion."""


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


def get_job_cache(job_description, config, job_title=None, job_company=None):
    """
    Get cached job JSON if it exists.
    Uses composite key: job_title + job_company + job_description
    Returns job_json if cache is valid, None otherwise.
    """
    if not job_description:
        return None
    
    try:
        # Create composite hash from title, company, and description
        # Normalize empty strings to None for consistent hashing
        title_str = (job_title or '').strip() if job_title else ''
        company_str = (job_company or '').strip() if job_company else ''
        desc_str = job_description.strip() if job_description else ''
        
        # Create individual hashes
        title_hash = hashlib.md5(title_str.encode('utf-8')).hexdigest()
        company_hash = hashlib.md5(company_str.encode('utf-8')).hexdigest()
        desc_hash = hashlib.md5(desc_str.encode('utf-8')).hexdigest()
        
        # Composite cache key: title_hash_company_hash_desc_hash
        cache_key = f"{title_hash}_{company_hash}_{desc_hash}"
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT job_json FROM job_cache WHERE cache_key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        
        return None
    except Exception as e:
        print(f"Error checking job cache: {e}")
        return None


def set_job_cache(job_description, job_json, config, job_title=None, job_company=None):
    """
    Store job JSON in cache.
    Uses composite key: job_title + job_company + job_description
    """
    if not job_description:
        return
    
    try:
        # Create composite hash from title, company, and description
        # Normalize empty strings to None for consistent hashing
        title_str = (job_title or '').strip() if job_title else ''
        company_str = (job_company or '').strip() if job_company else ''
        desc_str = job_description.strip() if job_description else ''
        
        # Create individual hashes
        title_hash = hashlib.md5(title_str.encode('utf-8')).hexdigest()
        company_hash = hashlib.md5(company_str.encode('utf-8')).hexdigest()
        desc_hash = hashlib.md5(desc_str.encode('utf-8')).hexdigest()
        
        # Composite cache key: title_hash_company_hash_desc_hash
        cache_key = f"{title_hash}_{company_hash}_{desc_hash}"
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO job_cache 
               (cache_key, job_title_hash, job_company_hash, job_description_hash, job_json, updated_at) 
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (cache_key, title_hash, company_hash, desc_hash, json.dumps(job_json))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching job: {e}")


def get_keyword_analysis_cache(job_description, resume_path, config):
    """
    Get cached keyword analysis if it exists.
    Returns analysis_json if cache is valid, None otherwise.
    Uses composite key: job_description_hash + resume_path_hash
    """
    if not job_description or not resume_path:
        return None
    
    try:
        # Create hashes
        job_hash = hashlib.md5(job_description.encode('utf-8')).hexdigest()
        resume_hash = hashlib.md5(resume_path.encode('utf-8')).hexdigest()
        # Composite cache key
        cache_key = f"{job_hash}_{resume_hash}"
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT analysis_json FROM keyword_analysis_cache WHERE cache_key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        
        return None
    except Exception as e:
        print(f"Error checking keyword analysis cache: {e}")
        return None


def set_keyword_analysis_cache(job_description, resume_path, analysis_json, config):
    """
    Store keyword analysis in cache.
    Uses composite key: job_description_hash + resume_path_hash
    """
    if not job_description or not resume_path or not analysis_json:
        return
    
    try:
        # Create hashes
        job_hash = hashlib.md5(job_description.encode('utf-8')).hexdigest()
        resume_hash = hashlib.md5(resume_path.encode('utf-8')).hexdigest()
        # Composite cache key
        cache_key = f"{job_hash}_{resume_hash}"
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO keyword_analysis_cache 
               (cache_key, job_description_hash, resume_path_hash, analysis_json, updated_at) 
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (cache_key, job_hash, resume_hash, json.dumps(analysis_json))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching keyword analysis: {e}")


def extract_essential_job_info(job_text):
    """
    Extract only essential information from job description, removing boilerplate.
    Keeps: Title, About/Summary, Responsibilities, Requirements, Preferred qualifications
    Removes: Benefits, Company info, Legal text, Contact info, Closing statements
    Uses a less aggressive approach to preserve important content.
    """
    if not job_text:
        return job_text
    
    # Keep first 500 chars (usually contains title, company, location, and intro)
    first_part = job_text[:500] if len(job_text) > 500 else job_text
    
    # Patterns for sections to remove (more specific to avoid removing important content)
    remove_patterns = [
        r'(?i)(what\'s\s*in\s*it\s*for\s*you|benefits\s*package|compensation\s*package|perks\s*and\s*benefits)[:.]?\s*.+?(?=\n\n(?:Location|$)|$)',
        r'(?i)(about\s*(?:the\s*)?company[^:]*:|company\s*overview[^:]*:|who\s*we\s*are[^:]*:)[:.]?\s*.+?(?=\n\n(?:Location|$)|$)',
        r'(?i)(location\(s\)[^:]*:|work\s*location[^:]*:)[:.]?\s*.+?(?=\n\n|$)',
        r'(?i)(equal\s*opportunity|accommodation|accessibility|diversity\s*statement)[:.]?\s*.+?(?=\n\n|$)',
        r'(?i)(we\s*thank\s*all\s*applicants|candidates\s*must\s*apply\s*directly|candidates\s*must\s*apply\s*online).+?(?=\n\n|$)',
        r'(?i)(requisition\s*id|job\s*id|posting\s*id)[:.]?\s*[^\n]+',
        r'(?i)(scotiabank\s*is\s*a\s*leading|guided\s*by\s*our\s*purpose)[:.]?\s*.+?(?=\n\n|$)',
    ]
    
    # Remove unwanted sections from the rest of the text
    rest_of_text = job_text[500:] if len(job_text) > 500 else ""
    cleaned_rest = rest_of_text
    for pattern in remove_patterns:
        cleaned_rest = re.sub(pattern, '', cleaned_rest, flags=re.DOTALL | re.IGNORECASE)
    
    # Combine first part with cleaned rest
    result = first_part + cleaned_rest
    
    # Limit total length to 3000 chars to speed up processing
    if len(result) > 3000:
        result = result[:3000] + "..."
    
    return result


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


def call_ollama(prompt, base_url, model, num_predict=None, temperature=None, top_p=None, top_k=None):
    """
    Generic function to call Ollama API with optimized parameters for speed.
    
    Args:
        prompt: The prompt to send to the model
        base_url: Ollama base URL
        model: Model name to use
        num_predict: Maximum number of tokens to generate (limits output length for speed)
        temperature: Sampling temperature (0.1-0.3 for extraction, 0.3-0.5 for analysis)
        top_p: Nucleus sampling parameter (0.9 is a good default)
        top_k: Top-k sampling parameter (40 is a good default)
    """
    import requests
    try:
        url = f"{base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        # Add optimization parameters if provided
        # Ollama API expects options at the top level, not nested
        options = {}
        if num_predict is not None:
            options["num_predict"] = num_predict
        if temperature is not None:
            options["temperature"] = temperature
        if top_p is not None:
            options["top_p"] = top_p
        if top_k is not None:
            options["top_k"] = top_k
        
        if options:
            payload["options"] = options
        
        print(f"DEBUG: Sending request to Ollama API: {url}")
        print(f"DEBUG: Payload keys: {list(payload.keys())}, model={payload.get('model')}, has_options={bool(payload.get('options'))}")
        if payload.get('options'):
            print(f"DEBUG: Options: {payload['options']}")
        
        response = requests.post(url, json=payload, timeout=300)
        print(f"DEBUG: Ollama API response status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            result = response_data.get("response", "").strip()
            
            # Some models (like gpt-oss) may return thinking in a separate field
            # If response is empty but thinking exists, use thinking as fallback
            if not result:
                thinking = response_data.get("thinking", "").strip()
                if thinking:
                    print(f"WARNING: Response field is empty, but thinking field exists. Using thinking field.")
                    result = thinking
                else:
                    print(f"ERROR: Ollama API returned 200 but response is empty.")
                    print(f"ERROR: Full response_data keys: {list(response_data.keys())}")
                    print(f"ERROR: response_data content: {str(response_data)[:500]}")
                    return None
            
            print(f"DEBUG: Ollama API response length: {len(result)} chars, first 200 chars: {result[:200]}")
            return result
        else:
            print(f"ERROR: Ollama API error: {response.status_code} - {response.text[:500]}")
            print(f"ERROR: Request URL: {url}")
            print(f"ERROR: Request model: {payload.get('model')}")
            print(f"ERROR: Request prompt length: {len(payload.get('prompt', ''))} chars")
            return None
    except requests.exceptions.Timeout as e:
        print(f"ERROR: Ollama API timeout after 300s: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Ollama API request exception: {e}")
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error connecting to Ollama: {e}")
        import traceback
        traceback.print_exc()
        return None


def structured_job_prompt(raw_job_text, base_url, model, job_title=None, job_company=None, job_location=None):
    """
    STEP 1: Job Posting → Job JSON
    Converts raw job posting text into structured JSON using Ollama.
    
    Args:
        raw_job_text: Full job description text
        base_url: Ollama base URL
        model: Model name to use
        job_title: Optional job title from database (to help extraction)
        job_company: Optional company name from database (to help extraction)
        job_location: Optional location from database (to help extraction)
    
    Returns:
        dict: Extracted job JSON, or None if extraction fails
    """
    if not raw_job_text or not raw_job_text.strip():
        print("ERROR: structured_job_prompt called with empty raw_job_text")
        return None
    
    # Extract only essential info to speed up processing
    essential_job_text = extract_essential_job_info(raw_job_text)
    if not essential_job_text or not essential_job_text.strip():
        print("ERROR: extract_essential_job_info returned empty text")
        # Fallback to original text if extraction fails
        essential_job_text = raw_job_text[:2000]  # Limit to 2000 chars
    
    # Add title, company, and location context if provided (from database)
    context_info = ""
    if job_title:
        context_info += f"Job Title: {job_title}\n"
    if job_company:
        context_info += f"Company: {job_company}\n"
    if job_location:
        context_info += f"Location: {job_location}\n"
    if context_info:
        context_info = context_info + "\n"
    
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

{context_info}Job Posting:
{essential_job_text}

Output ONLY the JSON object with real extracted values, no other text."""

    # Step 1: Extraction - use lower temperature and limit tokens for speed
    print(f"Step 1: Calling Ollama with model={model}, base_url={base_url}")
    print(f"Step 1: Prompt length={len(prompt)} chars, essential_job_text length={len(essential_job_text)} chars")
    try:
        response = call_ollama(prompt, base_url, model, 
                              num_predict=1500,     # Increased to prevent JSON truncation
                              temperature=0.2,       # Low temperature for consistent extraction
                              top_p=0.9,            # Nucleus sampling for faster inference
                              top_k=40)             # Top-k sampling for faster inference
        if not response:
            print("ERROR: Step 1 - call_ollama returned None (no response from API)")
            # Create fallback JSON from database values
            print("WARNING: Step 1 - Creating fallback JSON from database values due to API failure")
            fallback_json = {
                "title": job_title or "",
                "company": job_company or "",
                "location": job_location or "",
                "description": essential_job_text[:500] if essential_job_text else "",
                "requirements": [],
                "skills": [],
                "keywords": []
            }
            print(f"Step 1: Returning fallback JSON with title='{fallback_json['title']}', company='{fallback_json['company']}'")
            return fallback_json
        print(f"Step 1: Received response from Ollama, length={len(response)} chars")
    except Exception as e:
        print(f"ERROR: Step 1 - Exception in call_ollama: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Try to extract JSON from response (in case there's any markdown formatting)
    # First try to find JSON wrapped in code blocks (use greedy match to capture full JSON)
    code_block_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # JSON might be incomplete - try to find starting brace and fix it
            json_match = re.search(r'\{.*', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Try to fix incomplete JSON by finding balanced braces
                # Count braces to find the last valid closing brace
                brace_count = 0
                last_valid_pos = -1
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            last_valid_pos = i
                            break
                
                if last_valid_pos > 0:
                    # We found a balanced JSON structure
                    json_str = json_str[:last_valid_pos + 1]
                else:
                    # No balanced structure found - try to close it manually
                    # This is a fallback - add closing brace if missing
                    if json_str.strip() and not json_str.strip().endswith('}'):
                        json_str = json_str.rstrip() + '\n}'
            else:
                # No JSON found at all - use entire response
                json_str = response
    
    try:
        parsed_json = json.loads(json_str)
        # Validate that we got a dict with at least some content
        if not isinstance(parsed_json, dict):
            print(f"ERROR: Step 1 - Parsed JSON is not a dict, type: {type(parsed_json)}")
            print(f"ERROR: Step 1 - JSON string was: {json_str[:500]}")
            # Create fallback JSON
            print("WARNING: Step 1 - Creating fallback JSON from database values")
            return {
                "title": job_title or "",
                "company": job_company or "",
                "location": job_location or "",
                "description": essential_job_text[:500] if essential_job_text else "",
                "requirements": [],
                "skills": [],
                "keywords": []
            }
        print(f"Step 1: Successfully parsed JSON, got {len(parsed_json)} keys")
    except json.JSONDecodeError as e:
        print(f"ERROR: Step 1 - JSON decode error: {e}")
        print(f"ERROR: Step 1 - Response was: {response[:1000]}")
        print(f"ERROR: Step 1 - Extracted JSON string was: {json_str[:1000]}")
        # Try to create a minimal valid JSON as fallback
        print("WARNING: Step 1 - Attempting to create fallback JSON from database values")
        fallback_json = {
            "title": job_title or "",
            "company": job_company or "",
            "location": job_location or "",
            "description": essential_job_text[:500] if essential_job_text else "",
            "requirements": [],
            "skills": [],
            "keywords": []
        }
        print(f"Step 1: Returning fallback JSON with title='{fallback_json['title']}', company='{fallback_json['company']}'")
        parsed_json = fallback_json  # Use fallback instead of returning None
    
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


def repair_incomplete_json(json_str):
    """
    Attempts to repair incomplete/truncated JSON by closing unclosed structures.
    Returns the repaired JSON string, or None if repair is not possible.
    """
    if not json_str or not json_str.strip():
        return None
    
    # First pass: analyze the structure to find where we are
    brace_depth = 0
    bracket_depth = 0
    in_string = False
    escape_next = False
    last_valid_pos = -1
    
    for i, char in enumerate(json_str):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char == '{':
            brace_depth += 1
        elif char == '}':
            brace_depth -= 1
            if brace_depth == 0 and bracket_depth == 0:
                last_valid_pos = i
        elif char == '[':
            bracket_depth += 1
        elif char == ']':
            bracket_depth -= 1
            if brace_depth == 0 and bracket_depth == 0:
                last_valid_pos = i
    
    # If we found a complete structure, use it
    if last_valid_pos > 0:
        return json_str[:last_valid_pos + 1]
    
    # Second pass: repair the incomplete JSON
    repaired = json_str.rstrip()
    
    # If we're in the middle of a string, find where that incomplete element started
    # and remove it entirely
    if in_string:
        # Work backwards to find the opening quote of this incomplete string
        temp_escape = False
        string_start = -1
        for i in range(len(repaired) - 1, -1, -1):
            char = repaired[i]
            if temp_escape:
                temp_escape = False
                continue
            if char == '\\':
                temp_escape = True
                continue
            if char == '"' and not temp_escape:
                string_start = i
                break
        
        if string_start > 0:
            # Check if there's a comma before this incomplete string element
            # Look backwards for comma, bracket, or brace (not in string)
            truncate_pos = string_start
            temp_in_string = False
            temp_escape2 = False
            for i in range(string_start - 1, -1, -1):
                char = repaired[i]
                if temp_escape2:
                    temp_escape2 = False
                    continue
                if char == '\\':
                    temp_escape2 = True
                    continue
                if char == '"' and not temp_escape2:
                    temp_in_string = not temp_in_string
                    continue
                if not temp_in_string:
                    if char == ',':
                        truncate_pos = i
                        break
                    elif char in '[{':
                        # We've reached the start of the array/object, truncate here
                        truncate_pos = i + 1  # Keep the opening bracket/brace
                        break
            
            # Truncate to remove the incomplete string element
            repaired = repaired[:truncate_pos].rstrip()
            # Remove trailing comma if present
            if repaired.endswith(','):
                repaired = repaired[:-1].rstrip()
    
    # Remove any trailing comma
    repaired = re.sub(r',\s*$', '', repaired)
    
    # Close arrays first (they're usually nested inside objects)
    while bracket_depth > 0:
        repaired += ']'
        bracket_depth -= 1
    
    # Close objects
    while brace_depth > 0:
        repaired += '}'
        brace_depth -= 1
    
    return repaired


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

    # Step 2: Extraction - use lower temperature but allow more tokens for complete JSON
    print(f"Step 2: Calling Ollama with model={model}, base_url={base_url}")
    print(f"Step 2: Resume text length={len(resume_text)} chars, prompt length={len(prompt)} chars")
    try:
        # Use higher token limit for resume extraction (resumes can be long)
        # Try 3000 tokens first, but some models may have limits
        response = call_ollama(prompt, base_url, model,
                              num_predict=3000,     # Increased further to prevent JSON truncation
                              temperature=0.2,      # Low temperature for consistent extraction
                              top_p=0.9,            # Nucleus sampling for faster inference
                              top_k=40)             # Top-k sampling for faster inference
    except Exception as e:
        print(f"ERROR: Step 2 - Exception calling call_ollama: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    if not response:
        print("ERROR: Step 2 - call_ollama returned None (no response from API)")
        print(f"ERROR: This usually means:")
        print(f"  1. Ollama API returned an error (check server logs above)")
        print(f"  2. The model '{model}' doesn't exist (run 'ollama list' to check)")
        print(f"  3. Ollama service is not running")
        print(f"  4. The prompt was too long (current length: {len(prompt)} chars)")
        return None
    
    print(f"Step 2: Received response from Ollama, length={len(response)} chars")
    
    # Try to extract JSON from response (similar to Step 1)
    # First try to find JSON wrapped in code blocks (use greedy match to capture full JSON)
    code_block_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # JSON might be incomplete - try to find starting brace and fix it
            json_match = re.search(r'\{.*', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Try to fix incomplete JSON by finding balanced braces
                # Count braces to find the last valid closing brace
                brace_count = 0
                last_valid_pos = -1
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            last_valid_pos = i
                            break
                
                if last_valid_pos > 0:
                    # We found a balanced JSON structure
                    json_str = json_str[:last_valid_pos + 1]
                else:
                    # No balanced structure found - try to close it manually
                    # This is a fallback - add closing brace if missing
                    if json_str.strip() and not json_str.strip().endswith('}'):
                        json_str = json_str.rstrip() + '\n}'
            else:
                # No JSON found at all - use entire response
                json_str = response
    
    try:
        parsed_json = json.loads(json_str)
        if not isinstance(parsed_json, dict):
            print(f"ERROR: Step 2 - Parsed JSON is not a dict, type: {type(parsed_json)}")
            print(f"ERROR: Step 2 - JSON string was: {json_str[:500]}")
            return None
        print(f"Step 2: Successfully parsed JSON, got {len(parsed_json)} top-level keys")
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"ERROR: Step 2 - JSON decode error: {e}")
        print(f"ERROR: Step 2 - Response was: {response[:1000]}")
        print(f"ERROR: Step 2 - Extracted JSON string was: {json_str[:1000]}")
        
        # Try to repair incomplete JSON
        if "Unterminated string" in str(e) or "Expecting" in str(e):
            print(f"WARNING: Step 2 - JSON appears to be truncated. Attempting to repair...")
            repaired_json = repair_incomplete_json(json_str)
            if repaired_json:
                try:
                    parsed_json = json.loads(repaired_json)
                    if isinstance(parsed_json, dict):
                        print(f"SUCCESS: Step 2 - Successfully repaired and parsed truncated JSON")
                        print(f"Step 2: Successfully parsed JSON, got {len(parsed_json)} top-level keys")
                        return parsed_json
                    else:
                        print(f"ERROR: Step 2 - Repaired JSON is not a dict, type: {type(parsed_json)}")
                except json.JSONDecodeError as repair_error:
                    print(f"ERROR: Step 2 - First repair attempt failed: {repair_error}")
                    # Try a more aggressive repair: remove the last incomplete element more aggressively
                    print(f"WARNING: Step 2 - Attempting more aggressive repair...")
                    # Find the last complete array element by looking for pattern: "complete string",\n
                    # This is a simpler heuristic: find the last line that ends with ", and is a complete string
                    lines = repaired_json.split('\n')
                    repaired_lines = []
                    found_incomplete = False
                    for line in lines:
                        line_stripped = line.strip()
                        # If we find a line that looks like an incomplete string (starts with " but doesn't end with ",)
                        if found_incomplete:
                            continue  # Skip incomplete lines
                        if line_stripped.startswith('"') and not line_stripped.endswith('",') and not line_stripped.endswith('"'):
                            # This might be the start of an incomplete string
                            # Check if previous line was complete
                            if repaired_lines and repaired_lines[-1].strip().endswith('",'):
                                # Previous was complete, skip this incomplete one
                                found_incomplete = True
                                continue
                        repaired_lines.append(line)
                    
                    if found_incomplete:
                        # Reconstruct and try to close structures
                        aggressive_repair = '\n'.join(repaired_lines).rstrip()
                        # Remove trailing comma
                        aggressive_repair = re.sub(r',\s*$', '', aggressive_repair)
                        # Close arrays and objects (count them)
                        brace_count = aggressive_repair.count('{') - aggressive_repair.count('}')
                        bracket_count = aggressive_repair.count('[') - aggressive_repair.count(']')
                        aggressive_repair += ']' * bracket_count + '}' * brace_count
                        
                        try:
                            parsed_json = json.loads(aggressive_repair)
                            if isinstance(parsed_json, dict):
                                print(f"SUCCESS: Step 2 - Aggressive repair succeeded")
                                print(f"Step 2: Successfully parsed JSON, got {len(parsed_json)} top-level keys")
                                return parsed_json
                        except:
                            pass
                    
                    print(f"ERROR: Step 2 - Could not repair JSON after multiple attempts")
                    print(f"ERROR: Step 2 - Last repair attempt result: {repaired_json[:1000]}")
                except Exception as repair_error:
                    print(f"ERROR: Step 2 - Unexpected error repairing JSON: {repair_error}")
            else:
                print(f"ERROR: Step 2 - Could not repair JSON. Consider increasing num_predict or using a model with longer context.")
        return None
    except Exception as e:
        print(f"ERROR: Step 2 - Unexpected error parsing JSON: {e}")
        print(f"ERROR: Step 2 - Response was: {response[:1000] if response else 'No response'}")
        import traceback
        traceback.print_exc()
        return None


def resume_analysis_prompt(job_json, resume_json, job_keywords, resume_keywords, base_url, model):
    """
    STEP 3: Job JSON + Resume JSON → Keyword Analysis
    Identifies matching and missing keywords between job and resume.
    """
    # Extract only essential info from job description to speed up processing
    job_description_full = job_json.get("description", "") if isinstance(job_json, dict) else str(job_json)
    job_description = extract_essential_job_info(job_description_full)
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

    # Step 3: Keyword Analysis - moderate temperature and token limit
    response = call_ollama(prompt, base_url, model,
                          num_predict=2000,     # Increased to prevent truncation for keyword analysis
                          temperature=0.3,      # Moderate temperature for analysis
                          top_p=0.9,            # Nucleus sampling for faster inference
                          top_k=40)             # Top-k sampling for faster inference
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


def resume_improvement_prompt(raw_job_description, job_json, resume_json, job_keywords, resume_keywords, base_url, model):
    """
    COMBINED STEP 3+4: Keyword Analysis + Improvements
    First identifies matching and missing keywords, then generates overallFit, improvements, and aspirationalImprovements.
    """
    # Validate input types
    if not isinstance(job_json, dict):
        print(f"ERROR: resume_improvement_prompt - job_json is not a dict, type: {type(job_json)}")
        raise TypeError(f"job_json must be a dict, got {type(job_json)}")
    if not isinstance(resume_json, dict):
        print(f"ERROR: resume_improvement_prompt - resume_json is not a dict, type: {type(resume_json)}")
        raise TypeError(f"resume_json must be a dict, got {type(resume_json)}")
    
    # Ensure job_keywords and resume_keywords are lists
    if not isinstance(job_keywords, list):
        print(f"WARNING: resume_improvement_prompt - job_keywords is not a list, type: {type(job_keywords)}, converting...")
        if isinstance(job_keywords, dict):
            # If it's a dict (like keyword_analysis from old API), extract keywords
            if 'matching' in job_keywords and isinstance(job_keywords['matching'], list):
                job_keywords = job_keywords['matching']
            else:
                job_keywords = []
        elif isinstance(job_keywords, str):
            job_keywords = [job_keywords] if job_keywords else []
        else:
            job_keywords = []
    
    if not isinstance(resume_keywords, list):
        print(f"WARNING: resume_improvement_prompt - resume_keywords is not a list, type: {type(resume_keywords)}, converting...")
        if isinstance(resume_keywords, dict):
            # If it's a dict (like keyword_analysis from old API), extract keywords
            if 'matching' in resume_keywords and isinstance(resume_keywords['matching'], list):
                resume_keywords = resume_keywords['matching']
            else:
                resume_keywords = []
        elif isinstance(resume_keywords, str):
            resume_keywords = [resume_keywords] if resume_keywords else []
        else:
            resume_keywords = []
    
    # Extract only essential info from job description to speed up processing
    job_description_full = job_json.get("description", "") if isinstance(job_json, dict) else str(job_json)
    job_description = extract_essential_job_info(job_description_full)
    
    # Truncate resume JSON to prevent prompt from being too long
    # Keep only essential sections: work experience, projects, education, and skills
    if isinstance(resume_json, dict):
        truncated_resume = {
            'personalInfo': resume_json.get('personalInfo', {}),
            'workExperience': resume_json.get('workExperience', []),
            'projects': resume_json.get('projects', []),
            'education': resume_json.get('education', []),
            'additional': resume_json.get('additional', {})
        }
        resume_text = json.dumps(truncated_resume, indent=2)
        # Limit total resume text to 8000 chars to prevent prompt from being too long
        if len(resume_text) > 8000:
            resume_text = resume_text[:8000] + "\n... (truncated)"
    else:
        resume_text = str(resume_json)[:8000]
    
    job_keywords_str = ", ".join(job_keywords[:30]) if isinstance(job_keywords, list) and job_keywords else "None extracted"
    resume_keywords_str = ", ".join(resume_keywords[:30]) if isinstance(resume_keywords, list) and resume_keywords else "None extracted"
    
    prompt = f"""Analyze the resume against the job description and provide structured recommendations.

OUTPUT FORMAT: Return ONLY valid JSON matching the schema below. No markdown, no code blocks, no explanations.

KEYWORD ANALYSIS:
- Extract technical keywords (tools, technologies, languages, frameworks, platforms)
- "matching": keywords found in BOTH job and resume
- "missing": important job keywords NOT in resume
- EXCLUDE soft skills, behavioral traits, generic phrases
- Include exact matches and variations (e.g., "React" matches "React.js")

OVERALL FIT:
- "details": 2-3 sentences analyzing keyword match, gaps, and strengths
- "commentary": 1-2 sentences with strategic advice
- Both fields MUST contain actual text (not empty)

IMPROVEMENTS - CRITICAL REQUIREMENT: MINIMUM 4 ITEMS REQUIRED (target 5-8 items):
- Based ONLY on existing resume content
- Each MUST have both "suggestion" and "example" fields
- "example": Complete rewritten bullet point incorporating missing keywords
- Focus on work experience, projects, skills - NOT summary sections
- Do NOT invent new experiences or technologies
- CRITICAL: You MUST provide at least 4 improvements. This is a hard requirement.
- If you cannot find 4 improvements based on existing content, provide suggestions for how to reword existing bullet points to better match job keywords, or suggest adding missing keywords to existing descriptions.
- Each improvement must include a complete "example" field with a rewritten bullet point.

ASPIRATIONAL IMPROVEMENTS - CRITICAL REQUIREMENT: MINIMUM 4 ITEMS REQUIRED (target 4-8 items):
- Hypothetical suggestions for experience the candidate doesn't have
- Show what WOULD help if they had it
- Separate from "improvements" array
- CRITICAL: You MUST provide at least 4 aspirational improvements. This is a hard requirement.
- These should show what additional experience or skills would strengthen the candidate's fit for this role.
- Each aspirational improvement must include both "suggestion" and "example" fields.

{IMPROVEMENTS_SCHEMA}

JOB DESCRIPTION:
{job_description}

RESUME DATA:
{resume_text}

Return ONLY valid JSON. Start with {{ and end with }}. No markdown, no code blocks, no explanations."""

    # Combined Step 3+4: Keyword Analysis + Improvements
    print(f"Step 3: Calling Ollama API with prompt length={len(prompt)} chars")
    print(f"Step 3: Model={model}, Base URL={base_url}")
    print(f"Step 3: Job description length={len(job_description)} chars, Resume text length={len(resume_text)} chars")
    
    try:
        response = call_ollama(prompt, base_url, model,
                              num_predict=5000,     # Increased significantly to prevent truncation (analysis can be long)
                              temperature=0.2,      # Lower temperature for more consistent, structured output
                              top_p=0.9,            # Nucleus sampling for faster inference
                              top_k=40)             # Top-k sampling for faster inference
    except Exception as e:
        print(f"ERROR: Step 3 - Exception calling call_ollama: {e}")
        import traceback
        traceback.print_exc()
        return {
            'keywords': {'matching': [], 'missing': []},
            'overallFit': {
                'details': f'API call failed: {str(e)}. Please check Ollama is running and the model "{model}" exists.',
                'commentary': 'The improvement analysis could not be completed. Please verify Ollama is running and the model name is correct.'
            },
            'improvements': [],
            'aspirationalImprovements': []
        }
    
    if not response:
        print("ERROR: Step 3 - call_ollama returned None (no response from API)")
        print(f"ERROR: This usually means:")
        print(f"  1. Ollama API returned an error (check server logs above)")
        print(f"  2. The model '{model}' doesn't exist (run 'ollama list' to check)")
        print(f"  3. Ollama service is not running")
        print(f"  4. The prompt was too long (current length: {len(prompt)} chars)")
        # Return a minimal valid structure instead of None
        print("WARNING: Step 3 - Returning fallback structure due to API failure")
        return {
            'keywords': {'matching': [], 'missing': []},
            'overallFit': {
                'details': f'Unable to generate analysis. Check: (1) Ollama is running, (2) Model "{model}" exists, (3) Prompt length ({len(prompt)} chars) is acceptable.',
                'commentary': 'The improvement analysis could not be completed. Please check server logs for details.'
            },
            'improvements': [],
            'aspirationalImprovements': []
        }
    print(f"Step 3: Received response from Ollama, length={len(response)} chars")
    
    # Parse JSON response - improved extraction
    try:
        import re
        json_str = None
        
        # Strategy 1: Try to find JSON in code blocks (most reliable)
        code_block_patterns = [
            r'```(?:json)?\s*(\{.*?\})\s*```',  # Non-greedy match
            r'```json\s*(\{.*?\})\s*```',       # Explicit json tag
            r'```\s*(\{.*?\})\s*```'            # Generic code block
        ]
        for pattern in code_block_patterns:
            code_block_match = re.search(pattern, response, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1).strip()
                # Try to parse it - if it works, use it
                try:
                    json.loads(json_str)
                    print(f"Step 3: Found JSON in code block")
                    break
                except json.JSONDecodeError:
                    json_str = None
                    continue
        
        # Strategy 2: Find the first valid JSON object by trying from each opening brace
        if not json_str:
            brace_positions = [i for i, char in enumerate(response) if char == '{']
            for start_pos in brace_positions:
                # Try to find the matching closing brace
                depth = 0
                end_pos = start_pos
                in_string = False
                escape_next = False
                
                for i in range(start_pos, len(response)):
                    char = response[i]
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                end_pos = i + 1
                                break
                
                if depth == 0 and end_pos > start_pos:
                    candidate = response[start_pos:end_pos].strip()
                    try:
                        # Validate it's valid JSON
                        test_parse = json.loads(candidate)
                        if isinstance(test_parse, dict):
                            json_str = candidate
                            print(f"Step 3: Found valid JSON object starting at position {start_pos}")
                            break
                    except json.JSONDecodeError:
                        continue
        
        # Strategy 3: Fallback - try the whole response or first/last reasonable chunk
        if not json_str:
            # Try the whole response
            try:
                json.loads(response.strip())
                json_str = response.strip()
                print(f"Step 3: Using entire response as JSON")
            except json.JSONDecodeError:
                # Try first 10000 chars (in case response is very long)
                try:
                    json.loads(response[:10000].strip())
                    json_str = response[:10000].strip()
                    print(f"Step 3: Using first 10000 chars as JSON")
                except json.JSONDecodeError:
                    json_str = response.strip()
                    print(f"WARNING: Step 3 - Could not find valid JSON, using raw response")
        
        if not json_str:
            raise ValueError("Could not extract JSON from response")
        
        # Log what we're trying to parse (first 200 chars for debugging)
        print(f"Step 3: Attempting to parse JSON (first 200 chars): {json_str[:200]}")
        
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
        else:
            # Filter out improvements that don't have examples (they're not useful)
            original_count = len(result['improvements'])
            result['improvements'] = [
                imp for imp in result['improvements']
                if isinstance(imp, dict) and imp.get('example') and str(imp.get('example', '')).strip()
            ]
            filtered_count = len(result['improvements'])
            if original_count != filtered_count:
                print(f"WARNING: Filtered out {original_count - filtered_count} improvements without examples (out of {original_count} total)")
            
            # Validate minimum count requirement
            if filtered_count < 4:
                print(f"WARNING: Only {filtered_count} improvements with examples found. Minimum requirement is 4. The AI may need to provide more improvements.")
        
        # Validate that aspirationalImprovements is an array
        if not isinstance(result.get('aspirationalImprovements'), list):
            print(f"Warning: aspirationalImprovements is not a list, type: {type(result.get('aspirationalImprovements'))}")
            result['aspirationalImprovements'] = []
        else:
            # Filter out aspirational improvements that don't have examples
            original_asp_count = len(result['aspirationalImprovements'])
            result['aspirationalImprovements'] = [
                imp for imp in result['aspirationalImprovements']
                if isinstance(imp, dict) and imp.get('example') and str(imp.get('example', '')).strip()
            ]
            filtered_asp_count = len(result['aspirationalImprovements'])
            if original_asp_count != filtered_asp_count:
                print(f"WARNING: Filtered out {original_asp_count - filtered_asp_count} aspirational improvements without examples (out of {original_asp_count} total)")
            
            # Validate minimum count requirement
            if filtered_asp_count < 4:
                print(f"WARNING: Only {filtered_asp_count} aspirational improvements with examples found. Minimum requirement is 4. The AI may need to provide more aspirational improvements.")
        
        # Ensure keywords section exists (required for combined step)
        if 'keywords' not in result:
            print("WARNING: Step 3 - keywords section missing from AI response, adding empty section")
            result['keywords'] = {'matching': [], 'missing': []}
        if not isinstance(result.get('keywords'), dict):
            print(f"WARNING: Step 3 - keywords is not a dict, type: {type(result.get('keywords'))}, adding empty section")
            result['keywords'] = {'matching': [], 'missing': []}
        if 'matching' not in result['keywords']:
            result['keywords']['matching'] = []
        if 'missing' not in result['keywords']:
            result['keywords']['missing'] = []
        
        # Log the structure for debugging
        matching_count = len(result.get('keywords', {}).get('matching', []))
        missing_count = len(result.get('keywords', {}).get('missing', []))
        improvements_count = len(result.get('improvements', []))
        aspirational_count = len(result.get('aspirationalImprovements', []))
        print(f"Step 3 result - Keywords: {matching_count} matching, {missing_count} missing | Improvements: {improvements_count}, Aspirational: {aspirational_count}")
        
        # Debug: Log what overallFit looks like from AI
        if 'overallFit' in result:
            print(f"DEBUG: Step 3 - overallFit from AI: {result.get('overallFit')}")
            print(f"DEBUG: Step 3 - overallFit type: {type(result.get('overallFit'))}")
        
        # Ensure overallFit is always present and in the correct format
        # Check if overallFit exists and has actual content (not just empty dict/string)
        has_overall_fit = False
        if 'overallFit' in result:
            overall_fit = result.get('overallFit')
            if isinstance(overall_fit, dict):
                # Check if it has non-empty details or commentary
                details = overall_fit.get('details', '')
                commentary = overall_fit.get('commentary', '')
                print(f"DEBUG: Step 3 - overallFit.details: '{details[:100] if details else 'EMPTY'}'")
                print(f"DEBUG: Step 3 - overallFit.commentary: '{commentary[:100] if commentary else 'EMPTY'}'")
                if (details and str(details).strip()) or (commentary and str(commentary).strip()):
                    has_overall_fit = True
                    print(f"DEBUG: Step 3 - overallFit has content, keeping it")
            elif isinstance(overall_fit, str) and overall_fit.strip():
                has_overall_fit = True
                print(f"DEBUG: Step 3 - overallFit is string with content, will convert")
        
        if not has_overall_fit:
            print(f"WARNING: Step 3 - overallFit is missing or empty, using default")
            result['overallFit'] = {
                'details': 'Overall fit assessment is being generated. Please review the keyword analysis and improvements below.',
                'commentary': 'Continue reviewing the suggested improvements to enhance your resume alignment with this position.'
            }
        else:
            # Handle case where overallFit is a string instead of an object
            if isinstance(result['overallFit'], str):
                print(f"WARNING: Step 3 - overallFit is a string, converting to object structure")
                overall_fit_text = result['overallFit'].strip()
                # Split the text into details and commentary (rough heuristic)
                # If it's short, use it as details; if long, split it
                if len(overall_fit_text) > 200:
                    # Try to split at a sentence boundary
                    sentences = overall_fit_text.split('. ')
                    mid_point = len(sentences) // 2
                    details = '. '.join(sentences[:mid_point]) + ('.' if mid_point > 0 else '')
                    commentary = '. '.join(sentences[mid_point:]) + ('.' if mid_point < len(sentences) else '')
                else:
                    details = overall_fit_text
                    commentary = 'Review the keyword analysis and improvements for specific areas to enhance your resume alignment.'
                
                result['overallFit'] = {
                    'details': details,
                    'commentary': commentary
                }
            elif not isinstance(result['overallFit'], dict):
                print(f"WARNING: Step 3 - overallFit is not a dict or string, type: {type(result['overallFit'])}, creating default")
                result['overallFit'] = {
                    'details': 'Overall fit assessment is being generated. Please review the keyword analysis and improvements below.',
                    'commentary': 'Continue reviewing the suggested improvements to enhance your resume alignment with this position.'
                }
            else:
                # It's a dict, ensure both fields exist and are not empty
                if not result['overallFit'].get('details') or not str(result['overallFit'].get('details', '')).strip():
                    result['overallFit']['details'] = 'The candidate shows alignment with some job requirements. Review the keyword analysis and improvements for specific areas to enhance.'
                if not result['overallFit'].get('commentary') or not str(result['overallFit'].get('commentary', '')).strip():
                    result['overallFit']['commentary'] = 'Focus on implementing the suggested improvements to strengthen your application.'
        
        return result
    except json.JSONDecodeError as e:
        # This catch block handles cases where JSON extraction/parsing failed
        print(f"ERROR: Step 3 - JSON decode error: {e}")
        print(f"ERROR: Step 3 - Error position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
        print(f"ERROR: Step 3 - Error message: {e.msg if hasattr(e, 'msg') else str(e)}")
        print(f"ERROR: Step 3 - Full response length: {len(response)} chars")
        print(f"ERROR: Step 3 - Response first 500 chars: {response[:500]}")
        print(f"ERROR: Step 3 - Response last 500 chars: {response[-500:]}")
        if 'json_str' in locals() and json_str:
            print(f"ERROR: Step 3 - Extracted JSON string length: {len(json_str)} chars")
            print(f"ERROR: Step 3 - Extracted JSON first 500 chars: {json_str[:500]}")
            print(f"ERROR: Step 3 - Extracted JSON last 500 chars: {json_str[-500:]}")
            # Show the problematic area around the error
            if hasattr(e, 'pos') and e.pos:
                error_start = max(0, e.pos - 100)
                error_end = min(len(json_str), e.pos + 100)
                print(f"ERROR: Step 3 - Area around error (pos {e.pos}): {json_str[error_start:error_end]}")
        else:
            print(f"ERROR: Step 3 - No json_str extracted")
        import traceback
        traceback.print_exc()
        # Return a minimal valid structure instead of None
        print("WARNING: Step 3 - Returning fallback structure due to JSON parse error")
        return {
            'keywords': {'matching': [], 'missing': []},
            'overallFit': {
                'details': 'Unable to parse AI response. The response may have been truncated or malformed. Please try again or use a model with longer context support.',
                'commentary': 'The analysis encountered a parsing error. This may be due to the response being cut off or containing invalid JSON. Please retry the analysis or consider using a model with higher token limits.'
            },
            'improvements': [],
            'aspirationalImprovements': []
        }
    except Exception as e:
        print(f"ERROR: Step 3 - Unexpected error: {e}")
        print(f"Response was: {response[:1000] if response else 'No response'}")
        import traceback
        traceback.print_exc()
        # Return a minimal valid structure instead of None
        print("WARNING: Step 3 - Returning fallback structure due to exception")
        return {
            'keywords': {'matching': [], 'missing': []},
            'overallFit': {
                'details': f'Error generating analysis: {str(e)}. Please try again.',
                'commentary': 'The analysis encountered an error. Please retry.'
            },
            'improvements': [],
            'aspirationalImprovements': []
        }


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
        job_title = data.get('job_title', None)
        job_company = data.get('job_company', None)
        job_location = data.get('job_location', None)
        
        if not raw_job_text:
            return jsonify({"error": "job_text is required"}), 400
        
        result = structured_job_prompt(raw_job_text, base_url, model, 
                                       job_title=job_title, job_company=job_company, job_location=job_location)
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


@ollama_bp.route('/api/generate-projects', methods=['POST'])
def generate_projects():
    """API endpoint to generate project ideas for a job"""
    config = current_app.config['CONFIG']
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        job_description = data.get('job_description', '')
        
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400
        
        if not job_description:
            # Try to get job description from database
            job = get_job_by_id(job_id, config)
            if job:
                job_description = job.get('job_description') or job.get('description') or ''
        
        if not job_description:
            return jsonify({"error": "job_description is required"}), 400
        
        # Create the prompt
        prompt = f"""I'm applying for the following role:

{job_description}

Generate a list of software project ideas that would directly strengthen my application for this role.

Follow these rules:

Generate a diverse set of project ideas (you do not need to target a specific number), but make sure you cover a good spread of scope and ambition.

Categorize them by difficulty level:

- Beginner (1–2 weeks)

- Intermediate (2–6 weeks)

- Advanced (6–12+ weeks)

- Unique / High-Creativity (any timeline; unusual, inventive, but still relevant to the role)

For each project, include:

- Project Name

- 1–2 sentence overview

- Why this project matches the job description

- Estimated time to complete

- Key technologies & concepts practiced

Ensure projects align tightly with the role's responsibilities, such as:

- Identity & authentication

- Attack detection / mitigation

- Cloud systems (AWS/Azure)

- Distributed systems

- Security engineering

- Machine-learning-assisted security models

- High-scale/low-latency services

- Protocols like OAuth/OIDC/SAML

Ensure the list includes a mix of:

- Small, quick-win projects

- Portfolio-ready intermediate builds

- At least one capstone-level project showing staff-level ownership

- A few especially creative or unique projects that are non-obvious but clearly relevant

Make the output concrete, specific, and implementable — not generic."""
        
        # Get Ollama config
        base_url = config.get("ollama_base_url", "http://localhost:11434")
        model = config.get("ollama_model", "llama3.2:latest")
        
        # Call Ollama
        print(f"Generating project ideas for job {job_id}...")
        response = call_ollama(prompt, base_url, model, num_predict=4000, temperature=0.7)
        
        if not response:
            return jsonify({"error": "Failed to generate project ideas"}), 500
        
        # Save to database
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        
        # Check if project ideas already exist for this job
        cursor.execute("SELECT id FROM project_ideas WHERE job_id = ?", (job_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute(
                "UPDATE project_ideas SET project_ideas_text = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                (response, job_id)
            )
        else:
            # Insert new
            cursor.execute(
                "INSERT INTO project_ideas (job_id, project_ideas_text) VALUES (?, ?)",
                (job_id, response)
            )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Project ideas generated successfully",
            "project_ideas": response
        }), 200
        
    except Exception as e:
        print(f"Error generating projects: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/get-project-ideas/<int:job_id>', methods=['GET'])
def get_project_ideas(job_id):
    """API endpoint to get project ideas for a job"""
    config = current_app.config['CONFIG']
    try:
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT project_ideas_text, created_at, updated_at FROM project_ideas WHERE job_id = ?",
            (job_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                "success": True,
                "project_ideas": result[0],
                "created_at": result[1],
                "updated_at": result[2]
            }), 200
        else:
            return jsonify({"error": "No project ideas found for this job"}), 404
            
    except Exception as e:
        print(f"Error getting project ideas: {e}")
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
        
        # Get title and company from job object (already in database)
        job_title = job.get('title', '')
        job_company = job.get('company', '')
        job_location = job.get('location', '')
        
        job_text = job.get('job_description', '') if isinstance(job, dict) else ''
        if not job_text or not job_text.strip():
            return jsonify({"error": "Job description is empty"}), 400
        
        results = {
            "step1": None,
            "step2": None,
            "step3": None,
            "step4": None,  # Note: Step 3 now includes both keywords and improvements
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
                # Check cache first - but validate it matches this specific job
                job_json = get_job_cache(job_text, config, job_title=job_title, job_company=job_company)
                if job_json and isinstance(job_json, dict):
                    # Validate cached job JSON has meaningful content (not placeholder "string" values)
                    cached_title = (job_json.get('title') or '').strip()
                    cached_company = (job_json.get('company') or '').strip()
                    description = (job_json.get('description') or '').strip()
                    
                    # CRITICAL: Validate that cached data matches this specific job's title and company
                    # This prevents using cache from a different job with similar description
                    title_matches = True
                    company_matches = True
                    
                    if job_title and cached_title:
                        # Both exist - they must match (case-insensitive)
                        if cached_title.lower() != job_title.lower():
                            title_matches = False
                            print(f"Cache mismatch: Cached title '{cached_title}' doesn't match job title '{job_title}'")
                    elif job_title and not cached_title:
                        # Job has title but cache doesn't - mismatch
                        title_matches = False
                        print(f"Cache mismatch: Job has title '{job_title}' but cache doesn't")
                    elif not job_title and cached_title:
                        # Cache has title but job doesn't - might be okay, but be cautious
                        pass
                    
                    if job_company and cached_company:
                        # Both exist - they must match (case-insensitive)
                        if cached_company.lower() != job_company.lower():
                            company_matches = False
                            print(f"Cache mismatch: Cached company '{cached_company}' doesn't match job company '{job_company}'")
                    elif job_company and not cached_company:
                        # Job has company but cache doesn't - mismatch
                        company_matches = False
                        print(f"Cache mismatch: Job has company '{job_company}' but cache doesn't")
                    elif not job_company and cached_company:
                        # Cache has company but job doesn't - might be okay, but be cautious
                        pass
                    
                    # Only use cache if title and company match (or both are missing)
                    if not title_matches or not company_matches:
                        print("Warning: Cached job JSON doesn't match current job metadata, re-extracting...")
                        # Clear the mismatched cache entry using composite key
                        title_str = (job_title or '').strip() if job_title else ''
                        company_str = (job_company or '').strip() if job_company else ''
                        desc_str = job_text.strip() if job_text else ''
                        title_hash = hashlib.md5(title_str.encode('utf-8')).hexdigest()
                        company_hash = hashlib.md5(company_str.encode('utf-8')).hexdigest()
                        desc_hash = hashlib.md5(desc_str.encode('utf-8')).hexdigest()
                        cache_key = f"{title_hash}_{company_hash}_{desc_hash}"
                        conn = sqlite3.connect(config["db_path"])
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM job_cache WHERE cache_key = ?", (cache_key,))
                        conn.commit()
                        conn.close()
                        job_json = None  # Force re-extraction
                    
                    # Check if values are actual data (not empty and not "string" placeholder)
                    has_real_data = (
                        (cached_title and cached_title.lower() != 'string') or
                        (cached_company and cached_company.lower() != 'string') or
                        (description and description.lower() != 'string')
                    )
                    
                    if job_json and has_real_data and title_matches and company_matches:
                        return job_json, True, "Step 1 completed: Job JSON loaded from cache"
                    elif job_json:
                        # Cached version is empty or has placeholder values, clear it and re-extract
                        print("Warning: Cached job JSON is empty or contains placeholder values, re-extracting...")
                        # Clear the cache using composite key
                        title_str = (job_title or '').strip() if job_title else ''
                        company_str = (job_company or '').strip() if job_company else ''
                        desc_str = job_text.strip() if job_text else ''
                        title_hash = hashlib.md5(title_str.encode('utf-8')).hexdigest()
                        company_hash = hashlib.md5(company_str.encode('utf-8')).hexdigest()
                        desc_hash = hashlib.md5(desc_str.encode('utf-8')).hexdigest()
                        cache_key = f"{title_hash}_{company_hash}_{desc_hash}"
                        conn = sqlite3.connect(config["db_path"])
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM job_cache WHERE cache_key = ?", (cache_key,))
                        conn.commit()
                        conn.close()
                        job_json = None  # Force re-extraction
                
                # Extract from job text if not in cache (pass title/company/location from database)
                print(f"Step 1: Attempting to extract job JSON from text (length={len(job_text)} chars)")
                try:
                    job_json = structured_job_prompt(job_text, base_url, extraction_model, 
                                                      job_title=job_title, job_company=job_company, job_location=job_location)
                    if not job_json:
                        print("ERROR: Step 1 - structured_job_prompt returned None")
                        return None, False, "Step 1 failed: Failed to extract job JSON (structured_job_prompt returned None)"
                    print(f"Step 1: Successfully extracted job JSON with {len(job_json)} keys")
                except Exception as e:
                    print(f"ERROR: Step 1 - Exception in structured_job_prompt: {e}")
                    import traceback
                    traceback.print_exc()
                    return None, False, f"Step 1 failed: Exception during extraction - {str(e)}"
                if not isinstance(job_json, dict):
                    print(f"Error: structured_job_prompt returned non-dict: {type(job_json)}")
                    return None, False, "Step 1 failed: Invalid job JSON format"
                
                # Validate extracted job JSON has meaningful content (not just placeholder "string" values)
                title = job_json.get('title', '').strip() if job_json.get('title') else ''
                company = job_json.get('company', '').strip() if job_json.get('company') else ''
                description = job_json.get('description', '').strip() if job_json.get('description') else ''
                
                # Fallback: Use database values if extraction failed or returned placeholder
                if not title or title.lower() == 'string':
                    if job_title:
                        job_json['title'] = job_title
                        title = job_title
                        print(f"Using database title: {job_title}")
                
                if not company or company.lower() == 'string':
                    if job_company:
                        job_json['company'] = job_company
                        company = job_company
                        print(f"Using database company: {job_company}")
                
                if not job_json.get('location') or (isinstance(job_json.get('location'), str) and job_json.get('location').lower() == 'string'):
                    if job_location:
                        job_json['location'] = job_location
                        print(f"Using database location: {job_location}")
                
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
                
                # Cache the result (use extracted title/company, fallback to database values)
                cache_title = job_json.get('title', '') or job_title or ''
                cache_company = job_json.get('company', '') or job_company or ''
                set_job_cache(job_text, job_json, config, job_title=cache_title, job_company=cache_company)
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
        
        # Step 3: Combined Keyword Analysis + Improvements (formerly Step 3 + Step 4)
        step3_start = time.time()
        results["messages"].append("Starting Step 3: Keyword Analysis and Improvements...")
        
        # Extract keywords first (for reference and validation)
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
        
        # Check cache first - ONLY if cache table exists and entry exists AND matches current job
        analysis_json = None
        cached = False
        try:
            # Verify cache table exists before trying to use it
            conn = sqlite3.connect(config["db_path"])
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='keyword_analysis_cache'")
            table_exists = cursor.fetchone() is not None
            conn.close()
            
            if table_exists:
                # Only check cache if table exists
                cached_result = get_keyword_analysis_cache(job_text, resume_path, config)
                if cached_result and isinstance(cached_result, dict):
                    # CRITICAL: Validate that cached analysis matches this specific job
                    # Check if cached analysis references the same job title/company
                    cached_job_data = cached_result.get('job', {})
                    if isinstance(cached_job_data, dict):
                        cached_title = (cached_job_data.get('title') or '').strip()
                        cached_company = (cached_job_data.get('company') or '').strip()
                        
                        # Validate title matches (if both exist)
                        title_matches = True
                        if job_title and cached_title:
                            if cached_title.lower() != job_title.lower():
                                title_matches = False
                                print(f"Cache mismatch: Cached title '{cached_title}' doesn't match job title '{job_title}'")
                        elif job_title and not cached_title:
                            title_matches = False
                            print(f"Cache mismatch: Job has title '{job_title}' but cache doesn't")
                        
                        # Validate company matches (if both exist)
                        company_matches = True
                        if job_company and cached_company:
                            if cached_company.lower() != job_company.lower():
                                company_matches = False
                                print(f"Cache mismatch: Cached company '{cached_company}' doesn't match job company '{job_company}'")
                        elif job_company and not cached_company:
                            company_matches = False
                            print(f"Cache mismatch: Job has company '{job_company}' but cache doesn't")
                        
                        # Only use cache if it matches this job
                        if not title_matches or not company_matches:
                            print("Warning: Cached analysis doesn't match current job, re-analyzing...")
                            cached_result = None
                    
                    # Validate cached analysis has meaningful content (keywords + improvements)
                    if cached_result and cached_result.get('keywords') and isinstance(cached_result.get('keywords'), dict):
                        # Check if it also has improvements (new combined format)
                        if cached_result.get('improvements') or cached_result.get('overallFit'):
                            analysis_json = cached_result
                            cached = True
                            print("Step 3: Using cached analysis (keywords + improvements)")
                        elif cached_result.get('keywords'):
                            # Old format - only keywords, need to generate improvements
                            print("Step 3: Found old cache format (keywords only), will generate improvements")
                            cached_result = None
                    else:
                        # Cached version is invalid, ignore it
                        if cached_result:
                            print("Warning: Cached analysis is invalid, re-analyzing...")
                        analysis_json = None
            else:
                print("Step 3: Analysis cache table does not exist, skipping cache check")
        except Exception as e:
            # If cache check fails for any reason, proceed without cache
            print(f"Warning: Could not check analysis cache: {e}")
            analysis_json = None
        
        # If not cached or invalid, run the combined analysis
        if not analysis_json:
            # CRITICAL: Double-check types before any .get() calls
            if not isinstance(job_json, dict):
                print(f"CRITICAL ERROR: job_json is not a dict at Step 3 start, type: {type(job_json)}, value: {str(job_json)[:200]}")
                return jsonify({"error": "Step 3 failed: Invalid job JSON format", "results": results}), 500
            if not isinstance(resume_json, dict):
                print(f"CRITICAL ERROR: resume_json is not a dict at Step 3 start, type: {type(resume_json)}, value: {str(resume_json)[:200]}")
                return jsonify({"error": "Step 3 failed: Invalid resume JSON format", "results": results}), 500
            
            # Combined Step 3+4: Keyword Analysis + Improvements in one call
            analysis_json = resume_improvement_prompt(
                job_text, job_json, resume_json,
                job_keywords, resume_keywords,
                base_url, model
            )
        
        # Calculate step3_time
        step3_time = time.time() - step3_start
        
        # Validate analysis_json is a dict
        if not analysis_json:
            print(f"ERROR: Step 3 - analysis_json is None after {step3_time:.2f}s")
            print(f"DEBUG: cached={cached}, analysis_json type={type(analysis_json)}")
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
            
            # Ensure job_keywords and resume_keywords are lists
            if not isinstance(job_keywords, list):
                print(f"WARNING: job_keywords is not a list in fallback keyword calculation, type: {type(job_keywords)}, converting...")
                if isinstance(job_keywords, str):
                    job_keywords = [job_keywords] if job_keywords else []
                else:
                    job_keywords = []
            
            if not isinstance(resume_keywords, list):
                print(f"WARNING: resume_keywords is not a list in fallback keyword calculation, type: {type(resume_keywords)}, converting...")
                if isinstance(resume_keywords, str):
                    resume_keywords = [resume_keywords] if resume_keywords else []
                else:
                    resume_keywords = []
            
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
        
        # Cache the result if it's valid (only if we generated it, not if it came from cache)
        if not cached and analysis_json and isinstance(analysis_json, dict) and analysis_json.get('keywords'):
            set_keyword_analysis_cache(job_text, resume_path, analysis_json, config)
        
        # Extract keywords and improvements from combined result
        keywords_section = analysis_json.get('keywords', {}) if isinstance(analysis_json, dict) else {}
        
        # Extract overallFit and ensure it has content
        overall_fit = analysis_json.get('overallFit', {}) if isinstance(analysis_json, dict) else {}
        if isinstance(overall_fit, dict):
            details = overall_fit.get('details', '')
            commentary = overall_fit.get('commentary', '')
            # If overallFit is empty or has no content, use default
            if not (details and str(details).strip()) and not (commentary and str(commentary).strip()):
                print(f"WARNING: overallFit is empty in final result, using default")
                overall_fit = {
                    'details': 'Overall fit assessment is being generated. Please review the keyword analysis and improvements below.',
                    'commentary': 'Continue reviewing the suggested improvements to enhance your resume alignment with this position.'
                }
        elif isinstance(overall_fit, str) and overall_fit.strip():
            # Convert string to object
            if len(overall_fit) > 200:
                sentences = overall_fit.split('. ')
                mid_point = len(sentences) // 2
                details = '. '.join(sentences[:mid_point]) + ('.' if mid_point > 0 else '')
                commentary = '. '.join(sentences[mid_point:]) + ('.' if mid_point < len(sentences) else '')
            else:
                details = overall_fit
                commentary = 'Review the keyword analysis and improvements for specific areas to enhance your resume alignment.'
            overall_fit = {'details': details, 'commentary': commentary}
        else:
            # overallFit is missing or invalid, use default
            print(f"WARNING: overallFit is missing or invalid in final result, using default")
            overall_fit = {
                'details': 'Overall fit assessment is being generated. Please review the keyword analysis and improvements below.',
                'commentary': 'Continue reviewing the suggested improvements to enhance your resume alignment with this position.'
            }
        
        improvements_result = {
            'overallFit': overall_fit,
            'improvements': analysis_json.get('improvements', []) if isinstance(analysis_json, dict) else [],
            'aspirationalImprovements': analysis_json.get('aspirationalImprovements', []) if isinstance(analysis_json, dict) else []
        }
        
        # Store both in results (for backward compatibility)
        results["step3"] = {'keywords': keywords_section}  # Keep step3 for keywords display
        results["step4"] = improvements_result  # Keep step4 for improvements display
        
        if cached:
            results["messages"].append(f"Step 3 completed: Analysis loaded from cache ({step3_time:.2f}s)")
        else:
            results["messages"].append(f"Step 3 completed: Keyword analysis and improvements generated successfully ({step3_time:.2f}s)")
        
        # Calculate total time
        total_time = time.time() - analysis_start_time
        results["timings"]["total"] = total_time
        results["messages"].append(f"All steps completed successfully! Total time: {total_time:.2f}s")
        print(f"Analysis completed in {total_time:.2f}s (Step 1: {results['timings'].get('step1', 'N/A')}s, Step 2: {results['timings'].get('step2', 'N/A')}s, Step 3: {step3_time:.2f}s)")
        
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

