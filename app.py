import logging
import os
import uuid
import base64
import time
import requests
from flask import Flask, jsonify, request, send_from_directory,render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from contextlib import contextmanager
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Paths and config
chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
chromedriver_bin = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")
UPLOAD_FOLDER = 'images'
TEMP_UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Track temporary uploads for cleanup
temp_uploads = {}

# Context manager for per-request driver
@contextmanager
def get_driver():
    options = Options()
    options.binary_location = chrome_bin
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/116.0.0.0 Safari/537.36"
    )
    service = Service(chromedriver_bin)
    driver = webdriver.Chrome(service=service, options=options)
    try:
        yield driver
    finally:
        driver.quit()

# Function to save thumbnail and return serve URL
def save_thumbnail(img_src):
    if not img_src or img_src == 'None':
        return None
    image_id = str(uuid.uuid4())
    try:
        if img_src.startswith('data:image/'):
            # Decode base64
            header, encoded = img_src.split(',', 1)
            img_data = base64.b64decode(encoded)
            mime_type = header.split(';')[0].split(':')[1]
            ext = '.png' if 'png' in mime_type.lower() else '.jpg'
            filepath = os.path.join(UPLOAD_FOLDER, f"{image_id}{ext}")
            with open(filepath, 'wb') as f:
                f.write(img_data)
        else:
            # Download image
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
            }
            resp = requests.get(img_src, headers=headers, timeout=10)
            if resp.status_code != 200:
                logging.warning(f"Failed to download thumbnail: {img_src}")
                return None
            content_type = resp.headers.get('content-type', '').lower()
            ext = '.png' if 'png' in content_type else '.jpg'
            filepath = os.path.join(UPLOAD_FOLDER, f"{image_id}{ext}")
            with open(filepath, 'wb') as f:
                f.write(resp.content)
        logging.info(f"✅ Saved thumbnail: {image_id}{ext}")
        return f"{BASE_URL}/serve/{image_id}{ext}"
    except Exception as e:
        logging.error(f"❌ Failed to save thumbnail {img_src}: {e}")
        return None

