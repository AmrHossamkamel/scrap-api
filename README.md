# Web Scraping API

## Overview

This project is a FastAPI-based web scraping service that crawls websites and extracts article content. The application provides REST API endpoints for initiating web scraping operations on specified domains, with built-in safeguards for rate limiting and domain restrictions.

**Made by Eng: Amr Hossam**

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: FastAPI for REST API development
- **Language**: Python 3.x
- **HTTP Client**: Requests library with session management for connection pooling
- **HTML Parsing**: BeautifulSoup for content extraction and DOM manipulation
- **Data Models**: Pydantic models for request/response validation and serialization

### Core Design Patterns
- **Object-Oriented Design**: WebScraper class encapsulates scraping logic and state management
- **Session Management**: Persistent HTTP sessions for improved performance and connection reuse
- **Rate Limiting**: Built-in timeout controls and maximum page limits to prevent abuse
- **Domain Validation**: URL parsing and domain matching to ensure scraping stays within specified boundaries

### Security & Safety Features
- **User Agent Spoofing**: Mimics browser headers to avoid bot detection
- **Domain Restriction**: Enforces same-domain crawling to prevent unauthorized scraping
- **Request Limits**: Configurable maximum page limits and timeout controls
- **URL Deduplication**: Tracks visited URLs to prevent infinite loops

### Data Processing
- **Content Extraction**: HTML parsing and content extraction from web pages
- **URL Normalization**: Proper URL joining and parsing for link following
- **Structured Output**: Pydantic models ensure consistent API responses

## External Dependencies

### Core Libraries
- **FastAPI**: Web framework for building REST APIs
- **Requests**: HTTP client for web scraping operations
- **BeautifulSoup**: HTML/XML parsing and content extraction
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for running the FastAPI application

### Python Standard Library
- **urllib.parse**: URL parsing and manipulation
- **datetime**: Timestamp generation and timezone handling
- **uuid**: Unique identifier generation
- **logging**: Application logging and debugging
- **typing**: Type hints and annotations

### Potential Integrations
- No database dependencies currently configured
- No external API integrations present
- No authentication services integrated
- No cloud storage or CDN dependencies