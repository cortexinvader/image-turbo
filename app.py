from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import subprocess
import os
import traceback

app = Flask(__name__)

def get_binary_version(binary_path):
    try:
        result = subprocess.run([binary_path, "--version"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Could not determine version: {e}"

def check_google_title():
    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    chromedriver_bin = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")

    options = Options()
    options.binary_location = chrome_bin
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--single-process")

    service = Service(chromedriver_bin)

    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get("https://www.google.com")
        title = driver.title
        return title
    finally:
        if driver:
            driver.quit()

@app.route('/')
def index():
    try:
        title = check_google_title()
        return jsonify({"google_title": title})
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == '__main__':
    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    chromedriver_bin = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")
    print("Chromium version:", get_binary_version(chrome_bin))
    print("Chromedriver version:", get_binary_version(chromedriver_bin))
    app.run(host='0.0.0.0', port=10000)
