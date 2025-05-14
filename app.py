from flask import Flask, request, render_template, jsonify, Response
import time

app = Flask(__name__)

# Simulated client data
clients = ["jane_smith", "john_doe"]

@app.route('/')
def index():
    # Serve the main UI directly, no login required
    return render_template('index.html', clients=clients)

@app.route('/api/client/<client_id>', methods=['GET'])
def get_client(client_id):
    # Avoid strict JSON parsing for GET requests (no body expected)
    data = {
        'info': {'name': client_id, 'case_number': '123', 'email': '', 'phone': '', 'case_type': '', 'notes': ''},
        'history': [],
        'documents': []
    }
    return jsonify(data), 200

@app.route('/api/new_conversation/<client_id>', methods=['POST'])
def new_conversation(client_id):
    # Handle JSON requests gracefully
    if request.is_json:
        # Process JSON data if present
        data = request.get_json()
    else:
        # Fallback for non-JSON requests
        data = {}
    # Simulate clearing conversation
    return jsonify({'success': True}), 200

@app.route('/api/upload', methods=['POST'])
def upload_file():
    # Handle multipart/form-data for file uploads
    file = request.files.get('file')
    client_id = request.form.get('client_id', 'default_client')  # Default to "default_client" if not provided
    if not file:
        return jsonify({'error': 'Missing file'}), 400
    # Simulate file processing
    return jsonify({'text': 'Sample file content'}), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    # Handle JSON requests gracefully
    if request.is_json:
        data = request.get_json()
        messages = data.get('messages', [])
        client_id = data.get('client_id', 'default_client')  # Default to "default_client" if not provided
    else:
        # Fallback for non-JSON requests
        return jsonify({'error': 'Expected application/json'}), 415

    # Simulate a streaming response
    def generate():
        # Start the stream
        response_chunks = ["Sample ", "response ", "from ", "the ", "server."]
        for chunk in response_chunks:
            # Use a properly formatted f-string for the JSON response
            yield f'data: {{"choices": [{{"delta": {{"content": "{chunk}"}}}}]}}\n\n'
            time.sleep(0.5)  # Simulate delay between chunks
        # End the stream
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/client/<client_id>', methods=['POST'])
def save_client(client_id):
    # Handle JSON requests gracefully
    if request.is_json:
        data = request.get_json()
    else:
        return jsonify({'error': 'Expected application/json'}), 415
    # Simulate saving client info
    return jsonify({'success': True}), 200

if __name__ == '__main__':
    app.run(debug=True)
