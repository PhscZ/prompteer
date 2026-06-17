from flask import Flask, render_template, request, jsonify, Response
import requests
import json
import os

app = Flask(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'nanogpt_history.json')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/models', methods=['GET'])
def get_models():
    api_key = request.args.get('api_key')
    if not api_key: return jsonify({"error": "API Key required"}), 400
    url = "https://nano-gpt.com/api/v1/models?detailed=true"
    headers = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    if not data: return jsonify({"error": "Empty request"}), 400

    api_key = data.get('api_key')
    model = data.get('model')
    suffix = data.get('suffix', '')
    prompt_text = data.get('prompt', '')
    files = data.get('files', [])

    if not api_key or not model: return jsonify({"error": "API Key and Model required"}), 400

    full_model = model + suffix
    content = []

    for f in files:
        f_type = f.get('type', '')
        f_name = f.get('name', 'file')
        f_data = f.get('data', '')
        if f_type.startswith('image/'):
            content.append({"type": "image_url", "image_url": {"url": f_data}})
        else:
            content.append({"type": "text", "text": f"[File: {f_name}]\n{f_data}"})

    if prompt_text.strip():
        content.append({"type": "text", "text": prompt_text})

    if not content: return jsonify({"error": "Prompt or files are required"}), 400

    messages = [{"role": "user", "content": content}]
    
    payload = {
        "model": full_model, 
        "messages": messages, 
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}

    def generate():
        try:
            with requests.post("https://nano-gpt.com/api/v1/chat/completions", headers=headers, json=payload, stream=True, timeout=(10, 600)) as resp:
                if resp.status_code != 200:
                    error_msg = resp.text
                    try: error_msg = resp.json().get('error', {}).get('message', error_msg) 
                    except: pass
                    yield f"data: {json.dumps({'error': str(error_msg)})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                for chunk in resp.iter_content(chunk_size=None, decode_unicode=False):
                    if chunk:
                        yield chunk

                yield "\n\ndata: [DONE]\n\n"

        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'error': 'The request timed out after 10 minutes.'})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return jsonify(json.load(f))
        except Exception: return jsonify([])
    return jsonify([])

@app.route('/api/history', methods=['POST'])
def save_history():
    try:
        data = request.json
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting NanoGPT Prompteer on http://localhost:5000")
    app.run(port=5000, debug=True, threaded=True)