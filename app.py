from flask import Flask, render_template, request, jsonify
from automation.web_automator import WebAutomator
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_automation', methods=['POST'])
def run_automation():
    url = request.json.get('url')
    action = request.json.get('action')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        automator = WebAutomator()
        result = automator.run(url, action)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
