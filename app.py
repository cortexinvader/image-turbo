import logging
import os
import uuid
import base64
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from contextlib import contextmanager
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest
import threading

app = Flask(__name__)

# Production configuration
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max upload
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Production logging
if not app.debug:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Paths and config
chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
chromedriver_bin = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")
UPLOAD_FOLDER = os.path.join(app.root_path, 'images')
TEMP_UPLOAD_FOLDER = os.path.join(app.root_path, 'temp_uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

BASE_URL = os.getenv("RENDER_EXTERNAL_URL", f"http://localhost:{os.getenv('PORT', 10000)}")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Production storage
temp_uploads = {}
sessions = {}

@contextmanager
def get_production_driver():
    """Production-optimized Chrome driver"""
    options = Options()
    options.binary_location = chrome_bin
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_argument("--timeout=30")
    
    service = Service(chromedriver_bin, log_path=os.devnull)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except:
            pass

def save_thumbnail(img_src):
    """Production thumbnail saver"""
    if not img_src or img_src == 'None':
        return None
    
    image_id = str(uuid.uuid4())
    try:
        if img_src.startswith('data:image/'):
            header, encoded = img_src.split(',', 1)
            img_data = base64.b64decode(encoded)
            mime_type = header.split(';')[0].split(':')[1]
            ext = '.png' if 'png' in mime_type.lower() else '.jpg'
            filepath = os.path.join(UPLOAD_FOLDER, f"{image_id}{ext}")
            with open(filepath, 'wb') as f:
                f.write(img_data)
        else:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.google.com/',
                'Cache-Control': 'no-cache'
            }
            resp = requests.get(img_src, headers=headers, timeout=15, stream=True)
            if resp.status_code != 200:
                logging.warning(f"Thumbnail download failed {resp.status_code}: {img_src}")
                return None
            
            content_type = resp.headers.get('content-type', '').lower()
            ext = '.png' if 'png' in content_type else '.jpg'
            filepath = os.path.join(UPLOAD_FOLDER, f"{image_id}{ext}")
            
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Production size check
        if os.path.exists(filepath) and os.path.getsize(filepath) > 2 * 1024 * 1024:
            os.unlink(filepath)
            return None
            
        logging.info(f"✅ Thumbnail saved: {image_id}{ext}")
        return f"{BASE_URL}/serve/{image_id}{ext}"
        
    except Exception as e:
        logging.error(f"❌ Thumbnail save failed {img_src[:50]}...: {e}")
        return None

def handle_file_upload(file):
    """Production file upload handler"""
    if not file or file.filename == '':
        return None, {"error": "No file provided"}
    
    filename = secure_filename(file.filename)
    if not allowed_file(filename) or len(filename) > 100:
        return None, {"error": f"Invalid file: {file.filename}"}
    
    upload_id = str(uuid.uuid4())
    original_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    temp_filename = f"{upload_id}.{original_ext}"
    temp_path = os.path.join(TEMP_UPLOAD_FOLDER, temp_filename)
    
    file.save(temp_path)
    file_size = os.path.getsize(temp_path)
    
    if file_size > app.config['MAX_CONTENT_LENGTH']:
        os.unlink(temp_path)
        return None, {"error": "File too large (max 8MB)"}
    
    dummy_url = f"{BASE_URL}/temp/{upload_id}"
    
    temp_uploads[upload_id] = {
        "path": temp_path,
        "original_filename": filename,
        "size_bytes": file_size,
        "expires": datetime.now() + timedelta(hours=1),
        "ip": get_remote_address(request.environ)
    }
    
    logging.info(f"✅ Upload {upload_id}: {file_size}B from {temp_uploads[upload_id]['ip']}")
    return dummy_url, {
        "status": "success",
        "upload_id": upload_id,
        "temp_url": dummy_url,
        "filename": filename,
        "size_bytes": file_size,
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
    }

def cleanup_temp_uploads():
    """Production cleanup"""
    now = datetime.now()
    expired_count = 0
    total_size = 0
    
    for upload_id, info in list(temp_uploads.items()):
        if now > info["expires"]:
            try:
                if os.path.exists(info["path"]):
                    file_size = os.path.getsize(info["path"])
                    os.unlink(info["path"])
                    total_size += file_size
                    expired_count += 1
                logging.info(f"🧹 Cleaned: {info['original_filename']}")
            except Exception as e:
                logging.error(f"Cleanup failed {upload_id}: {e}")
            finally:
                del temp_uploads[upload_id]
    
    if expired_count > 0:
        logging.info(f"🧹 Cleanup: {expired_count} files, {total_size}B freed")

