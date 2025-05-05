from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import logging
import os

# Logging Setup
LOG_LEVEL = logging.DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format='[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FlaskSeleniumApp")

app = Flask(__name__)

@app.route('/')
def home():
    logger.info("Received request at '/' route")

    try:
        logger.debug("Setting up Chrome options for headless operation")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")

        logger.debug("Downloading and using ChromeDriver with webdriver-manager")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        url = "https://www.google.com"
        logger.info(f"Navigating to {url}")
        driver.get(url)

        title = driver.title
        logger.info(f"Page title fetched: {title}")

        driver.quit()
        logger.debug("WebDriver closed successfully")

        return jsonify({"title": title})
    except Exception as e:
        logger.exception("An error occurred while processing the request")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
