from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import time
import os
import logging
import traceback
import sys
import json
import uuid
import datetime
import socket
import platform
from logging.handlers import RotatingFileHandler
import threading

# Create a custom logger
logger = logging.getLogger("search_app")
logger.setLevel(logging.DEBUG)

# Create handlers
log_directory = "logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Create console handler for logging to stderr
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)

# Create file handler for INFO level and above
info_file_handler = RotatingFileHandler(
    os.path.join(log_directory, "app_info.log"),
    maxBytes=10485760,  # 10 MB
    backupCount=10
)
info_file_handler.setLevel(logging.INFO)

# Create file handler for DEBUG level
debug_file_handler = RotatingFileHandler(
    os.path.join(log_directory, "app_debug.log"),
    maxBytes=10485760,  # 10 MB
    backupCount=10
)
debug_file_handler.setLevel(logging.DEBUG)

# Create file handler for ERROR level
error_file_handler = RotatingFileHandler(
    os.path.join(log_directory, "app_error.log"),
    maxBytes=10485760,  # 10 MB
    backupCount=10
)
error_file_handler.setLevel(logging.ERROR)

# Create a detailed formatter
detailed_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(process)d | %(thread)d | %(name)s | %(module)s | %(funcName)s:%(lineno)d | %(message)s"
)

