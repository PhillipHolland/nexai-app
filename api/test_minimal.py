import os
from flask import Flask, render_template

# Simple test to see if Flask works
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

app = Flask(__name__, 
           static_folder=static_dir,
           template_folder=template_dir)

@app.route('/')
def test_homepage():
    try:
        return render_template('landing.html')
    except Exception as e:
        return f"""<!DOCTYPE html>
<html><head><title>Test</title></head>
<body>
<h1>Template Error: {e}</h1>
<p>Template folder: {app.template_folder}</p>
<p>Templates exist: {os.path.exists(app.template_folder)}</p>
<p>Landing.html exists: {os.path.exists(os.path.join(app.template_folder, 'landing.html'))}</p>
</body></html>"""

if __name__ == '__main__':
    app.run(debug=True)