from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

@app.route('/')
def index():
    url = request.args.get('url', 'https://www.google.com')  # Get URL from query param
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.binary_location = "/usr/bin/chromium"  # Path to Chromium binary

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(url)
        title = driver.title
    finally:
        driver.quit()

    return jsonify({"title": title})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000)
