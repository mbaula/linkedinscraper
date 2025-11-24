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

@app.route('/get_CoverLetter/<int:job_id>', methods=['POST'])
def get_CoverLetter(job_id):
    print("CoverLetter clicked!")
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()

    def get_chat_gpt(prompt):
        try:
            completion = openai.ChatCompletion.create(
                model=config["OpenAI_Model"],
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Error connecting to OpenAI: {e}")
            return None

    cursor.execute("SELECT job_description, title, company FROM jobs WHERE id = ?", (job_id,))
    job_tuple = cursor.fetchone()
    if job_tuple is not None:
        column_names = [column[0] for column in cursor.description]
        job = dict(zip(column_names, job_tuple))
    
    resume = read_pdf(config["resume_path"])

    # Check if resume is None
    if resume is None:
        print("Error: Resume not found or couldn't be read.")
        return jsonify({"error": "Resume not found or couldn't be read."}), 400

    # Check if OpenAI API key is empty
    if not config["OpenAI_API_KEY"]:
        print("Error: OpenAI API key is empty.")
        return jsonify({"error": "OpenAI API key is empty."}), 400

    openai.api_key = config["OpenAI_API_KEY"]
    consideration = ""
    user_prompt = ("You are a career coach with over 15 years of experience helping job seekers land their dream jobs in tech. You are helping a candidate to write a cover letter for the below role. Approach this task in three steps. Step 1. Identify main challenges someone in this position would face day to day. Step 2. Write an attention grabbing hook for your cover letter that highlights your experience and qualifications in a way that shows you empathize and can successfully take on challenges of the role. Consider incorporating specific examples of how you tackled these challenges in your past work, and explore creative ways to express your enthusiasm for the opportunity. Put emphasis on how the candidate can contribute to company as opposed to just listing accomplishments. Keep your hook within 100 words or less. Step 3. Finish writing the cover letter based on the resume and keep it within 250 words. Respond with final cover letter only. \n job description: " + job['job_description'] + "\n company: " + job['company'] + "\n title: " + job['title'] + "\n resume: " + resume)
    if consideration:
        user_prompt += "\nConsider incorporating that " + consideration

    response = get_chat_gpt(user_prompt)
    if response is None:
        return jsonify({"error": "Failed to get a response from OpenAI."}), 500

    user_prompt2 = ("You are young but experienced career coach helping job seekers land their dream jobs in tech. I need your help crafting a cover letter. Here is a job description: " + job['job_description'] + "\nhere is my resume: " + resume + "\nHere's the cover letter I got so far: " + response + "\nI need you to help me improve it. Let's approach this in following steps. \nStep 1. Please set the formality scale as follows: 1 is conversational English, my initial Cover letter draft is 10. Step 2. Identify three to five ways this cover letter can be improved, and elaborate on each way with at least one thoughtful sentence. Step 4. Suggest an improved cover letter based on these suggestions with the Formality Score set to 7. Avoid subjective qualifiers such as drastic, transformational, etc. Keep the final cover letter within 250 words. Please respond with the final cover letter only.")
    if user_prompt2:
        response = get_chat_gpt(user_prompt2)
        if response is None:
            return jsonify({"error": "Failed to get a response from OpenAI."}), 500

    query = "UPDATE jobs SET cover_letter = ? WHERE id = ?"
    print(f'Executing query: {query} with job_id: {job_id} and cover letter: {response}')
    cursor.execute(query, (response, job_id))
    conn.commit()
    conn.close()
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
