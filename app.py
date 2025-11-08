"""
Swedish Lead Generation System - Login-based Lead Management
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import sqlite3
import threading
import time
from datetime import datetime
import secrets
import re
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Configuration
DATABASE = 'leads.db'
UPDATE_INTERVAL = 1800  # Update every 30 minutes
PAYPAL_EMAIL = os.environ.get('PAYPAL_EMAIL', 'reveriopaypal@gmail.com')
LEAD_PRICE = 0.10  # €0.10 per lead
MIN_PURCHASE = 10.00  # Minimum €10 purchase

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE,
                  password TEXT,
                  credits INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0.0,
                  created_at TIMESTAMP)''')
    
    # Leads table
    c.execute('''CREATE TABLE IF NOT EXISTS leads
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  company_name TEXT,
                  industry TEXT,
                  location TEXT,
                  website TEXT,
                  email TEXT,
                  phone TEXT,
                  description TEXT,
                  source TEXT,
                  status TEXT DEFAULT 'Ny',
                  user_id INTEGER,
                  created_at TIMESTAMP,
                  last_updated TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  payment_id TEXT UNIQUE,
                  user_id INTEGER,
                  amount REAL,
                  leads INTEGER,
                  status TEXT,
                  created_at TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

def scrape_business_leads():
    """Scrape Swedish business leads from public sources"""
    leads = []
    
    # Source 1: Swedish Reddit communities
    subreddits = ['sweden', 'tillsverige', 'swedish', 'stockholm', 'gothenburg', 'malmo']
    for subreddit in subreddits:
        try:
            url = f'https://www.reddit.com/r/{subreddit}/hot.json?limit=30'
            headers = {'User-Agent': 'SwedishLeadGen/1.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get('data', {}).get('children', []):
                    post_data = post.get('data', {})
                    title = post_data.get('title', '')
                    selftext = post_data.get('selftext', '')
                    full_text = (title + ' ' + selftext).lower()
                    
                    if is_swedish_lead(full_text):
                        email = extract_email(title + ' ' + selftext)
                        website = extract_website(title + ' ' + selftext)
                        
                        if title and len(title) > 10:
                            location = extract_swedish_location(title + ' ' + selftext)
                            lead = {
                                'company_name': extract_company_name(title),
                                'industry': categorize_industry(title + ' ' + selftext),
                                'location': location,
                                'website': website,
                                'email': email,
                                'phone': extract_phone(title + ' ' + selftext),
                                'description': selftext[:300] if selftext else title,
                                'source': f'Reddit r/{subreddit}',
                                'created_at': datetime.fromtimestamp(post_data.get('created_utc', 0))
                            }
                            leads.append(lead)
        except Exception as e:
            print(f"Error scraping r/{subreddit}: {e}")
    
    return leads

def is_swedish_lead(text):
    """Check if lead is Swedish-related"""
    text_lower = text.lower()
    swedish_locations = ['stockholm', 'gothenburg', 'göteborg', 'malmo', 'malmö', 'uppsala', 
                        'linköping', 'örebro', 'västerås', 'helsingborg', 'norrköping',
                        'lund', 'umeå', 'gävle', 'borås', 'eskilstuna', 'södertälje',
                        'karlstad', 'täby', 'växjö', 'halmstad', 'sundsvall', 'luleå',
                        'trollhättan', 'östersund', 'borlänge', 'falun', 'uddevalla',
                        'sweden', 'sverige', 'svensk', 'swedish', 'se', '.se']
    
    if any(loc in text_lower for loc in swedish_locations):
        return True
    if '.se' in text_lower:
        return True
    if '+46' in text or '0046' in text:
        return True
    return False

def extract_email(text):
    """Extract email from text"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else None

def extract_website(text):
    """Extract website URL from text"""
    pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?'
    matches = re.findall(pattern, text)
    return matches[0] if matches else None

def extract_phone(text):
    """Extract phone number from text"""
    pattern = r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}'
    matches = re.findall(pattern, text)
    return matches[0] if matches and len(matches[0]) > 7 else None

def extract_company_name(text):
    """Extract company name from text"""
    words = text.split()
    for i, word in enumerate(words):
        if word and word[0].isupper() and len(word) > 3:
            if i < len(words) - 1 and words[i+1] and words[i+1][0].isupper():
                return f"{word} {words[i+1]}"
            return word
    return "Okänt Företag"

