from abc import ABC, abstractmethod
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
import time as tm


class BaseScraper(ABC):
    """
    Abstract base class for all job board scrapers.
    Each job board scraper should inherit from this class and implement the required methods.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the scraper with configuration.
        
        Args:
            config: Configuration dictionary containing scraper settings
        """
        self.config = config
        self.source_name = self.get_source_name()
    
    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return the name of the job board source (e.g., 'linkedin', 'indeed').
        
        Returns:
            str: Source name
        """
        pass
    
    @abstractmethod
    def get_job_cards(self) -> List[Dict]:
        """
        Scrape job cards from the job board.
        This should return a list of job dictionaries with at minimum:
        - title: Job title
        - company: Company name
        - location: Job location
        - date: Posting date
        - job_url: URL to the job posting
        
        Returns:
            List[Dict]: List of job dictionaries
        """
        pass
    
    @abstractmethod
    def get_job_description(self, job_url: str) -> str:
        """
        Fetch and parse the full job description from a job URL.
        
        Args:
            job_url: URL of the job posting
            
        Returns:
            str: Job description text
        """
        pass
    
    def get_with_retry(self, url: str, retries: int = 3, delay: int = 1) -> BeautifulSoup:
        """
        Generic method to fetch a URL with retry logic.
        Can be overridden by subclasses if needed.
        
        Args:
            url: URL to fetch
            retries: Number of retry attempts
            delay: Delay between retries in seconds
            
        Returns:
            BeautifulSoup: Parsed HTML content, or None if all retries fail
        """
        for i in range(retries):
            try:
                if len(self.config.get('proxies', {})) > 0:
                    r = requests.get(url, headers=self.config.get('headers', {}), 
                                   proxies=self.config['proxies'], timeout=5)
                else:
                    r = requests.get(url, headers=self.config.get('headers', {}), timeout=5)
                return BeautifulSoup(r.content, 'html.parser')
            except requests.exceptions.Timeout:
                print(f"Timeout occurred for URL: {url}, retrying in {delay}s...")
                tm.sleep(delay)
            except Exception as e:
                print(f"An error occurred while retrieving the URL: {url}, error: {e}")
        return None
    
    def normalize_job(self, job: Dict) -> Dict:
        """
        Normalize job data to ensure consistent format.
        Adds default fields if missing.
        
        Args:
            job: Job dictionary from scraper
            
        Returns:
            Dict: Normalized job dictionary
        """
        normalized = {
            'title': job.get('title', ''),
            'company': job.get('company', ''),
            'location': job.get('location', ''),
            'date': job.get('date', ''),
            'job_url': job.get('job_url', ''),
            'job_description': job.get('job_description', ''),
            'source': self.source_name,
            'applied': job.get('applied', 0),
            'hidden': job.get('hidden', 0),
            'interview': job.get('interview', 0),
            'rejected': job.get('rejected', 0)
        }
        return normalized


