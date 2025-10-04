from flask import Flask, jsonify, request, send_from_directory
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import os
import base64
import uuid
import tempfile
from dotenv import load_dotenv
import random

app = Flask(__name__)

# Load environment variables
load_dotenv()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "localhost:10000")

# Initialize temporary directory for images
TEMP_IMAGE_DIR = os.path.join(tempfile.gettempdir(), "images")
os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

# User agent list for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
]

# Get binary version
def get_binary_version(binary_path):
    try:
        result = subprocess.run([binary_path, "--version"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Could not determine version: {e}"

# Save base64 image to file and return filename
def save_base64_image(base64_string):
    try:
        image_data = base64_string.split(",")[1]
        image_bytes = base64.b64decode(image_data)
        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(TEMP_IMAGE_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filename
    except Exception as e:
        return None

# Initialize Selenium WebDriver
chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
chromedriver_bin = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")
options = Options()
options.binary_location = chrome_bin
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--remote-debugging-port=9222")
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
service = Service(chromedriver_bin)
driver = webdriver.Chrome(service=service, options=options)

# JavaScript snippets
JS_SNIPPET_1 = """
(() => {
  const results = [];
  const links = document.querySelectorAll("a.LBcIee");
  for (const [idx, link] of [...links].entries()) {
    if (results.length >= %s) break;
    const img = link.querySelector("img");
    const imageSourceDiv = link.querySelector(".R8BTeb.q8U8x.LJEGod.du278d.i0Rdmd");
    const descriptionSpan = link.querySelector("span.Yt787.JGD2rd");
    if (!img?.src || !imageSourceDiv?.innerText || !descriptionSpan?.innerText || !link.href) continue;
    results.push({
      index: idx,
      imageSrc: img.src,
      imageSource: imageSourceDiv.innerText.trim(),
      pageLink: link.href,
      description: descriptionSpan.innerText.trim()
    });
  }
  return results;
})();
"""

JS_SNIPPET_2 = """
const el = document.querySelector("body > div.L3eUgb > div.o3j99.ikrT4e.om7nvf > form > div:nth-child(1) > div.A8SBwf > div.RNNXgb > div.SDkEP > div.fM33ce.dRYYxd > div.WC2Die > div.nDcEnd");
if (el) {
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.focus();
  el.click();
} else {
  console.log("Element not found on page.");
}
"""

JS_SNIPPET_4 = """
const input = document.querySelector("body > div.L3eUgb > div.o3j99.ikrT4e.om7nvf > form > div:nth-child(1) > div.A8SBwf > div.RNNXgb > div.M8H8pb > c-wiz > div.NzSfif > div > div.NrdQVe > div.f6GA0 > div.e8Eule > div.PXT6cd > input");
const button = document.querySelector("body > div.L3eUgb > div.o3j99.ikrT4e.om7nvf > form > div:nth-child(1) > div.A8SBwf > div.RNNXgb > div.M8H8pb > c-wiz > div.NzSfif > div > div.NrdQVe > div.f6GA0 > div.e8Eule > div.PXT6cd > div");
if (input && button) {
  input.value = "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.value = "%s";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  button.click();
} else {
  console.log("Input or button not found.");
}
"""

# Navigate to Google Images on startup
driver.get("https://images.google.com")
driver.execute_script(JS_SNIPPET_2)

@app.route("/search", methods=["GET"])
def search_images():
    """Handle GET request to search Google Images and return scraped results with served image URLs."""
    query = request.args.get("query")
    num = min(int(request.args.get("num", 5)), 15)

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    try:
        driver.execute_script(JS_SNIPPET_4 % query)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.LBcIee"))
        )
        results = driver.execute_script(JS_SNIPPET_1 % num)
        for result in results:
            if result["imageSrc"].startswith("data:image"):
                filename = save_base64_image(result["imageSrc"])
                if filename:
                    result["imageSrc"] = f"http://{RENDER_EXTERNAL_URL}/images/{filename}"
                else:
                    result["imageSrc"] = ""
        driver.execute_script(JS_SNIPPET_2)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/images/<filename>")
def serve_image(filename):
    """Serve an image file from the temporary directory."""
    try:
        return send_from_directory(TEMP_IMAGE_DIR, filename)
    except Exception as e:
        return jsonify({"error": "Image not found"}), 404

@app.route("/")
def index():
    """Serve the testing HTML page."""
    return send_from_directory(".", "index.html")

if __name__ == "__main__":
    print("Chromium version:", get_binary_version(chrome_bin))
    print("Chromedriver version:", get_binary_version(chromedriver_bin))
    app.run(host="0.0.0.0", port=10000)