def extract_swedish_location(text):
    """Extract Swedish location from text"""
    text_lower = text.lower()
    swedish_cities = [
        'stockholm', 'gothenburg', 'göteborg', 'malmo', 'malmö', 'uppsala',
        'linköping', 'örebro', 'västerås', 'helsingborg', 'norrköping',
        'lund', 'umeå', 'gävle', 'borås', 'eskilstuna', 'södertälje',
        'karlstad', 'täby', 'växjö', 'halmstad', 'sundsvall', 'luleå',
        'trollhättan', 'östersund', 'borlänge', 'falun', 'uddevalla',
        'visby', 'kalmar', 'skövde', 'kristianstad', 'huddinge',
        'botkyrka', 'tyresö', 'sollentuna', 'haninge', 'nacka'
    ]
    
    city_map = {
        'göteborg': 'Göteborg', 'malmö': 'Malmö', 'linköping': 'Linköping',
        'örebro': 'Örebro', 'västerås': 'Västerås', 'helsingborg': 'Helsingborg',
        'norrköping': 'Norrköping', 'umeå': 'Umeå', 'gävle': 'Gävle',
        'borås': 'Borås', 'eskilstuna': 'Eskilstuna', 'södertälje': 'Södertälje',
        'karlstad': 'Karlstad', 'täby': 'Täby', 'växjö': 'Växjö',
        'halmstad': 'Halmstad', 'sundsvall': 'Sundsvall', 'luleå': 'Luleå',
        'trollhättan': 'Trollhättan', 'östersund': 'Östersund',
        'borlänge': 'Borlänge', 'falun': 'Falun', 'uddevalla': 'Uddevalla',
        'visby': 'Visby', 'kalmar': 'Kalmar', 'skövde': 'Skövde',
        'kristianstad': 'Kristianstad', 'huddinge': 'Huddinge',
        'botkyrka': 'Botkyrka', 'tyresö': 'Tyresö', 'sollentuna': 'Sollentuna',
        'haninge': 'Haninge', 'nacka': 'Nacka'
    }
    
    for city in swedish_cities:
        if city in text_lower:
            return city_map.get(city, city.capitalize())
    
    if 'sweden' in text_lower or 'sverige' in text_lower:
        return 'Sweden'
    
    return 'Stockholm'

def categorize_industry(text):
    """Categorize industry from text"""
    text_lower = text.lower()
    if any(word in text_lower for word in ['tech', 'software', 'app', 'saas', 'developer']):
        return 'Technology'
    elif any(word in text_lower for word in ['ecommerce', 'retail', 'shop', 'store']):
        return 'E-commerce'
    elif any(word in text_lower for word in ['marketing', 'advertising', 'seo']):
        return 'Marketing'
    elif any(word in text_lower for word in ['finance', 'fintech', 'crypto', 'bitcoin']):
        return 'Finance'
    elif any(word in text_lower for word in ['health', 'medical', 'fitness']):
        return 'Healthcare'
    else:
        return 'General Business'