@limiter.limit("10/minute")
def start():
    """Production start function"""
    try:
        with get_production_driver() as driver:
            wait = WebDriverWait(driver, 15)
            
            driver.get("https://images.google.com/")
            logging.info("✅ Navigated to Google Images")
            
            search_by_image_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[jsname="R5mgy"]'))
            )
            search_by_image_btn.click()
            logging.info("✅ Search interface ready")
            
            session_id = str(uuid.uuid4())
            sessions[session_id] = {
                "url": driver.current_url,
                "title": driver.title,
                "timestamp": datetime.now(),
                "expires": datetime.now() + timedelta(minutes=30)
            }
            
            return {
                "status": "success",
                "session_id": session_id,
                "page_title": driver.title,
                "url": driver.current_url,
                "message": "Search session initialized",
                "expires_at": (datetime.now() + timedelta(minutes=30)).isoformat()
            }
            
    except Exception as e:
        logging.error(f"❌ Start failed: {e}")
        return {"error": f"Initialization failed: {str(e)}"}

@limiter.limit("5/minute")
def imgSch(session_id, upload_type="url", value=None):
    """Production search function"""
    if not value:
        return {"error": "Missing image value"}
    
    if upload_type not in ['file', 'url']:
        return {"error": "Invalid type: use 'file' or 'url'"}
    
    try:
        with get_production_driver() as driver:
            wait = WebDriverWait(driver, 15)
            
            driver.get("https://images.google.com/")
            search_by_image_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[jsname="R5mgy"]'))
            )
            search_by_image_btn.click()
            
            if upload_type == "file":
                if not os.path.exists(value) or not os.access(value, os.R_OK):
                    return {"error": f"File not accessible: {value}"}
                
                file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"]')))
                file_input.send_keys(os.path.abspath(value))
                logging.info(f"✅ File search: {os.path.basename(value)}")
                
            else:  # url
                if not (value.startswith('http://') or value.startswith('https://')):
                    return {"error": "URL must start with http:// or https://"}
                
                try:
                    url_tab = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//a[contains(text(), "Paste image link") or contains(text(), "URL")]'))
                    )
                    url_tab.click()
                except:
                    pass
                
                url_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]')))
                url_input.clear()
                url_input.send_keys(value)
                url_input.submit()
                logging.info(f"✅ URL search: {value[:50]}...")
            
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-ri]')), 20)
            time.sleep(3)
            
            return {
                "status": "success",
                "method": upload_type,
                "value": value[:100] + "..." if len(value) > 100 else value,
                "results_url": driver.current_url,
                "completed_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logging.error(f"❌ Search failed: {e}")
        return {"error": f"Search failed: {str(e)}"}

@limiter.limit("5/minute")
def getImg(max_results=20):
    """Production results extraction"""
    try:
        with get_production_driver() as driver:
            wait = WebDriverWait(driver, 15)
            
            # Initialize search
            driver.get("https://images.google.com/")
            search_by_image_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[jsname="R5mgy"]'))
            )
            search_by_image_btn.click()
            
            # Quick test search
            try:
                url_tab = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//a[contains(text(), "Paste image link")]'))
                )
                url_tab.click()
            except:
                pass
            
            url_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]')))
            test_url = "https://picsum.photos/400/300"
            url_input.send_keys(test_url)
            url_input.submit()
            
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-ri]')), 20)
            time.sleep(3)
            
            # Progressive scroll
            for i in range(3):
                driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/3});")
                time.sleep(2 + i)
            
            js_script = f"""
            (() => {{
                const results = [];
                const cards = document.querySelectorAll("div.kb0PBd.cvP2Ce, [data-ri]");
                
                for (let i = 0; i < cards.length && results.length < {max_results}; i++) {{
                    const card = cards[i];
                    
                    const imgEl = card.querySelector("img[src], div.gdOPf img") || card.querySelector("img");
                    let imgSrc = imgEl?.src || null;
                    
                    if (!imgSrc || imgSrc.includes('data:image/gif;base64,R0lGODlh')) continue;
                    
                    const description = card.querySelector("span.Yt787, [data-desc]")?.innerText?.trim() || 
                                       card.querySelector("div[data-lines] span")?.innerText?.trim() || null;
                    
                    let pageLink = card.querySelector("a[href^='http']")?.href || card.querySelector("a")?.href || null;
                    if (pageLink && pageLink.length > 150) {{
                        pageLink = pageLink.slice(0, 150) + "...";
                    }}
                    
                    const sourceSite = card.querySelector(".R8BTeb, cite")?.innerText?.trim() || null;
                    
                    if (imgSrc && description && pageLink && sourceSite) {{
                        results.push({{
                            description: description.length > 200 ? description.slice(0, 200) + "..." : description,
                            thumbnail: imgSrc,
                            pageLink: pageLink,
                            sourceSite: sourceSite
                        }});
                    }}
                }}
                return results;
            }})();
            """
            
            raw_results = driver.execute_script(js_script)
            
            # Retry logic
            retry_count = 0
            while not raw_results and retry_count < 2:
                time.sleep(3)
                raw_results = driver.execute_script(js_script)
                retry_count += 1
            
            processed_results = []
            failed_thumbnails = 0
            
            for raw in raw_results[:max_results]:
                try:
                    thumb_url = save_thumbnail(raw['thumbnail'])
                    if thumb_url:
                        processed = raw.copy()
                        processed['thumbnail'] = thumb_url
                        processed_results.append(processed)
                    else:
                        failed_thumbnails += 1
                except Exception as e:
                    logging.error(f"Result processing failed: {e}")
                    failed_thumbnails += 1
            
            logging.info(f"✅ Extracted {len(processed_results)} results")
            return {
                "status": "success",
                "count": len(processed_results),
                "requested": max_results,
                "failed_thumbnails": failed_thumbnails,
                "results": processed_results
            }
            
    except Exception as e:
        logging.error(f"❌ Extraction failed: {e}")
        return {"error": f"Extraction failed: {str(e)}", "count": 0, "results": []}

