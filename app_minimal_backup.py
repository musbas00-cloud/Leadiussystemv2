from flask import Flask
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/')
def index():
    return "Hello from the ABSOLUTE MINIMAL Leadius app!"

@app.route('/test')
def test():
    return "Test route working on absolute minimal app."