def save_leads(leads):
    """Save leads to database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    for lead in leads:
        c.execute("SELECT id FROM leads WHERE company_name = ? AND source = ?", 
                 (lead['company_name'], lead['source']))
        if c.fetchone():
            continue
        
        c.execute('''INSERT INTO leads 
                    (company_name, industry, location, website, email, phone, 
                     description, source, status, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Ny', ?, ?)''',
                 (lead['company_name'], lead['industry'], lead['location'],
                  lead.get('website'), lead.get('email'), lead.get('phone'),
                  lead['description'], lead['source'], lead['created_at'], datetime.now()))
    
    conn.commit()
    conn.close()

def update_leads():
    """Update leads from various sources"""
    print(f"[{datetime.now()}] Updating leads...")
    leads = scrape_business_leads()
    if leads:
        save_leads(leads)
        print(f"[{datetime.now()}] Saved {len(leads)} new leads")
    return len(leads)

def background_updater():
    """Background thread to update leads periodically"""
    while True:
        try:
            update_leads()
        except Exception as e:
            print(f"Error in background updater: {e}")
        time.sleep(UPDATE_INTERVAL)

# Routes
@app.route('/')
def index():
    """Login page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register new user"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        if c.fetchone():
            conn.close()
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create user
        password_hash = generate_password_hash(password)
        c.execute('''INSERT INTO users (email, password, credits, created_at)
                    VALUES (?, ?, 0, ?)''',
                 (email, password_hash, datetime.now()))
        
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        session['email'] = email
        
        return jsonify({'status': 'success', 'redirect': '/dashboard'})
    
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    """Login user"""
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    
    if not user or not check_password_hash(user[1], password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    session['user_id'] = user[0]
    session['email'] = email
    
    return jsonify({'status': 'success', 'redirect': '/dashboard'})

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Main dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('leads.html')

@app.route('/api/lead-stats', methods=['GET'])
def lead_stats():
    """Get lead statistics"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Total leads
    c.execute("SELECT COUNT(*) FROM leads WHERE user_id = ?", (user_id,))
    total_leads = c.fetchone()[0]
    
    # Leads today
    c.execute("SELECT COUNT(*) FROM leads WHERE user_id = ? AND DATE(created_at) = DATE('now')", (user_id,))
    leads_today = c.fetchone()[0]
    
    # Leads by status
    c.execute("SELECT status, COUNT(*) FROM leads WHERE user_id = ? GROUP BY status", (user_id,))
    status_counts = dict(c.fetchall())
    
    # Recent leads
    c.execute("SELECT company_name, location, status FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_id,))
    recent_leads = [{'company_name': row[0], 'location': row[1], 'status': row[2]} for row in c.fetchall()]
    
    # User credits
    c.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
    credits = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_leads': total_leads,
        'leads_today': leads_today,
        'status_counts': status_counts,
        'recent_leads': recent_leads,
        'credits': credits
    })

@app.route('/api/my-leads', methods=['GET'])
def my_leads():
    """Get user's leads"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    status = request.args.get('status', '')
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    query = "SELECT * FROM leads WHERE user_id = ?"
    params = [user_id]
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT 100"
    
    c.execute(query, params)
    leads = c.fetchall()
    conn.close()
    
    leads_list = []
    for lead in leads:
        leads_list.append({
            'id': lead[0],
            'company_name': lead[1],
            'industry': lead[2],
            'location': lead[3],
            'website': lead[4],
            'email': lead[5],
            'phone': lead[6],
            'description': lead[7],
            'source': lead[8],
            'status': lead[9],
            'created_at': lead[11]
        })
    
    return jsonify({'leads': leads_list, 'count': len(leads_list)})

@app.route('/api/generate-leads', methods=['POST'])
def generate_leads():
    """Generate new leads for user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    count = int(request.json.get('count', 10))
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Check credits
    c.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()
    if not result or result[0] < count:
        conn.close()
        return jsonify({'error': 'Insufficient credits'}), 402
    
    credits = result[0]
    
    # Get available leads
    swedish_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 'Örebro', 
                     'Västerås', 'Helsingborg', 'Norrköping', 'Lund', 'Umeå', 'Gävle', 
                     'Borås', 'Eskilstuna', 'Södertälje', 'Karlstad', 'Täby', 'Växjö', 
                     'Halmstad', 'Sundsvall', 'Luleå', 'Trollhättan', 'Östersund', 
                     'Borlänge', 'Falun', 'Uddevalla', 'Visby', 'Kalmar', 'Skövde', 
                     'Kristianstad', 'Huddinge', 'Botkyrka', 'Tyresö', 'Sollentuna', 
                     'Haninge', 'Nacka', 'Sweden']
    
    query = "SELECT * FROM leads WHERE location IN (" + ",".join(["?"] * len(swedish_cities)) + ") AND (user_id IS NULL OR user_id = 0) ORDER BY created_at DESC LIMIT ?"
    params = swedish_cities + [count]
    
    c.execute(query, params)
    leads = c.fetchall()
    
    # Assign leads to user
    lead_ids = []
    for lead in leads:
        c.execute("UPDATE leads SET user_id = ?, status = 'Ny', last_updated = ? WHERE id = ?",
                 (user_id, datetime.now(), lead[0]))
        lead_ids.append(lead[0])
    
    # Deduct credits
    c.execute("UPDATE users SET credits = credits - ? WHERE id = ?", (count, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'leads_generated': len(lead_ids),
        'credits_remaining': credits - count,
        'lead_ids': lead_ids
    })

@app.route('/api/update-lead-status', methods=['POST'])
def update_lead_status():
    """Update lead status"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    lead_id = request.json.get('lead_id')
    new_status = request.json.get('status')
    
    if not lead_id or not new_status:
        return jsonify({'error': 'Missing parameters'}), 400
    
    valid_statuses = ['Ny', 'Kontaktad', 'Konverterad', 'Borttagen']
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute("UPDATE leads SET status = ?, last_updated = ? WHERE id = ? AND user_id = ?",
             (new_status, datetime.now(), lead_id, user_id))
    
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Lead not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Lead status updated'})

@app.route('/update')
def manual_update():
    """Manually trigger lead update"""
    count = update_leads()
    return jsonify({'status': 'success', 'leads_added': count})

if __name__ == '__main__':
    init_db()
    
    # Initial update
    print("Initializing Swedish Lead Generation System...")
    update_leads()
    
    # Start background updater
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