# Assign formatters to handlers
console_handler.setFormatter(detailed_formatter)
info_file_handler.setFormatter(detailed_formatter)
debug_file_handler.setFormatter(detailed_formatter)
error_file_handler.setFormatter(detailed_formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(info_file_handler)
logger.addHandler(debug_file_handler)
logger.addHandler(error_file_handler)

# Initialize Flask app
app = Flask(__name__)

# Add logging to Flask app
app.logger.handlers = logger.handlers
app.logger.setLevel(logging.DEBUG)

# System info at startup
def log_system_info():
    """Log detailed system information at startup"""
    try:
        system_info = {
            "hostname": socket.gethostname(),
            "ip_address": socket.gethostbyname(socket.gethostname()),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "memory": f"{os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')/(1024.**3):.1f} GB" if hasattr(os, 'sysconf') else "Unknown",
            "cpu_count": os.cpu_count()
        }
        logger.info(f"System information: {json.dumps(system_info)}")
    except Exception as e:
        logger.error(f"Failed to log system information: {str(e)}")

def get_chrome_options():
    """
    Configure and return Chrome options for Selenium WebDriver
    """
    logger.debug("Setting up Chrome options")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # Log all options for debugging
    logger.debug(f"Chrome options configured: {chrome_options.arguments}")
    return chrome_options

@app.before_request
def log_request_info():
    """Log detailed information for each incoming request"""
    request_id = str(uuid.uuid4())
    # Store request ID in g object for access in other functions
    request.request_id = request_id
    
    # Create structured log entry
    log_data = {
        "request_id": request_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "method": request.method,
        "path": request.path,
        "query_string": request.query_string.decode('utf-8'),
        "headers": dict(request.headers),
        "remote_addr": request.remote_addr,
        "args": dict(request.args)
    }
    
    # Log the request details
    logger.info(f"Request received: {json.dumps(log_data)}")

@app.after_request
def log_response_info(response):
    """Log information about the response being sent"""
    # Extract request_id if available
    request_id = getattr(request, 'request_id', 'unknown')
    
    # Don't log binary responses or large bodies
    response_body = response.get_data(as_text=True) if response.content_type and 'json' in response.content_type and len(response.get_data()) < 1000 else "[Response body too large or binary]"
    
    log_data = {
        "request_id": request_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "status_code": response.status_code,
        "content_type": response.content_type,
        "content_length": response.content_length,
        "response_body": response_body
    }
    
    logger.info(f"Response sent: {json.dumps(log_data)}")
    return response

@app.route('/search')
def search():
    """
    API endpoint to search Google and return results
    """
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))
    query = request.args.get('q', '')
    logger.info(f"[{request_id}] Search request with query: '{query}'")

    if not query:
        logger.warning(f"[{request_id}] Empty search query received")
        return jsonify({"error": "Please provide a search query using '?q=your_query'", "request_id": request_id}), 400

    start_time = time.time()
    driver = None
    
    try:
        logger.debug(f"[{request_id}] Initializing Chrome WebDriver")
        chrome_options = get_chrome_options()
        chrome_driver_path = "/usr/bin/chromedriver"
        
        if not os.path.exists(chrome_driver_path):
            logger.error(f"[{request_id}] ChromeDriver not found at {chrome_driver_path}")
            return jsonify({
                "error": f"ChromeDriver not found at {chrome_driver_path}",
                "status": "error",
                "request_id": request_id
            }), 500
            
        logger.debug(f"[{request_id}] Creating Service with ChromeDriver at {chrome_driver_path}")
        service = Service(chrome_driver_path)
        
        try:
            logger.debug(f"[{request_id}] Initializing Chrome WebDriver with service and options")
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info(f"[{request_id}] Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to initialize Chrome WebDriver: {str(e)}")
            logger.debug(f"[{request_id}] Chrome WebDriver error details: {traceback.format_exc()}")
            return jsonify({
                "error": f"Failed to initialize Chrome WebDriver: {str(e)}",
                "status": "error",
                "request_id": request_id
            }), 500

        search_url = f"https://www.google.com/search?q={query}"
        logger.info(f"[{request_id}] Navigating to URL: {search_url}")
        
        try:
            driver.get(search_url)
            logger.debug(f"[{request_id}] Page loaded, current URL: {driver.current_url}")
            
            # Wait for page to load
            logger.debug(f"[{request_id}] Waiting {5} seconds for page content to load")
            time.sleep(5)
            
            # Get page source and parse with BeautifulSoup
            page_source = driver.page_source
            page_source_length = len(page_source)
            logger.debug(f"[{request_id}] Retrieved page source ({page_source_length} bytes)")
            
            logger.debug(f"[{request_id}] Parsing page source with BeautifulSoup")
            soup = BeautifulSoup(page_source, "html.parser")
            
            # Find all elements with class "WaaZC"
            logger.debug(f"[{request_id}] Searching for elements with class 'WaaZC'")
            results = soup.find_all(class_="WaaZC")
            logger.info(f"[{request_id}] Found {len(results)} search results")
            
            # Extract text from each result
            logger.debug(f"[{request_id}] Extracting text from search results")
            extracted_texts = []
            for i, result in enumerate(results):
                text = result.get_text()
                logger.debug(f"[{request_id}] Result #{i+1}: {text[:50]}...")
                extracted_texts.append(text)
            
        except Exception as e:
            logger.error(f"[{request_id}] Error during web scraping: {str(e)}")
            logger.debug(f"[{request_id}] Web scraping error details: {traceback.format_exc()}")
            return jsonify({
                "error": f"Error during web scraping: {str(e)}",
                "status": "error",
                "request_id": request_id
            }), 500
        finally:
            if driver:
                logger.debug(f"[{request_id}] Quitting Chrome WebDriver")
                driver.quit()
                logger.info(f"[{request_id}] Chrome WebDriver quit successfully")

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        logger.info(f"[{request_id}] Search completed in {elapsed_time:.2f} seconds")
        
        # Return results
        response_data = {
            "query": query,
            "results": extracted_texts,
            "count": len(extracted_texts),
            "status": "success",
            "request_id": request_id,
            "elapsed_time_seconds": elapsed_time
        }
        
        logger.info(f"[{request_id}] Returning {len(extracted_texts)} results for query '{query}'")
        return jsonify(response_data)

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.critical(f"[{request_id}] Unhandled exception: {str(e)}")
        logger.critical(f"[{request_id}] Exception details: {traceback.format_exc()}")
        
        return jsonify({
            "error": str(e),
            "status": "error",
            "request_id": request_id,
            "elapsed_time_seconds": elapsed_time
        }), 500

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))
    logger.warning(f"[{request_id}] 404 error: {request.path}")
    return jsonify({
        "error": "Route not found",
        "status": "error",
        "request_id": request_id
    }), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))
    logger.error(f"[{request_id}] 500 error: {str(e)}")
    return jsonify({
        "error": "Internal server error",
        "status": "error",
        "request_id": request_id
    }), 500

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))
    logger.debug(f"[{request_id}] Health check requested")
    
    # Check if chromedriver exists
    chrome_driver_path = "/usr/bin/chromedriver"
    chromedriver_exists = os.path.exists(chrome_driver_path)
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "chromedriver_exists": chromedriver_exists,
        "chromedriver_path": chrome_driver_path,
        "python_version": platform.python_version(),
        "request_id": request_id
    }
    
    logger.info(f"[{request_id}] Health check: {json.dumps(health_data)}")
    return jsonify(health_data)

# Performance monitoring middleware
@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def log_request_performance(response):
    if hasattr(request, 'start_time'):
        elapsed_time = time.time() - request.start_time
        request_id = getattr(request, 'request_id', 'unknown')
        logger.info(f"[{request_id}] Request performance: {request.method} {request.path} completed in {elapsed_time:.4f} seconds")
    return response

if __name__ == '__main__':
    try:
        # Log system information at startup
        log_system_info()
        
        # Get port from environment variable or use default
        port = int(os.environ.get("PORT", 3000))
        host = '0.0.0.0'
        
        logger.info(f"Starting Flask app on {host}:{port}")
        logger.info(f"Log files will be stored in: {os.path.abspath(log_directory)}")
        
        # Start the Flask app
        app.run(host=host, port=port)
        
    except Exception as e:
        logger.critical(f"Failed to start the application: {str(e)}")
        logger.critical(f"Startup error details: {traceback.format_exc()}")
        sys.exit(1)