# Handle file upload and create temp URL
def handle_file_upload(file):
    """Convert uploaded file to temporary URL"""
    if not file or file.filename == '':
        return None, {"error": "No file provided"}
    
    if not allowed_file(file.filename):
        return None, {"error": f"Invalid file type: {file.filename}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}
    
    # Create unique ID
    upload_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    original_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    temp_filename = f"{upload_id}.{original_ext}"
    temp_path = os.path.join(TEMP_UPLOAD_FOLDER, temp_filename)
    
    # Save uploaded file
    file.save(temp_path)
    file_size = os.path.getsize(temp_path)
    
    # Create dummy URL
    dummy_url = f"{BASE_URL}/temp/{upload_id}"
    
    # Track for cleanup (1 hour expiry)
    temp_uploads[upload_id] = {
        "path": temp_path,
        "original_filename": filename,
        "size_bytes": file_size,
        "expires": datetime.now() + timedelta(hours=1)
    }
    
    logging.info(f"✅ File uploaded: {filename} ({file_size}B) → {dummy_url}")
    return dummy_url, {
        "status": "success",
        "upload_id": upload_id,
        "temp_url": dummy_url,
        "filename": filename,
        "size_bytes": file_size
    }

# Cleanup expired temp uploads
def cleanup_temp_uploads():
    now = datetime.now()
    expired_count = 0
    for upload_id, info in list(temp_uploads.items()):
        if now > info["expires"]:
            try:
                if os.path.exists(info["path"]):
                    os.unlink(info["path"])
                    expired_count += 1
                logging.info(f"🧹 Cleaned expired upload: {info['original_filename']}")
            except Exception as e:
                logging.error(f"Failed to cleanup {upload_id}: {e}")
            del temp_uploads[upload_id]
    if expired_count > 0:
        logging.info(f"🧹 Cleanup: removed {expired_count} expired uploads")

# PATH 1: Direct URL search
def search_by_url_direct(image_url, max_results=20):
    """Direct URL search - no file handling"""
    if not image_url.startswith(('http://', 'https://')):
        return {"error": "Invalid URL format. Must start with http:// or https://"}
    
    try:
        with get_driver() as driver:
            wait = WebDriverWait(driver, 10)
            
            # Navigate to Google Images
            driver.get("https://images.google.com/")
            search_by_image_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[jsname="R5mgy"]'))
            )
            search_by_image_btn.click()
            logging.info("✅ Opened Google Images Search by Image")
            
            # Switch to URL tab and search
            try:
                url_tab = wait.until(EC.element_to_be_clickable((By.XPATH, '//a[contains(text(), "Paste image link") or contains(text(), "URL")]'))) 
                url_tab.click()
            except:
                pass  # Already on URL tab
            
            url_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]')))
            url_input.clear()
            url_input.send_keys(image_url)
            url_input.submit()
            logging.info(f"✅ Direct URL search: {image_url}")
            
            # Wait for results
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-ri]')))
            time.sleep(2)
            
            # Scroll for more results
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Extract results
            js_script = f"""
            (() => {{
                const results = [];
                const cards = document.querySelectorAll("div.kb0PBd.cvP2Ce");
                
                for (let i = 0; i < cards.length && results.length < {max_results}; i++) {{
                    const card = cards[i];
                    
                    const imgEl = card.querySelector("div.gdOPf.q07dbf.uhHOwf.ez24Df img") || card.querySelector("img");
                    let imgSrc = imgEl?.src || null;
                    
                    const description = card.querySelector("span.Yt787.JGD2rd")?.innerText?.trim() || null;
                    let pageLink = card.querySelector("a[jsname='sTFXNd']")?.href || card.querySelector("a")?.href || null;
                    if (pageLink && pageLink.length > 120) {{
                        pageLink = pageLink.slice(0, 120) + "...";
                    }}
                    const sourceSite = card.querySelector("div.R8BTeb.q8U8x.LJEGod.du278d.i0Rdmd")?.innerText?.trim() || null;
                    
                    if (imgSrc && description && pageLink && sourceSite) {{
                        results.push({{
                            description: description,
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
            
            # Retry if empty
            if not raw_results:
                time.sleep(3)
                raw_results = driver.execute_script(js_script)
            
            # Process thumbnails
            processed_results = []
            for raw in raw_results:
                thumb_url = save_thumbnail(raw['thumbnail'])
                if thumb_url:
                    processed = raw.copy()
                    processed['thumbnail'] = thumb_url
                    processed_results.append(processed)
            
            logging.info(f"✅ Direct URL search complete: {len(processed_results)} results")
            return {
                "status": "success",
                "type": "url",
                "search_url": image_url,
                "count": len(processed_results),
                "requested": max_results,
                "results": processed_results
            }
            
    except Exception as e:
        logging.error(f"❌ Direct URL search failed: {e}")
        return {"error": str(e)}

# PATH 2: File upload → Temp URL → Search
def search_by_file_upload(file, max_results=20):
    """File upload → create temp URL → search"""
    # Step 1: Handle file upload
    dummy_url, upload_result = handle_file_upload(file)
    if not dummy_url:
        return upload_result
    
    upload_id = upload_result["upload_id"]
    
    try:
        # Step 2: Search using the temp URL
        search_result = search_by_url_direct(dummy_url, max_results)
        
        # Step 3: Add upload info to success response
        if search_result.get("status") == "success":
            search_result["upload_info"] = {
                "upload_id": upload_id,
                "temp_url": dummy_url,
                "original_filename": upload_result.get("filename"),
                "expires_in": "1 hour"
            }
        else:
            # Cleanup failed search
            cleanup_temp_uploads()  # Will remove this upload_id
            
        return search_result
        
    except Exception as e:
        # Cleanup on error
        if upload_id in temp_uploads:
            try:
                if os.path.exists(temp_uploads[upload_id]["path"]):
                    os.unlink(temp_uploads[upload_id]["path"])
                del temp_uploads[upload_id]
            except:
                pass
        return {"error": f"Search failed after upload: {str(e)}"}
@app.route('/')
def house():
    return render_template('index.html')
# Flask Routes - CLEAR PATHS!
@app.route('/search', methods=['GET', 'POST'])
def api_search():
    """Unified search: type=url → direct URL, type=file → upload + temp URL"""
    
    # PATH 2: File upload (POST multipart only)
    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        max_results = request.form.get('max_results', 20, type=int)
        return jsonify(search_by_file_upload(file, max_results))
    
    # PATH 1: URL search (GET or POST JSON)
    if request.method == 'POST':
        data = request.get_json() or {}
        search_type = data.get('type', 'url')
        image_url = data.get('value') or data.get('url')
        max_results = data.get('max_results', 20)
    else:  # GET
        search_type = request.args.get('type', 'url')
        image_url = request.args.get('value') or request.args.get('url')
        max_results = request.args.get('max_results', 20, type=int)
    
    # Handle different types clearly
    if search_type == 'url' and image_url:
        if not image_url.startswith(('http://', 'https://')):
            return jsonify({"error": "URL must start with http:// or https://"}), 400
        result = search_by_url_direct(image_url, max_results)
        return jsonify(result) if "error" not in result else jsonify(result), 500
    
    elif search_type == 'file':
        return jsonify({
            "error": "File uploads require POST multipart form-data with 'file' field, "
                    "not JSON or GET parameters. Use: curl -F 'file=@image.jpg' /search"
        }), 400
    
    else:
        return jsonify({
            "error": "Missing parameters. For URLs: ?url=IMAGE_URL or ?value=IMAGE_URL, "
                    "or POST JSON {'type':'url', 'value':'IMAGE_URL'}. "
                    "For files: POST multipart with 'file' field."
        }), 400

# Serve routes
@app.route('/temp/<upload_id>')
def serve_temp_upload(upload_id):
    """Serve temporary uploaded files (for file→URL conversion)"""
    if upload_id not in temp_uploads:
        return jsonify({"error": "Upload not found"}), 404
    
    info = temp_uploads[upload_id]
    if datetime.now() > info["expires"]:
        try:
            if os.path.exists(info["path"]):
                os.unlink(info["path"])
            del temp_uploads[upload_id]
        except:
            pass
        return jsonify({"error": "Upload expired"}), 404
    
    filename = os.path.basename(info["path"])
    return send_from_directory(os.path.dirname(info["path"]), filename)

@app.route('/serve/<path:filename>')
def serve_image(filename):
    """Serve saved thumbnails (permanent)"""
    if not (filename.endswith('.jpg') or filename.endswith('.png')):
        return "Invalid file", 403
    return send_from_directory(UPLOAD_FOLDER, filename)

# Utility routes
@app.route('/health', methods=['GET'])
def health():
    cleanup_temp_uploads()
    return jsonify({
        "status": "healthy",
        "base_url": BASE_URL,
        "temp_uploads_active": len(temp_uploads),
        "paths": {
            "url": "Direct URL search (GET/POST JSON)",
            "file": "File upload → temp URL → search (POST multipart)"
        }
    })

if __name__ == '__main__':
    cleanup_temp_uploads()
    app.run(host='0.0.0.0', port=10000, debug=True, threaded=True)
