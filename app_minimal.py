"""
Minimal version of app.py to test step by step
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import secrets
import re
import os

# Optional imports
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import pandas as pd
except ImportError:
    pd = None

# Create Flask app
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.urandom(24)

# Configuration - simplified
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leads.db')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEADS_FOLDER = os.path.join(BASE_DIR, 'Leads')
POSSIBLE_LEADS_PATHS = [
    os.path.join(BASE_DIR, 'Leads'),
    '/home/Leadius/mysite/Leads',
    '/home/Leadius/Leads'
]

UPDATE_INTERVAL = 1800
PAYPAL_EMAIL = os.environ.get('PAYPAL_EMAIL', 'reveriopaypal@gmail.com')
LEAD_PRICE = 0.10
MIN_PURCHASE = 10.00
LOCK_DURATION_DAYS = 180

# Simple test route
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'Minimal app is working'})

@app.route('/test')
def test():
    return jsonify({
        'status': 'ok',
        'message': 'Test route works',
        'pandas': pd is not None,
        'beautifulsoup': BeautifulSoup is not None
    })

if __name__ == '__main__':
    app.run(debug=True)

