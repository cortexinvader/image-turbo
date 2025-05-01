from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
import shutil
import subprocess
import requests
import zipfile
import io

# Create a custom logger
logger = logging.getLogger("search_app")
logger.setLevel(logging.DEBUG)

# Create console handler for logging to stderr
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)

# Create a detailed formatter
detailed_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(process)d | %(thread)d | %(name)s | %(module)s | %(funcName)s:%(lineno)d | %(message)s"
)

# Assign formatters to handlers
console_handler.setFormatter(detailed_formatter)

# Add handlers to the logger
logger.addHandler(console_handler)

# If not running on Render, add file handlers
if not os.environ.get("RENDER"):
    # Create log directory
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # Create file handlers
    info_file_handler = RotatingFileHandler(
        os.path.join(log_directory, "app_info.log"),
        maxBytes=10485760,  # 10 MB
        backupCount=10
    )
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(detailed_formatter)
    logger.addHandler(info_file_handler)

    debug_file_handler = RotatingFileHandler(
        os.path.join(log_directory, "app_debug.log"),
        maxBytes=10485760,  # 10 MB
        backupCount=10
    )
    debug_file_handler.setLevel(logging.DEBUG)
    debug_file_handler.setFormatter(detailed_formatter)
    logger.addHandler(debug_file_handler)

    error_file_handler = RotatingFileHandler(
        os.path.join(log_directory, "app_error.log"),
        maxBytes=10485760,  # 10 MB
        backupCount=10
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
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
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "environment": "Render" if os.environ.get("RENDER") else "Unknown"
        }
        logger.info(f"System information: {json.dumps(system_info)}")
    except Exception as e:
        logger.error(f"Failed to log system information: {str(e)}")

# ChromeDriver setup function
def setup_chromedriver():
    """
    Set up ChromeDriver based on the current environment
    Returns: Path to ChromeDriver or None if setup failed
    """
    # Check for environment variable
    if os.environ.get("CHROMEDRIVER_PATH"):
        driver_path = os.environ.get("CHROMEDRIVER_PATH")
        if os.path.exists(driver_path) and os.access(driver_path, os.X_OK):
            logger.info(f"Using ChromeDriver from environment variable: {driver_path}")
            return driver_path
    
    # Check common locations
    common_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/app/chromedriver",
        os.path.join(os.getcwd(), "chromedriver")
    ]
    
    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"Found existing ChromeDriver at: {path}")
            return path
    
    # If we're on Render, we need to download and set up ChromeDriver
    if os.environ.get("RENDER"):
        try:
            return download_chromedriver_for_render()
        except Exception as e:
            logger.error(f"Failed to download ChromeDriver: {str(e)}")
            logger.error(traceback.format_exc())
    
    return None

