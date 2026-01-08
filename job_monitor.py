#!/usr/bin/env python3
"""
Job Monitor - Monitors company job pages and sends Telegram notifications for new postings.
"""

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Represents a job posting."""
    title: str
    url: str
    company: str
    found_at: str
    description: str = ""
    
    @property
    def id(self) -> str:
        """Generate unique ID for the job based on URL and title."""
        content = f"{self.url}{self.title}".lower()
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class JobSource:
    """Configuration for a job source website."""
    name: str
    url: str
    keywords: list[str] = None  # Optional keyword filters
    exclude_keywords: list[str] = None  # Keywords to exclude
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.exclude_keywords is None:
            self.exclude_keywords = []


class TelegramNotifier:
    """Sends notifications via Telegram."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat."""
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": False
                },
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def notify_new_job(self, job: Job) -> bool:
        """Send notification about a new job posting."""
        message = (
            f"🆕 <b>New Job Posted!</b>\n\n"
            f"🏢 <b>Company:</b> {job.company}\n"
            f"💼 <b>Position:</b> {job.title}\n"
            f"🔗 <a href=\"{job.url}\">View Job</a>\n"
            f"📅 Found: {job.found_at}"
        )
        if job.description:
            # Truncate description if too long
            desc = job.description[:200] + "..." if len(job.description) > 200 else job.description
            message += f"\n\n📝 {desc}"
        
        return self.send_message(message)