# PRODUCTION ROUTES - GET-FIRST

@app.route('/', methods=['GET'])
def index():
    """Production frontend"""
    return render_template('index.html')

@app.route('/start', methods=['GET'])
@limiter.limit("10/minute")
def api_start():
    """GET-only start - browser friendly"""
    result = start()
    if "error" in result:
        return jsonify(result), 500
    
    response = jsonify(result)
    response.headers['Cache-Control'] = 'public, max-age=300'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response, 200

@app.route('/search', methods=['GET', 'POST'])
@limiter.limit("5/minute")
def api_search():
    """GET-first search endpoint"""
    try:
        # GET support (primary)
        if request.method == 'GET':
            session_id = request.args.get('session_id')
            upload_type = request.args.get('type', 'url')
            value = request.args.get('value') or request.args.get('url')
        
        # POST support
        else:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON required"}), 400
            session_id = data.get('session_id')
            upload_type = data.get('type', 'url')
            value = data.get('value') or data.get('url')
        
        if not session_id:
            return jsonify({
                "error": "Missing session_id",
                "get_usage": "/start",
                "post_usage": "POST /search with {'session_id': '...'}"
            }), 400
        
        if not value:
            return jsonify({
                "error": "Missing 'value'",
                "get_usage": "?session_id=abc&value=URL",
                "post_usage": "{'value': 'URL'}"
            }), 400
        
        result = imgSch(session_id, upload_type, value)
        if "error" in result:
            return jsonify(result), 500
        
        response = jsonify(result)
        if request.method == 'GET':
            response.headers['Cache-Control'] = 'public, max-age=600'
        
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
        
    except Exception as e:
        logging.error(f"Search error: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/results', methods=['GET'])
@limiter.limit("5/minute")
def api_results():
    """Pure GET results - bookmarkable"""
    try:
        max_results = request.args.get('max_results', 20, type=int)
        if max_results > 50:
            max_results = 50
        
        result = getImg(max_results=max_results)
        if "error" in result:
            return jsonify(result), 500
        
        response = jsonify(result)
        response.headers['Cache-Control'] = 'public, max-age=1800'
        response.headers['Vary'] = 'max_results'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
        
    except Exception as e:
        logging.error(f"Results error: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/full-search', methods=['GET', 'POST'])
@limiter.limit("3/minute")
def api_full_search():
    """GET-first full search - shareable URLs"""
    try:
        # GET primary support
        if request.method == 'GET':
            search_type = request.args.get('type', 'url')
            value = request.args.get('value') or request.args.get('url')
            max_results = request.args.get('max_results', 20, type=int)
            session_id = request.args.get('session_id')
        
        # POST fallback
        else:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON required"}), 400
            search_type = data.get('type', 'url')
            value = data.get('value') or data.get('url')
            max_results = data.get('max_results', 20)
            session_id = data.get('session_id')
        
        if not value:
            return jsonify({
                "error": "Missing 'value'",
                "get_example": "/full-search?value=https://example.com/image.jpg",
                "post_example": "{'value': 'https://example.com/image.jpg'}"
            }), 400
        
        if max_results > 50:
            max_results = 50
        
        if search_type not in ['url', 'file']:
            return jsonify({"error": "Type must be 'url' or 'file'"}), 400
        
        # Handle file uploads (POST only)
        search_value = value
        upload_info = None
        
        if search_type == 'file':
            if request.method != 'POST' or 'file' not in request.files:
                return jsonify({
                    "error": "File uploads require POST multipart",
                    "usage": "POST /full-search -F 'file=@image.jpg'"
                }), 400
            
            file = request.files['file']
            if not file or file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            dummy_url, upload_result = handle_file_upload(file)
            if not dummy_url:
                return jsonify(upload_result), 400
            
            search_value = dummy_url
            upload_info = upload_result
        
        # Validate URL
        if search_type == 'url' and not (search_value.startswith('http://') or search_value.startswith('https://')):
            return jsonify({
                "error": "URL must start with http:// or https://",
                "example": "/full-search?value=https://picsum.photos/400/300"
            }), 400
        
        # Start session
        if not session_id:
            start_result = start()
            if "error" in start_result:
                return jsonify(start_result), 500
            session_id = start_result["session_id"]
        else:
            start_result = {
                "status": "success",
                "session_id": session_id,
                "message": "Using existing session"
            }
        
        # Search
        search_result = imgSch(session_id, 'url', search_value)
        if "error" in search_result:
            return jsonify(search_result), 500
        
        # Results
        results = getImg(max_results=max_results)
        
        response_data = {
            "status": "success",
            "session_id": session_id,
            "type": search_type,
            "search_value": search_value,
            "start": start_result,
            "search": search_result,
            "results": results
        }
        
        if upload_info:
            response_data["upload_info"] = upload_info
        
        response = jsonify(response_data)
        
        # GET caching
        if request.method == 'GET':
            cache_duration = 1800 if search_type == 'url' else 300
            response.headers['Cache-Control'] = f'public, max-age={cache_duration}'
            response.headers['Vary'] = 'type,value'
        
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
        
    except Exception as e:
        logging.error(f"Full search error: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/upload', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def api_upload():
    """Upload endpoint with GET docs"""
    try:
        if request.method == 'GET':
            return jsonify({
                "usage": "POST multipart/form-data with 'file' field",
                "max_size": "8MB",
                "allowed_types": list(ALLOWED_EXTENSIONS),
                "example": "curl -X POST -F 'file=@image.jpg' /upload",
                "response_format": {
                    "status": "success",
                    "upload_id": "uuid-string",
                    "temp_url": "https://domain.com/temp/uuid",
                    "filename": "original.jpg",
                    "size_bytes": 123456,
                    "expires_at": "2024-01-01T12:00:00Z"
                }
            }), 200
        
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        dummy_url, upload_result = handle_file_upload(file)
        if not dummy_url:
            return jsonify(upload_result), 400
        
        response = jsonify(upload_result)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
        
    except Exception as e:
        logging.error(f"Upload error: {e}")
        return jsonify({"error": "Upload failed"}), 500

@app.route('/serve/<path:filename>')
def serve_image(filename):
    """Secure image serving"""
    try:
        if not (filename.endswith('.jpg') or filename.endswith('.png')):
            return "Invalid file", 403
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.abspath(filepath).startswith(os.path.abspath(UPLOAD_FOLDER)):
            return "Access denied", 403
        
        if not os.path.exists(filepath):
            return "Not found", 404
        
        response = send_from_directory(UPLOAD_FOLDER, filename, max_age=3600)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except Exception as e:
        logging.error(f"Serve error: {e}")
        return "Server error", 500

@app.route('/temp/<upload_id>')
def serve_temp_upload(upload_id):
    """Temp file serving"""
    try:
        if upload_id not in temp_uploads:
            return jsonify({"error": "Not found"}), 404
        
        info = temp_uploads[upload_id]
        if datetime.now() > info["expires"]:
            try:
                if os.path.exists(info["path"]):
                    os.unlink(info["path"])
                del temp_uploads[upload_id]
            except:
                pass
            return jsonify({"error": "Expired"}), 404
        
        filepath = os.path.join(TEMP_UPLOAD_FOLDER, os.path.basename(info["path"]))
        if not os.path.abspath(filepath).startswith(os.path.abspath(TEMP_UPLOAD_FOLDER)):
            return "Access denied", 403
        
        response = send_from_directory(
            TEMP_UPLOAD_FOLDER, 
            os.path.basename(info["path"]), 
            max_age=3600
        )
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        logging.error(f"Temp serve error: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/health', methods=['GET'])
def health():
    """Production health check"""
    cleanup_temp_uploads()
    
    disk_usage = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f)) 
                    for f in os.listdir(UPLOAD_FOLDER) 
                    if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)))
    
    temp_usage = sum(info["size_bytes"] for info in temp_uploads.values())
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "storage": {
            "thumbnails": len(os.listdir(UPLOAD_FOLDER)),
            "thumbnails_size_mb": round(disk_usage / (1024*1024), 1),
            "temp_uploads": len(temp_uploads),
            "temp_size_mb": round(temp_usage / (1024*1024), 1)
        },
        "endpoints": {
            "frontend": "GET /",
            "start": "GET /start",
            "search": "GET/POST /search",
            "results": "GET /results",
            "full-search": "GET/POST /full-search",
            "upload": "POST /upload"
        },
        "limits": {
            "start": "10/minute",
            "search": "5/minute",
            "full-search": "3/minute",
            "upload": "10/minute"
        }
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics"""
    cleanup_temp_uploads()
    
    disk_usage = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f)) 
                    for f in os.listdir(UPLOAD_FOLDER) 
                    if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)))
    
    temp_usage = sum(info["size_bytes"] for info in temp_uploads.values())
    
    metrics = [
        '# HELP reverse_image_search_requests_total Total requests',
        '# TYPE reverse_image_search_requests_total counter',
        f'reverse_image_search_requests_total {{type="total"}} {len(sessions) + len(temp_uploads)}',
        f'# HELP reverse_image_search_storage_bytes Storage usage',
        '# TYPE reverse_image_search_storage_bytes gauge',
        f'reverse_image_search_storage_bytes {{type="thumbnails"}} {disk_usage}',
        f'reverse_image_search_storage_bytes {{type="temp"}} {temp_usage}',
        f'# HELP reverse_image_search_sessions_active Active sessions',
        '# TYPE reverse_image_search_sessions_active gauge',
        f'reverse_image_search_sessions_active {len(sessions)}',
        f'# HELP reverse_image_search_uploads_active Active uploads',
        '# TYPE reverse_image_search_uploads_active gauge',
        f'reverse_image_search_uploads_active {len(temp_uploads)}'
    ]
    
    return '\n'.join(metrics), 200, {'Content-Type': 'text/plain; version=0.0.4'}

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large (max 8MB)"}), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Please wait."}), 429

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

def scheduled_cleanup():
    """Background cleanup"""
    while True:
        time.sleep(300)  # 5 minutes
        cleanup_temp_uploads()

if __name__ == '__main__':
    cleanup_temp_uploads()
    
    # Start cleanup thread
    if not app.debug:
        cleanup_thread = threading.Thread(target=scheduled_cleanup, daemon=True)
        cleanup_thread.start()
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 10000))
    
    app.run(host=host, port=port, debug=app.debug, threaded=True)
