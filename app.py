from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__)

def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    return chrome_options

@app.route('/search')
def search():
    query = request.args.get('q', '')

    if not query:
        return jsonify({"error": "Please provide a search query using '?q=your_query'"}), 400

    try:
        chrome_options = get_chrome_options()
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            driver.get(f"https://www.google.com/search?q={query}")
            time.sleep(5)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            results = soup.find_all(class_="WaaZC")
            extracted_texts = [result.get_text() for result in results]

        finally:
            driver.quit()

        return jsonify({
            "query": query,
            "results": extracted_texts,
            "status": "success"
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port)
