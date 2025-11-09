"""
Minimal test app to check if Flask works
"""
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'Flask is working'})

@app.route('/test')
def test():
    return jsonify({'status': 'ok', 'message': 'Test route works'})

if __name__ == '__main__':
    app.run(debug=True)

