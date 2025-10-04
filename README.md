# Image-Turbo 🦅

**Image-Turbo** is a fast Flask app that scrapes Google Images results for a URL query, converts base64 images to files, and serves them via custom URLs. With a sleek Bootstrap test UI, it’s built for speed and style. Ready to soar? 🚀

## Features
- Scrape up to 15 Google Images results (default: 5).
- Serve base64 images via `http://<your-domain>/images/<filename>`.
- Rotate user agents to avoid detection.
- Responsive HTML test UI at `/`.

## Prerequisites
- Python 3.8+
- Chromium & ChromeDriver

## Setup
1. Clone the repo:  
   ```bash
   git clone https://github.com/cortexinvader/image-turbo.git
   ```
2. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```
3. Place `index.html` in the project root for the test UI.
4. Start the app:  
   ```bash
   python app.py
   ```
5. Access the UI at:  
   ```
   http://localhost:10000/
   ```
   Or API at:  
   ```
   /search?query=<url>&num=5
   ```

## API
- **Endpoint**: `/search` (GET)  
- **Params**:  
  - `query` (string, required) — search URL  
  - `num` (integer, 1–15, default: 5) — number of results  
- **Response**: JSON containing:  
  - `imageSrc` — served URL of image  
  - `imageSource` — original image URL  
  - `pageLink` — page link where image is found  
  - `description` — image description

## Notes
- Google Images selectors may break if DOM changes — test regularly.
- Temporary files stored in `/tmp/images/`. Add cleanup for production.

## License
MIT. Fly high with Image-Turbo! 🦅
