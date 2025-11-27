# LinkedIn Job Scraper

A comprehensive Python application that scrapes job postings from LinkedIn, stores them in a SQLite database, and provides a powerful web interface for managing your job search. The application includes AI-powered cover letter generation, resume analysis, and an application tracker to help you stay organized throughout your job search journey.

![Screenshot image](./screenshot/screenshot1.png)

### Problem

If you spent any amount of time looking for jobs on LinkedIn you know how frustrating it is. The same job postings keep showing up in your search results, and you have to scroll through pages and pages of irrelevant job postings to find the ones that are relevant to you, only to see the ones you applied for weeks ago. This application aims to solve this problem by scraping job postings from LinkedIn and storing them in a SQLite database. You can filter out job postings based on keywords in Title and Description (tired of seeing Clinical QA Manager when you search for software QA jobs? Just filter out jobs that have "clinical" in the title). The jobs are sorted by date posted, not by what LinkedIn thinks is relevant to you. No sponsored job posts. No duplicate job posts. No irrelevant job posts. Just the jobs you want to see.

### IMPORTANT NOTE

If you are using this application, please be aware that LinkedIn does not allow scraping of its website. Use this application at your own risk. It's recommended to use proxy servers to avoid getting blocked by LinkedIn (more on proxy servers below).

### Features

- **Job Scraping**: Automated scraping of LinkedIn job postings based on customizable search queries
- **Advanced Filtering**: Filter jobs by search term, date posted, city, job title, company, and status
- **Job Status Management**: Mark jobs as saved, applied, interview, rejected, or hidden
- **AI-Powered Cover Letter Generation**: Generate personalized cover letters using OpenAI, Groq, or Ollama
- **Resume Analysis**: Analyze your resume against job postings using Ollama AI
- **Resume Improvement Suggestions**: Get AI-powered suggestions to improve your resume
- **Application Tracker**: Track all your job applications in one place with export functionality
- **Search Configuration UI**: Configure and execute job searches directly from the web interface
- **Export Functionality**: Export cover letters as PDF or DOCX, and applications as CSV

### Prerequisites

- Python 3.6 or higher
- Flask
- Flask-CORS
- Requests
- BeautifulSoup4
- Pandas
- SQLite3
- Pysocks
- OpenAI (optional, for cover letter generation)
- pdfminer.six (for PDF processing)
- reportlab (for PDF generation)
- python-docx (for DOCX generation)
- langdetect (for language detection)

### Installation

1. Clone the repository to your local machine.
2. Install the required packages using pip: `pip install -r requirements.txt`
3. Create a `config.json` file in the root directory of the project. See the `config.json` section below for details on the configuration options. `config_example.json` is provided as an example, feel free to use it as a template.
4. Run the scraper using the command `python main.py`. Note: run this first to populate the database with job postings prior to running app.py. Alternatively, you can use the web interface to configure and execute searches.
5. Run the application using the command `python app.py`.
6. Open a web browser and navigate to `http://127.0.0.1:5000` to view the job postings.

### Usage

The application consists of two main components: the scraper and the web interface.

#### Scraper

The scraper is implemented in `main.py`. It scrapes job postings from LinkedIn based on the search queries and filters specified in the `config.json` file. The scraper removes duplicate and irrelevant job postings based on the specified keywords and stores the remaining job postings in a SQLite database.

To run the scraper, execute the following command:

```
python main.py
```

#### Web Interface

The web interface is implemented using Flask in `app.py` using the application factory pattern with blueprints for better modularity. It provides a comprehensive interface to view and manage the job postings stored in the SQLite database.

**Main Features:**

1. **Job Listings Page** (`/`): 
   - View all job postings with advanced filtering options
   - Filter by search term, date posted, city, job title, company, and status
   - Sort by date or job title
   - Mark jobs as saved, applied, interview, rejected, or hidden
   - Unhide previously hidden jobs
   - Click on any job to view full details

2. **Application Tracker** (`/application_tracker`):
   - Track all your job applications
   - Add, update, and delete applications
   - Export applications to CSV
   - View application history

3. **Search Configuration** (`/search_config`):
   - Configure search queries and filters
   - Execute searches directly from the web interface
   - Monitor search progress
   - Stop running searches

