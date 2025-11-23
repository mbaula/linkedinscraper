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
        
        for k in range(0, rounds):
            for query in search_queries:
                keywords = quote(query.get('keywords', ''))
                location = quote(query.get('location', ''))
                f_wt = query.get('f_WT', '')
                
                for i in range(0, pages_to_scrape):
                    url = (f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
                          f"keywords={keywords}&location={location}&f_TPR=&f_WT={f_wt}&geoId=&"
                          f"f_TPR={timespan}&start={25*i}")
                    
                    soup = self.get_with_retry(url)
                    if soup:
                        jobs = self._transform_search_results(soup)
                        all_jobs.extend(jobs)
                        print(f"Finished scraping page: {url}")
        
        print(f"Total job cards scraped: {len(all_jobs)}")
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
            return "Could not fetch job description"
        
        return self._transform_job_description(soup)
    
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