class JobScraper:
    """Flexible job scraper that works with various website structures."""
    
    # Common patterns for job listings across different sites
    JOB_LINK_PATTERNS = [
        # Common URL patterns for job pages
        r'/jobs?/',
        r'/careers?/',
        r'/positions?/',
        r'/openings?/',
        r'/vacancies?/',
        r'/opportunities?/',
        r'/job-',
        r'/career-',
        r'/apply',
        r'jobid=',
        r'job_id=',
        r'position_id=',
        r'/job/\d+',
        r'/jobs/\d+',
    ]
    
    # Common CSS selectors for job listings
    JOB_SELECTORS = [
        # Common job listing containers
        '[class*="job-list"] a',
        '[class*="jobs-list"] a',
        '[class*="career"] a',
        '[class*="opening"] a',
        '[class*="position"] a',
        '[class*="vacancy"] a',
        '[data-job] a',
        '[data-position] a',
        # Lever/Greenhouse (common ATS platforms)
        '.posting a',
        '.posting-title a',
        '[data-qa="posting-name"] a',
        '.job-post a',
        # Workday
        '[data-automation-id="jobTitle"] a',
        # General list patterns
        'ul.jobs li a',
        'ul.positions li a',
        '.job-card a',
        '.job-item a',
        '.job-listing a',
        # Table-based listings
        'table.jobs a',
        'tr.job a',
        # Common frameworks
        '[class*="JobCard"] a',
        '[class*="job-card"] a',
        '[class*="JobListing"] a',
        '[class*="job-listing"] a',
    ]
    
    # Title-specific selectors
    TITLE_SELECTORS = [
        'h1', 'h2', 'h3', 'h4',
        '[class*="title"]',
        '[class*="name"]',
        '[class*="position"]',
        '[class*="role"]',
    ]
    
    def __init__(self, user_agent: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent or (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def is_job_url(self, url: str, base_url: str) -> bool:
        """Check if a URL looks like a job posting link."""
        url_lower = url.lower()
        
        # Check against common job URL patterns
        for pattern in self.JOB_LINK_PATTERNS:
            if re.search(pattern, url_lower):
                return True
        
        return False
    
    def extract_job_title(self, element) -> str:
        """Extract job title from a link element."""
        # Try to find title in child elements
        for selector in self.TITLE_SELECTORS:
            title_elem = element.select_one(selector)
            if title_elem and title_elem.get_text(strip=True):
                return title_elem.get_text(strip=True)
        
        # Fall back to link text
        text = element.get_text(strip=True)
        if text:
            return text
        
        # Try title attribute
        return element.get('title', '') or element.get('aria-label', '')
    
    def extract_description(self, element) -> str:
        """Extract job description snippet from element context."""
        parent = element.parent
        if parent:
            # Look for description in siblings or parent
            desc_elem = parent.select_one('[class*="description"], [class*="summary"], p')
            if desc_elem:
                return desc_elem.get_text(strip=True)
        return ""
    
    def scrape_jobs(self, source: JobSource) -> list[Job]:
        """Scrape jobs from a source URL."""
        soup = self.fetch_page(source.url)
        if not soup:
            return []
        
        jobs = []
        seen_urls = set()
        base_url = f"{urlparse(source.url).scheme}://{urlparse(source.url).netloc}"
        
        # Method 1: Use specific selectors
        for selector in self.JOB_SELECTORS:
            try:
                links = soup.select(selector)
                for link in links:
                    job = self._process_link(link, source, base_url, seen_urls)
                    if job:
                        jobs.append(job)
            except Exception:
                continue
        
        # Method 2: Find all links and filter by URL pattern (if few jobs found)
        if len(jobs) < 3:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                full_url = urljoin(base_url, href)
                
                if self.is_job_url(full_url, base_url):
                    job = self._process_link(link, source, base_url, seen_urls)
                    if job:
                        jobs.append(job)
        
        logger.info(f"Found {len(jobs)} jobs from {source.name}")
        return jobs
    
    def _process_link(self, link, source: JobSource, base_url: str, seen_urls: set) -> Optional[Job]:
        """Process a link element and return a Job if valid."""
        href = link.get('href', '')
        if not href or href.startswith('#') or href.startswith('javascript:'):
            return None
        
        full_url = urljoin(base_url, href)
        
        # Skip if already processed
        if full_url in seen_urls:
            return None
        seen_urls.add(full_url)
        
        # Extract title
        title = self.extract_job_title(link)
        if not title or len(title) < 3:
            return None
        
        # Skip navigation/generic links
        skip_texts = ['apply', 'learn more', 'read more', 'view all', 'see all', 'back', 'next', 'previous']
        if title.lower() in skip_texts:
            return None
        
        # Apply keyword filters
        if source.keywords:
            title_lower = title.lower()
            if not any(kw.lower() in title_lower for kw in source.keywords):
                return None
        
        if source.exclude_keywords:
            title_lower = title.lower()
            if any(kw.lower() in title_lower for kw in source.exclude_keywords):
                return None
        
        description = self.extract_description(link)
        
        return Job(
            title=title,
            url=full_url,
            company=source.name,
            found_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            description=description
        )


class JobMonitor:
    """Main job monitoring service."""
    
    def __init__(self, config_path: str = "config.json", data_dir: str = "data"):
        self.config_path = Path(config_path)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.seen_jobs_file = self.data_dir / "seen_jobs.json"
        
        self.config = self._load_config()
        self.seen_jobs = self._load_seen_jobs()
        
        self.scraper = JobScraper()
        self.notifier = None
        
        if self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
            self.notifier = TelegramNotifier(
                self.config['telegram_bot_token'],
                self.config['telegram_chat_id']
            )
    
    def _load_config(self) -> dict:
        """Load configuration from file or environment."""
        config = {
            'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
            'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
            'check_interval_minutes': int(os.getenv('CHECK_INTERVAL', '60')),
            'sources': []
        }
        
        if self.config_path.exists():
            with open(self.config_path) as f:
                file_config = json.load(f)
                config.update(file_config)
        
        return config
    
    def _load_seen_jobs(self) -> set:
        """Load previously seen job IDs."""
        if self.seen_jobs_file.exists():
            with open(self.seen_jobs_file) as f:
                return set(json.load(f))
        return set()
    
    def _save_seen_jobs(self):
        """Save seen job IDs to file."""
        with open(self.seen_jobs_file, 'w') as f:
            json.dump(list(self.seen_jobs), f)
    
    def check_for_new_jobs(self) -> list[Job]:
        """Check all sources for new jobs."""
        new_jobs = []
        
        for source_config in self.config.get('sources', []):
            source = JobSource(
                name=source_config['name'],
                url=source_config['url'],
                keywords=source_config.get('keywords', []),
                exclude_keywords=source_config.get('exclude_keywords', [])
            )
            
            try:
                jobs = self.scraper.scrape_jobs(source)
                
                for job in jobs:
                    if job.id not in self.seen_jobs:
                        new_jobs.append(job)
                        self.seen_jobs.add(job.id)
                        logger.info(f"New job found: {job.title} at {job.company}")
                
            except Exception as e:
                logger.error(f"Error checking {source.name}: {e}")
            
            # Be nice to servers
            time.sleep(2)
        
        self._save_seen_jobs()
        return new_jobs
    
    def notify_new_jobs(self, jobs: list[Job]):
        """Send notifications for new jobs."""
        if not self.notifier:
            logger.warning("Telegram not configured, skipping notifications")
            return
        
        for job in jobs:
            success = self.notifier.notify_new_job(job)
            if success:
                logger.info(f"Notification sent for: {job.title}")
            time.sleep(1)  # Rate limiting
    
    def run_once(self):
        """Run a single check cycle."""
        logger.info("Checking for new jobs...")
        new_jobs = self.check_for_new_jobs()
        
        if new_jobs:
            logger.info(f"Found {len(new_jobs)} new job(s)")
            self.notify_new_jobs(new_jobs)
        else:
            logger.info("No new jobs found")
        
        return new_jobs
    
    def run_continuous(self):
        """Run continuously, checking at intervals."""
        interval = self.config.get('check_interval_minutes', 60) * 60
        
        logger.info(f"Starting job monitor (checking every {interval // 60} minutes)")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Error during check cycle: {e}")
            
            logger.info(f"Next check in {interval // 60} minutes")
            time.sleep(interval)


def create_sample_config():
    """Create a sample configuration file."""
    sample_config = {
        "telegram_bot_token": "YOUR_BOT_TOKEN_HERE",
        "telegram_chat_id": "YOUR_CHAT_ID_HERE",
        "check_interval_minutes": 60,
        "sources": [
            {
                "name": "Example Company",
                "url": "https://example.com/careers",
                "keywords": ["engineer", "developer", "python"],
                "exclude_keywords": ["senior", "manager"]
            },
            {
                "name": "Another Company",
                "url": "https://another.com/jobs",
                "keywords": [],
                "exclude_keywords": []
            }
        ]
    }
    
    with open("config.json", "w") as f:
        json.dump(sample_config, f, indent=2)
    
    print("Sample config.json created! Edit it with your settings.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        create_sample_config()
    elif len(sys.argv) > 1 and sys.argv[1] == "--once":
        monitor = JobMonitor()
        monitor.run_once()
    else:
        monitor = JobMonitor()
        monitor.run_continuous()