**Job Status Colors:**
- **Applied**: Highlighted in light blue
- **Rejected**: Highlighted in red
- **Interview**: Highlighted in green
- **Hidden**: Removed from the list (can be unhidden)

To run the web interface, execute the following command:

```
python app.py
```

Then, open a web browser and navigate to `http://127.0.0.1:5000` to view the job postings.

### Configuration

The `config.json` file contains the configuration options for the scraper and the web interface. Below is a description of each option:

- `proxies`: The proxy settings for the requests library. Set the `http` and `https` keys with the appropriate proxy URLs.
- `headers`: The headers to be sent with the requests. Set the `User-Agent` key with a valid user agent string. If you don't know your user agent, google "my user agent" and it will show it.
- `OpenAI_API_KEY`: Your OpenAI API key. You can get it from your OpenAI dashboard. Required if using OpenAI for cover letter generation.
- `OpenAI_Model`: The name of the OpenAI model to use for cover letter generation. GPT-4 family of models produces best results, but also the most expensive one.
- `resume_path`: Local path to your resume in PDF format (only PDF is supported at this time). For best results it's advised that your PDF resume is formatted in a way that's easy for the AI to parse. Use a single column format, avoid images. You may get unpredictable results if it's in a two-column format.
- `search_queries`: An array of search query objects, each containing the following keys:
  - `keywords`: The keywords to search for in the job title.
  - `location`: The location to search for jobs.
  - `f_WT`: The job type filter. Values are as follows:
        -  0 - onsite
        -  1 - hybrid
        -  2 - remote
        -  empty (no value) - any one of the above.
- `desc_words`: An array of keywords to filter out job postings based on their description.
- `title_include`: An array of keywords to filter job postings based on their title. Keep *only* jobs that have at least one of the words from 'title_include' in its title. Leave empty if you don't want to filter by title.
- `title_exclude`: An array of keywords to filter job postings based on their title. Discard jobs that have ANY of the word from 'title_exclude' in its title. Leave empty if you don't want to filter by title.
- `company_exclude`: An array of keywords to filter job postings based on the company name. Discard jobs come from a certain company because life is too short to work for assholes.
- `languages`: Script will auto-detect the language from the description. If the language is not in this list, the job will be discarded. Leave empty if you don't want to filter by language. Use "en" for English, "de" for German, "fr" for French, "es" for Spanish, etc. See documentation for langdetect for more details.
- `timespan`: The time range for the job postings. "r604800" for the past week, "r84600" for the last 24 hours. Basically "r" plus 60 * 60 * 24 * <number of days>.
- `jobs_tablename`: The name of the table in the SQLite database where the job postings will be stored.
- `filtered_jobs_tablename`: The name of the table in the SQLite database where the filtered job postings will be stored.
- `db_path`: The path to the SQLite database file.
- `pages_to_scrape`: The number of pages to scrape for each search query.
- `rounds`: The number of times to run the scraper. LinkedIn doesn't always show the same results for the same search query, so running the scraper multiple times will increase the number of job postings scraped. I set up a cron job that runs every hour during the day.
- `days_to_scrape`: The number of days to scrape. The scraper will ignore job postings older than this number of days.
- `delete_unapplied_jobs_after_days`: Automatically delete jobs that haven't been applied to after a certain number of days. Set to 0 to disable.
- `app_table`: The name of the table in the SQLite database where applications will be stored.
- `ollama_model`: The Ollama model to use for cover letter generation and resume analysis (e.g., "llama3.2:latest").
- `ollama_base_url`: The base URL for your Ollama instance (default: "http://localhost:11434").
- `cover_letter_provider`: The provider to use for cover letter generation. Options: "openai", "groq", or "ollama".
- `groq_api_key`: Your Groq API key. Required if using Groq for cover letter generation.

### What remains to be done

- [ ] Add functionality to unhide and un-apply jobs.
- [ ] Add functionality to sort jobs by date added to the databse. Current sorting is by date posted on LinkedIn. Some jobs (~1-5%) are not being picked up by the search (and as such this scraper) until days after they are posted. This is a known issue with LinkedIn and there's nothing I can do about it, however sorting jobs by dated added to the database will make it easier to find those jobs.
- [ ] Add front end functionality to configure search, and execute that search from UI. Currently configuration is done in json file and search is executed from command line.


### Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

### License

This project is licensed under the MIT License.X
Write README.md file for this project. Make it detailed as possible.
X
