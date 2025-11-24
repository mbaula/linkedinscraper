from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
from urllib.parse import quote
from typing import List, Dict


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job board scraper.
    Implements LinkedIn-specific scraping logic.
    """
    
    def get_source_name(self) -> str:
        """Return the source name for LinkedIn."""
        return 'linkedin'
    
    def get_job_cards(self) -> List[Dict]:
        """
        Scrape job cards from LinkedIn search results.
        
        Returns:
            List[Dict]: List of job dictionaries
        """
        all_jobs = []
        rounds = self.config.get('rounds', 1)
        pages_to_scrape = self.config.get('pages_to_scrape', 10)
        search_queries = self.config.get('search_queries', [])
        timespan = self.config.get('timespan', 'r84600')
        
        total_rounds = rounds
        total_queries = len(search_queries)
        total_pages = total_rounds * total_queries * pages_to_scrape
        current_page = 0
        
        print(f"  Starting job card scraping:", flush=True)
        print(f"    - Rounds: {rounds}", flush=True)
        print(f"    - Search queries: {total_queries}", flush=True)
        print(f"    - Pages per query: {pages_to_scrape}", flush=True)
        print(f"    - Total pages to scrape: {total_pages}", flush=True)
        
        for round_num in range(0, rounds):
            print(f"\n  Round {round_num + 1}/{rounds}:", flush=True)
            for query_idx, query in enumerate(search_queries, 1):
                keywords = query.get('keywords', '')
                location = query.get('location', '')
                f_wt = query.get('f_WT', '')
                
                print(f"\n    Query {query_idx}/{total_queries}: '{keywords}' in '{location}'", flush=True)
                if f_wt:
                    print(f"      Work type filter: {f_wt}", flush=True)
                
                keywords_encoded = quote(keywords)
                location_encoded = quote(location)
                
                for page_num in range(0, pages_to_scrape):
                    current_page += 1
                    url = (f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
                          f"keywords={keywords_encoded}&location={location_encoded}&f_TPR=&f_WT={f_wt}&geoId=&"
                          f"f_TPR={timespan}&start={25*page_num}")
                    
                    print(f"      -> Scraping page {page_num + 1}/{pages_to_scrape} (Overall: {current_page}/{total_pages})...", flush=True)
                    soup = self.get_with_retry(url)
                    if soup:
                        jobs = self._transform_search_results(soup)
                        all_jobs.extend(jobs)
                        print(f"        [OK] Found {len(jobs)} job cards on this page", flush=True)
                    else:
                        print(f"        [ERROR] Failed to scrape page (may be empty or rate limited)", flush=True)
        
        print(f"\n  [OK] Job card scraping completed", flush=True)
        print(f"    - Total job cards scraped: {len(all_jobs)}", flush=True)
        return all_jobs
    
    def _transform_search_results(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse LinkedIn search results HTML into job dictionaries.
        
        Args:
            soup: BeautifulSoup object of the search results page
            
        Returns:
            List[Dict]: List of job dictionaries
        """
        joblist = []
        try:
            divs = soup.find_all('div', class_='base-search-card__info')
        except:
            print("Empty page, no jobs found")
            return joblist
        
        for item in divs:
            try:
                title = item.find('h3')
                if not title:
                    continue
                title = title.text.strip()
                
                company = item.find('a', class_='hidden-nested-link')
                company_text = company.text.strip().replace('\n', ' ') if company else ''
                
                location = item.find('span', class_='job-search-card__location')
                location_text = location.text.strip() if location else ''
                
                parent_div = item.parent
                entity_urn = parent_div.get('data-entity-urn', '')
                job_posting_id = entity_urn.split(':')[-1] if entity_urn else ''
                job_url = f'https://www.linkedin.com/jobs/view/{job_posting_id}/' if job_posting_id else ''
                
                date_tag_new = item.find('time', class_='job-search-card__listdate--new')
                date_tag = item.find('time', class_='job-search-card__listdate')
                date = ''
                if date_tag and date_tag.get('datetime'):
                    date = date_tag['datetime']
                elif date_tag_new and date_tag_new.get('datetime'):
                    date = date_tag_new['datetime']
                
                job = {
                    'title': title,
                    'company': company_text,
                    'location': location_text,
                    'date': date,
                    'job_url': job_url,
                    'job_description': '',  # Will be filled later
                    'applied': 0,
                    'hidden': 0,
                    'interview': 0,
                    'rejected': 0
                }
                joblist.append(job)
            except Exception as e:
                print(f"Error parsing job card: {e}")
                continue
        
        return joblist
    
    def get_job_description(self, job_url: str) -> str:
        """
        Fetch and parse the full job description from LinkedIn job URL.
        
        Args:
            job_url: URL of the LinkedIn job posting
            
        Returns:
            str: Job description text
        """
        soup = self.get_with_retry(job_url)
        if not soup:
            print(f"        [ERROR] Could not fetch job description from {job_url}", flush=True)
            return "Could not fetch job description"
        
        description = self._transform_job_description(soup)
        if description and description != "Could not find Job Description":
            print(f"        [OK] Job description fetched ({len(description)} characters)", flush=True)
        else:
            print(f"        [WARNING] Job description not found or empty", flush=True)
        return description
    
    def _transform_job_description(self, soup: BeautifulSoup) -> str:
        """
        Parse LinkedIn job description HTML into clean text.
        
        Args:
            soup: BeautifulSoup object of the job description page
            
        Returns:
            str: Clean job description text
        """
        div = soup.find('div', class_='description__text description__text--rich')
        if div:
            # Remove unwanted elements
            for element in div.find_all(['span', 'a']):
                element.decompose()
            
            # Replace bullet points
            for ul in div.find_all('ul'):
                for li in ul.find_all('li'):
                    li.insert(0, '-')
            
            text = div.get_text(separator='\n').strip()
            text = text.replace('\n\n', '')
            text = text.replace('::marker', '-')
            text = text.replace('-\n', '- ')
            text = text.replace('Show less', '').replace('Show more', '')
            return text
        else:
            return "Could not find Job Description"


