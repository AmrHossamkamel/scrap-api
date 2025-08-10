from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Set
import requests
from bs4 import BeautifulSoup
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse
import logging
from pydantic import BaseModel
import uvicorn
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Web Scraping API",
    description="A FastAPI-based web scraping API that crawls websites and extracts article content - Made by Eng: Amr Hossam",
    version="1.0.0"
)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

class ScrapedPage(BaseModel):
    """Model for scraped page data"""
    data: Dict[str, Any]

class WebScraper:
    def __init__(self, base_url: str, timeout: int = 10, max_pages: int = 100):
        self.base_url = base_url
        self.timeout = timeout
        self.max_pages = max_pages
        self.visited_urls: Set[str] = set()
        self.session = requests.Session()
        
        # Set user agent to avoid blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Parse base URL to get domain
        parsed_url = urlparse(base_url)
        self.domain = parsed_url.netloc
        self.scheme = parsed_url.scheme
    
    def is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to the same domain"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.domain or parsed.netloc == f"www.{self.domain}" or parsed.netloc == self.domain.replace("www.", "")
        except Exception:
            return False
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and sorting query parameters"""
        try:
            parsed = urlparse(url)
            # Remove fragment and normalize
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path.rstrip('/') if parsed.path != '/' else parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            return normalized
        except Exception:
            return url
    
    def extract_links(self, html_content: str, base_url: str) -> Set[str]:
        """Extract all internal links from HTML content"""
        links = set()
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all anchor tags with href attributes
            for link in soup.find_all('a', href=True):
                href_attr = link.get('href')
                if not href_attr:
                    continue
                href = str(href_attr).strip()
                if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
                    continue
                
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)
                
                # Check if it's the same domain
                if self.is_same_domain(absolute_url):
                    normalized_url = self.normalize_url(absolute_url)
                    links.add(normalized_url)
        
        except Exception as e:
            logger.error(f"Error extracting links: {e}")
        
        return links
    
    def extract_content(self, html_content: str, url: str) -> Dict[str, Any]:
        """Extract title and content from HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract title
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            else:
                h1_tag = soup.find('h1')
                if h1_tag:
                    title = h1_tag.get_text().strip()
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Extract main content
            content = ""
            
            # Try to find main content areas
            main_content = soup.find('main') or soup.find('article')
            if not main_content:
                # Look for divs with content-related class names
                content_divs = soup.find_all('div', class_=True)
                for div in content_divs:
                    class_names = div.get('class', [])
                    if isinstance(class_names, list):
                        class_str = ' '.join(class_names).lower()
                    else:
                        class_str = str(class_names).lower()
                    
                    if any(word in class_str for word in ['content', 'article', 'post', 'body']):
                        main_content = div
                        break
            
            if main_content:
                content = main_content.get_text(separator=' ', strip=True)
            else:
                # Fallback to body content
                body = soup.find('body')
                if body:
                    content = body.get_text(separator=' ', strip=True)
                else:
                    content = soup.get_text(separator=' ', strip=True)
            
            # Clean up content - remove extra whitespace
            content = ' '.join(content.split())
            
            # Generate unique ID and timestamp
            page_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            return {
                "created_at": created_at,
                "id": page_id,
                "source_url": url,
                "title": title,
                "content": content
            }
        
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return {
                "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "id": str(uuid.uuid4()),
                "source_url": url,
                "title": "",
                "content": f"Error extracting content: {str(e)}"
            }
    
    def scrape_page(self, url: str) -> Dict[str, Any]:
        """Scrape a single page and return extracted data"""
        try:
            logger.info(f"Scraping: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check if content type is HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                logger.warning(f"Skipping non-HTML content: {url}")
                return {
                    "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    "id": str(uuid.uuid4()),
                    "source_url": url,
                    "title": "Non-HTML Content",
                    "content": "Skipped non-HTML content"
                }
            
            return self.extract_content(response.text, url)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            return {
                "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "id": str(uuid.uuid4()),
                "source_url": url,
                "title": "",
                "content": f"Request error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return {
                "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "id": str(uuid.uuid4()),
                "source_url": url,
                "title": "",
                "content": f"Unexpected error: {str(e)}"
            }
    
    def crawl_website(self) -> List[Dict[str, Any]]:
        """Crawl the entire website and return scraped data"""
        scraped_data = []
        urls_to_visit = [self.normalize_url(self.base_url)]
        
        while urls_to_visit and len(scraped_data) < self.max_pages:
            current_url = urls_to_visit.pop(0)
            
            # Skip if already visited
            if current_url in self.visited_urls:
                continue
            
            # Mark as visited
            self.visited_urls.add(current_url)
            
            # Scrape the page
            page_data = self.scrape_page(current_url)
            if page_data:
                scraped_data.append(page_data)
                
                # Extract links only if we successfully scraped the page
                try:
                    response = self.session.get(current_url, timeout=self.timeout)
                    if response.status_code == 200 and 'text/html' in response.headers.get('content-type', '').lower():
                        new_links = self.extract_links(response.text, current_url)
                        
                        # Add new links to visit queue
                        for link in new_links:
                            if link not in self.visited_urls and link not in urls_to_visit:
                                urls_to_visit.append(link)
                
                except Exception as e:
                    logger.error(f"Error extracting links from {current_url}: {e}")
        
        logger.info(f"Crawling completed. Scraped {len(scraped_data)} pages.")
        return scraped_data

@app.get("/")
async def root():
    """Serve the main UI"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    else:
        # Fallback API information if static files don't exist
        return {
            "message": "Web Scraping API",
            "description": "A FastAPI-based web scraping API that crawls websites and extracts article content - Made by Eng: Amr Hossam",
            "endpoints": {
                "/scrape": "POST - Scrape a website for article content",
                "/docs": "GET - API documentation"
            }
        }

@app.get("/api", tags=["System Info"])
async def api_info():
    """API endpoint information and available routes"""
    return {
        "message": "🕷️ Web Scraping API",
        "description": "Advanced web scraping API that crawls websites and extracts article content - Made by Eng: Amr Hossam",
        "endpoints": {
            "/scrape": "🔍 POST - Scrape limited number of pages",
            "/scrape-single": "🎯 POST - Scrape single page only",
            "/scrape-all": "🚀 POST - Scrape ALL pages (unlimited)",
            "/docs": "📚 GET - Interactive API documentation",
            "/health": "💚 GET - System health check",
            "/api": "📊 GET - API information"
        },
        "features": [
            "🕸️ Automatic link discovery",
            "🛡️ Safe with duplicate prevention", 
            "📊 Smart content extraction",
            "⚡ High performance with HTTP sessions",
            "🎯 Support for limited and unlimited scraping"
        ],
        "developer": "👨‍💻 Eng: Amr Hossam",
        "version": "1.0.0"
    }

@app.post("/scrape-single", response_model=ScrapedPage, tags=["Web Scraping"])
async def scrape_single_page(
    url: str = Query(
        ..., 
        description="The URL of the specific page to scrape",
        example="https://example.com/article"
    ),
    timeout: int = Query(
        10, 
        description="Request timeout in seconds for the page", 
        ge=1, 
        le=60,
        example=10
    )
):
    """
    **Extract content from a single page only**
    
    This endpoint scrapes only the specified page without following any links.
    Perfect for extracting content from a specific article or page.
    
    ## Features:
    - 🎯 **Single Page**: Only scrapes the exact URL provided
    - ⚡ **Fast**: No link discovery, direct page scraping
    - 📊 **Smart Extraction**: Same content extraction as full scraping
    - 🛡️ **Safe**: No risk of infinite crawling
    
    ## Parameters:
    - **url**: Exact URL of the page to scrape
    - **timeout**: Timeout in seconds for the request
    
    ## Returns:
    A single scraped page containing:
    - Title and content
    - Source URL
    - Extraction timestamp
    - Unique ID
    
    ## Usage:
    Perfect for scraping specific articles, blog posts, or individual pages
    when you don't need the entire website.
    """
    
    # Validate URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        if parsed_url.scheme not in ['http', 'https']:
            raise HTTPException(status_code=400, detail="URL must use HTTP or HTTPS protocol")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")
    
    try:
        # Initialize scraper just to use its scrape_page method
        scraper = WebScraper(url, timeout=timeout, max_pages=1)
        
        # Scrape only the single page
        page_data = scraper.scrape_page(url)
        
        if not page_data or not page_data.get('content'):
            raise HTTPException(status_code=404, detail="No content could be extracted from the provided URL")
        
        # Format response according to specified structure
        return {
            "data": page_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during single page scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/scrape-all", response_model=List[ScrapedPage], tags=["Web Scraping"])
async def scrape_all_pages(
    url: str = Query(
        ..., 
        description="The base URL of the website to scrape completely",
        example="https://example.com"
    ),
    timeout: int = Query(
        10, 
        description="Request timeout in seconds for each page", 
        ge=1, 
        le=60,
        example=10
    )
):
    """
    **Extract content from ALL pages on a website with no limit**
    
    This endpoint scrapes the entire website by following all internal links
    without any page limit. Perfect for complete website content extraction.
    
    ## Features:
    - 🕸️ **Complete Discovery**: Finds and scrapes every internal page
    - ♾️ **No Limits**: Continues until all pages are discovered
    - 🛡️ **Domain Safe**: Only follows links within the same domain
    - 📊 **Smart Extraction**: Same content extraction as other endpoints
    - 🔄 **Duplicate Prevention**: Avoids visiting the same page twice
    
    ## Parameters:
    - **url**: Base URL of the website to scrape completely
    - **timeout**: Timeout in seconds for each page request
    
    ## Returns:
    A list of ALL scraped pages from the website, each containing:
    - Title and content
    - Source URL
    - Extraction timestamp
    - Unique ID
    
    ## Warning:
    This may take a very long time for large websites and will scrape
    every discoverable page. Use with caution on very large sites.
    """
    
    # Validate URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        if parsed_url.scheme not in ['http', 'https']:
            raise HTTPException(status_code=400, detail="URL must use HTTP or HTTPS protocol")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")
    
    try:
        # Initialize scraper with very high max_pages for unlimited scraping
        scraper = WebScraper(url, timeout=timeout, max_pages=999999)
        
        # Crawl entire website
        scraped_data = scraper.crawl_website()
        
        if not scraped_data:
            raise HTTPException(status_code=404, detail="No content could be scraped from the provided URL")
        
        # Format response according to specified structure
        formatted_response = []
        for page_data in scraped_data:
            formatted_response.append({
                "data": page_data
            })
        
        return formatted_response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during unlimited scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/scrape", response_model=List[ScrapedPage], tags=["Web Scraping"])
async def scrape_website(
    url: str = Query(
        ..., 
        description="The base URL of the website to scrape",
        example="https://example.com"
    ),
    max_pages: int = Query(
        100, 
        description="Maximum number of pages to scrape. Use 999999 or higher for unlimited scraping", 
        ge=1, 
        le=999999,
        example=50
    ),
    timeout: int = Query(
        10, 
        description="Request timeout in seconds for each page", 
        ge=1, 
        le=60,
        example=10
    )
):
    """
    **Extract content from websites**
    
    This API visits the specified website and extracts content from all internal pages.
    
    ## Features:
    - 🕸️ **Auto Discovery**: Follows all internal links automatically
    - 🛡️ **Safe**: Stays within the specified domain only
    - 📊 **Smart Extraction**: Cleans content and extracts titles and text
    - ⚡ **Fast**: Uses persistent HTTP sessions for performance
    - 🔄 **Duplicate Prevention**: Avoids visiting the same page twice
    
    ## Parameters:
    - **url**: Base URL of the website (must start with http or https)
    - **max_pages**: Maximum number of pages to scrape (use 999999+ for unlimited)
    - **timeout**: Timeout in seconds for each page request
    
    ## Returns:
    A list of scraped pages, each containing:
    - Title and content
    - Source URL
    - Extraction timestamp
    - Unique ID
    
    ## Usage Examples:
    - **Limited scraping**: `max_pages=50` to scrape only 50 pages
    - **Unlimited scraping**: `max_pages=999999` to scrape all pages on the website
    """
    
    # Validate URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        if parsed_url.scheme not in ['http', 'https']:
            raise HTTPException(status_code=400, detail="URL must use HTTP or HTTPS protocol")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")
    
    try:
        # Initialize scraper
        scraper = WebScraper(url, timeout=timeout, max_pages=max_pages)
        
        # Crawl website
        scraped_data = scraper.crawl_website()
        
        if not scraped_data:
            raise HTTPException(status_code=404, detail="No content could be scraped from the provided URL")
        
        # Format response according to specified structure
        formatted_response = []
        for page_data in scraped_data:
            formatted_response.append({
                "data": page_data
            })
        
        return formatted_response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/database")
async def database_page():
    """Serve the database management UI"""
    if os.path.exists("static/database.html"):
        return FileResponse("static/database.html")
    else:
        raise HTTPException(status_code=404, detail="Database management page not found")

@app.get("/health", tags=["System Info"])
async def health_check():
    """💚 System health check and API readiness verification"""
    return {
        "status": "healthy",
        "message": "✅ System is running normally",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": "Available 24/7",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )
