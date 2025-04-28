from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

@app.route('/search')
def search():
    query = request.args.get('q', '')

    if not query:
        return jsonify({"error": "Please provide a search query using '?q=your_query'"}), 400

    # Set up headless Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Open Google
        driver.get("https://www.google.com/search")

        # Find the search box and enter the query
        search_box = driver.find_element(By.ID, "APjFqb")
        search_box.send_keys(query)

        # Find and click the search button
        search_button = driver.find_element(By.CLASS_NAME, "btnK")
        search_button.click()

        # Wait for the results to load
        time.sleep(5)

        # Now get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Find all elements with class "WaaZC"
        results = soup.find_all(class_="WaaZC")
        extracted_texts = [result.get_text() for result in results]

    finally:
        driver.quit()

    return jsonify({"query": query, "results": extracted_texts})

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=3000)