def download_chromedriver_for_render():
    """
    Download and setup ChromeDriver specifically for Render.com environment
    Returns: Path to the downloaded ChromeDriver
    """
    logger.info("Attempting to download ChromeDriver for Render environment")
    
    # Create a directory for ChromeDriver
    driver_dir = os.path.join(os.getcwd(), "chromedriver_bin")
    if not os.path.exists(driver_dir):
        os.makedirs(driver_dir)
    
    # Path where we'll store ChromeDriver
    driver_path = os.path.join(driver_dir, "chromedriver")
    
    # First, check if Chrome is available
    try:
        # Try the default Chrome on Render
        chrome_paths = [
            "/opt/render/project/.render/chrome/opt/google/chrome/chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium"
        ]
        
        chrome_path = None
        chrome_version = None
        
        for path in chrome_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                chrome_path = path
                try:
                    result = subprocess.run([path, "--version"], capture_output=True, text=True)
                    chrome_version = result.stdout.strip()
                    logger.info(f"Found Chrome at {path}: {chrome_version}")
                    break
                except Exception as e:
                    logger.warning(f"Chrome found at {path} but couldn't get version: {str(e)}")
        
        if not chrome_path:
            # Install Chrome on Render if not found
            logger.info("Chrome not found. Installing Chrome on Render...")
            chrome_install_path = "/opt/render/project/.render/chrome"
            os.makedirs(chrome_install_path, exist_ok=True)
            
            # Download and install Chrome
            chrome_url = "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
            logger.info(f"Downloading Chrome from {chrome_url}")
            response = requests.get(chrome_url)
            deb_path = os.path.join(chrome_install_path, "chrome.deb")
            
            with open(deb_path, "wb") as f:
                f.write(response.content)
            
            # Extract Chrome from the deb package
            logger.info("Extracting Chrome package")
            subprocess.run(["dpkg", "-x", deb_path, chrome_install_path], check=True)
            
            # Set Chrome path
            chrome_path = os.path.join(chrome_install_path, "opt/google/chrome/chrome")
            os.chmod(chrome_path, 0o755)
            
            # Get Chrome version
            result = subprocess.run([chrome_path, "--version"], capture_output=True, text=True)
            chrome_version = result.stdout.strip()
            logger.info(f"Installed Chrome: {chrome_version}")
        
        # Extract major version for ChromeDriver
        if chrome_version:
            major_version = chrome_version.split(" ")[2].split(".")[0]
            logger.info(f"Chrome major version: {major_version}")
            
            # Get matching ChromeDriver version
            logger.info(f"Getting matching ChromeDriver for Chrome {major_version}")
            version_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
            response = requests.get(version_url)
            driver_version = response.text.strip()
            logger.info(f"Downloading ChromeDriver version {driver_version}")
            
            # Download ChromeDriver
            driver_url = f"https://chromedriver.storage.googleapis.com/{driver_version}/chromedriver_linux64.zip"
            response = requests.get(driver_url)
            
            # Extract the zip file
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                zip_file.extractall(driver_dir)
            
            # Make it executable
            os.chmod(driver_path, 0o755)
            logger.info(f"ChromeDriver installed at {driver_path}")
            
            # Set environment variable for future use
            os.environ["CHROMEDRIVER_PATH"] = driver_path
            
            return driver_path
    except Exception as e:
        logger.error(f"Error downloading ChromeDriver: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    
    return None

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
    
    # Specific options needed for Render
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36")
    
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
        # Setup ChromeDriver
        chrome_driver_path = setup_chromedriver()
        if not chrome_driver_path:
            logger.error(f"[{request_id}] ChromeDriver setup failed")
            return jsonify({
                "error": "ChromeDriver setup failed. See server logs for details.",
                "status": "error",
                "request_id": request_id
            }), 500
        
        logger.info(f"[{request_id}] Using ChromeDriver at {chrome_driver_path}")
        
        # Configure Chrome options
        chrome_options = get_chrome_options()
        
        # Initialize the Chrome service
        service = Service(executable_path=chrome_driver_path)
        
        # Initialize the WebDriver
        try:
            logger.debug(f"[{request_id}] Initializing Chrome WebDriver")
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

        # Navigate to Google search
        search_url = f"https://www.google.com/search?q={query}"
        logger.info(f"[{request_id}] Navigating to URL: {search_url}")
        
        try:
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            # Navigate to the search URL
            driver.get(search_url)
            logger.debug(f"[{request_id}] Page loaded, current URL: {driver.current_url}")
            
            # Wait for search results to load (using explicit wait)
            logger.debug(f"[{request_id}] Waiting for search results to load")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source and parse with BeautifulSoup
            page_source = driver.page_source
            page_source_length = len(page_source)
            logger.debug(f"[{request_id}] Retrieved page source ({page_source_length} bytes)")
            
            logger.debug(f"[{request_id}] Parsing page source with BeautifulSoup")
            soup = BeautifulSoup(page_source, "html.parser")
            
            # Find all elements with class "WaaZC"
            logger.debug(f"[{request_id}] Searching for elements with class 'WaaZC'")
            results = soup.find_all(class_="WaaZC")
            
            # If no results found with that class, try a different selector
            if not results:
                logger.debug(f"[{request_id}] No results found with class 'WaaZC', trying alternative selectors")
                # Try alternative selectors that might work for Google search results
                for selector in ["yuRUbf", "g", "rc", "tF2Cxc"]:
                    results = soup.find_all(class_=selector)
                    if results:
                        logger.info(f"[{request_id}] Found {len(results)} results with class '{selector}'")
                        break
                
                # If still no results, try to get any text content as fallback
                if not results:
                    logger.warning(f"[{request_id}] No results found with known selectors, using fallback")
                    # Use a more general approach to find search results
                    results = soup.find_all("div", {"class": True})
                    # Filter for divs that might contain search results (having text and links)
                    results = [div for div in results if div.get_text().strip() and div.find("a")]
            
            logger.info(f"[{request_id}] Found {len(results)} search results")
            
            # Extract text from each result
            logger.debug(f"[{request_id}] Extracting text from search results")
            extracted_texts = []
            for i, result in enumerate(results):
                text = result.get_text().strip()
                if text:  # Only include non-empty results
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

@app.route('/debug')
def debug_info():
    """Debug endpoint to show system environment and paths"""
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))
    logger.info(f"[{request_id}] Debug info requested")
    
    # Get ChromeDriver info
    chromedriver_path = setup_chromedriver()
    chromedriver_info = {
        "path": chromedriver_path,
        "exists": bool(chromedriver_path) and os.path.exists(chromedriver_path),
        "executable": bool(chromedriver_path) and os.path.exists(chromedriver_path) and os.access(chromedriver_path, os.X_OK)
    }
    
    # Get Chrome info
    chrome_info = {"installed": False, "version": None, "path": None}
    chrome_paths = [
        "/opt/render/project/.render/chrome/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium"
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_info["installed"] = True
            chrome_info["path"] = path
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True)
                chrome_info["version"] = result.stdout.strip()
            except:
                chrome_info["version"] = "Error getting version"
            break
    
    # Get system info
    try:
        system_info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "cwd": os.getcwd(),
            "uid": os.getuid()
        }
    except Exception as e:
        system_info = {"error": str(e)}
    
    # List directories to help debug
    dir_listing = {}
    for directory in ["/usr/bin", "/usr/local/bin", os.getcwd(), "/opt/render/project"]:
        try:
            if os.path.exists(directory):
                dir_listing[directory] = os.listdir(directory)
            else:
                dir_listing[directory] = "Directory does not exist"
        except Exception as e:
            dir_listing[directory] = f"Error listing directory: {str(e)}"
    
    debug_data = {
        "environment": dict(os.environ),
        "system_info": system_info,
        "chrome": chrome_info,
        "chromedriver": chromedriver_info,
        "directory_listings": dir_listing,
        "is_render": bool(os.environ.get("RENDER")),
        "request_id": request_id,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    logger.info(f"[{request_id}] Debug info generated")
    return jsonify(debug_data)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))
    logger.info(f"[{request_id}] Health check requested")
    
    # Check for ChromeDriver
    chromedriver_path = setup_chromedriver()
    
    health_data = {
        "status": "healthy" if chromedriver_path else "degraded",
        "timestamp": datetime.datetime.now().isoformat(),
        "chromedriver_exists": bool(chromedriver_path),
        "chromedriver_path": chromedriver_path or "Not found",
        "python_version": platform.python_version(),
        "request_id": request_id
    }
    
    logger.info(f"[{request_id}] Health check: {json.dumps(health_data)}")
    return jsonify(health_data)

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

if __name__ == '__main__':
    try:
        # Log system information at startup
        log_system_info()
        
        # Setup ChromeDriver at startup
        chromedriver_path = setup_chromedriver()
        if chromedriver_path:
            logger.info(f"ChromeDriver setup successful: {chromedriver_path}")
        else:
            logger.warning("ChromeDriver setup failed at startup. Will attempt again during requests.")
        
        # Get port from environment variable or use default
        port = int(os.environ.get("PORT", 3000))
        host = '0.0.0.0'
        
        logger.info(f"Starting Flask app on {host}:{port}")
        logger.info(f"Environment: {'Render' if os.environ.get('RENDER') else 'Local'}")
        
        # Start the Flask app
        app.run(host=host, port=port)
        
    except Exception as e:
        logger.critical(f"Failed to start the application: {str(e)}")
        logger.critical(f"Startup error details: {traceback.format_exc()}")
        sys.exit(1)
