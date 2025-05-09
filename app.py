from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

def check_google_title():
    options = Options()
    options.binary_location = "/usr/bin/chromium"  # Explicit Chromium binary path
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)

    driver.get("https://www.google.com")
    title = driver.title
    driver.quit()
    return title

@app.route('/')
def index():
    title = check_google_title()
    return jsonify({"google_title": title})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
