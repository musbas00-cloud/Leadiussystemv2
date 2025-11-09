
"""
Swedish Lead Generation System - Login-based Lead Management
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

# Optional imports - wrapped in try-except to prevent crashes if not installed
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import pandas as pd
except ImportError:
    pd = None

# Create Flask app - this should be the very first executable part of the app logic
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.urandom(24)

# Configuration (using dynamic path initialization)
# Use simple placeholders; actual paths initialized later to avoid import-time crashes
DATABASE = 'leads.db'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LEADS_FOLDER = os.path.join(BASE_DIR, 'Leads')
POSSIBLE_LEADS_PATHS = [
    os.path.join(BASE_DIR, 'Leads'),
    os.path.join(BASE_DIR, ' Leads'),
    # Removed PythonAnywhere specific absolute paths
]

UPDATE_INTERVAL = 1800  # Update every 30 minutes
PAYPAL_EMAIL = os.environ.get('PAYPAL_EMAIL', 'reveriopaypal@gmail.com')
LEAD_PRICE = 0.10  # €0.10 per lead
MIN_PURCHASE = 10.00  # Minimum €10 purchase
LOCK_DURATION_DAYS = 180  # Lock leads for 180 days

# Global flag to track if paths have been initialized
_PATHS_INITIALIZED = False

def _initialize_paths():
    """Initializes paths dynamically to avoid import-time crashes."""
    global DATABASE, BASE_DIR, LEADS_FOLDER, POSSIBLE_LEADS_PATHS, _PATHS_INITIALIZED
    if _PATHS_INITIALIZED: # Only run once
        return

    try:
        # Attempt to get the real base directory if possible
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    except Exception as e:
        BASE_DIR = os.getcwd() # Fallback

    # Re-construct paths based on the determined BASE_DIR
    DATABASE = os.path.join(BASE_DIR, 'leads.db')
    LEADS_FOLDER = os.path.join(BASE_DIR, 'Leads')
    POSSIBLE_LEADS_PATHS = [
        os.path.join(BASE_DIR, 'Leads'),
        os.path.join(BASE_DIR, ' Leads'),
    ]
    _PATHS_INITIALIZED = True

def init_db():
    """Initialize the database"""
    _initialize_paths() # Ensure paths are set
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
    except Exception as e:
        # If database connection fails, return early
        print(f"Error connecting to database at {DATABASE}: {e}")
        import traceback
        traceback.print_exc()
        return

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE,
                  password TEXT,
                  credits INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0.0,
                  role TEXT DEFAULT 'Customer',
                  created_at TIMESTAMP)''')

    # Add role column if it doesn't exist (for existing databases)
    try:
        c.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "Customer"')
        conn.commit()
        # Update existing users to have Customer role
        c.execute('UPDATE users SET role = "Customer" WHERE role IS NULL')
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists, just update NULL values
        try:
            c.execute('UPDATE users SET role = "Customer" WHERE role IS NULL')
            conn.commit()
        except Exception as update_e:
            # Silently fail, column might exist and not have NULLs
            pass
    except Exception as e:
        # Silently fail - role column might already exist
        pass

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
                  locked_until TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')

    # Add locked_until column if it doesn't exist (for existing databases)
    try:
        c.execute('ALTER TABLE leads ADD COLUMN locked_until TIMESTAMP')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    except Exception as e: # Catch other exceptions
        pass

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

def load_leads_from_excel():
    """Load leads from Excel files in the Leads folder"""
    _initialize_paths() # Ensure paths are initialized
    if pd is None:
        print("Error: pandas is not installed. Cannot load Excel files.")
        return []

    leads = []

    # Re-check for Leads folder
    current_leads_folder = LEADS_FOLDER
    for path in POSSIBLE_LEADS_PATHS:
        if os.path.exists(path):
            current_leads_folder = path
            break

    if not os.path.exists(current_leads_folder):
        print(f"ERROR: Leads folder not found at {current_leads_folder} or other possible paths.")
        return leads

    # Get all Excel files in the Leads folder
    try:
        excel_files = [f for f in os.listdir(current_leads_folder) if f.endswith(('.xlsx', '.xls'))]
    except Exception as e:
        print(f"ERROR: Cannot list files in {current_leads_folder}: {e}")
        return leads

    if not excel_files:
        print(f"ERROR: No Excel files found in {current_leads_folder}")
        try:
            all_files = os.listdir(current_leads_folder)
        except:
            pass
        return leads

    for excel_file in excel_files:
        try:
            file_path = os.path.join(current_leads_folder, excel_file)

            # Read Excel file
            try:
                df = pd.read_excel(file_path)
            except Exception as e:
                continue

            # Normalize column names (handle different naming)
            df.columns = df.columns.str.strip().str.lower()

            # Map common column names
            column_mapping = {
                'company': 'company_name',
                'company name': 'company_name',
                'företag': 'company_name',
                'företagsnamn': 'company_name',
                'name': 'company_name',
                'namn': 'company_name',

                'phone': 'phone',
                'telefon': 'phone',
                'phone number': 'phone',
                'telefonnummer': 'phone',
                'tel': 'phone',

                'email': 'email',
                'e-post': 'email',
                'e-mail': 'email',
                'mail': 'email',

                'website': 'website',
                'web': 'website',
                'url': 'website',
                'hemsida': 'website',

                'location': 'location',
                'city': 'location',
                'stad': 'location',
                'ort': 'location',
                'address': 'location',
                'adress': 'location',

                'industry': 'industry',
                'bransch': 'industry',
                'category': 'industry',
                'kategori': 'industry',

                'description': 'description',
                'beskrivning': 'description',
                'notes': 'description',
                'anteckningar': 'description'
            }

            # Rename columns
            for old_name, new_name in column_mapping.items():
                if old_name in df.columns:
                    df.rename(columns={old_name: new_name}, inplace=True)

            # Process each row
            rows_processed = 0
            rows_with_phone = 0
            rows_skipped = 0

            for index, row in df.iterrows():
                rows_processed += 1

                # Phone number is MANDATORY - try to find it in any column
                phone = None

                # First, try the mapped 'phone' column
                if 'phone' in df.columns:
                    phone_value = row.get('phone', '')
                    if pd.notna(phone_value):
                        phone = str(phone_value).strip()

                # If not found, search all columns for phone-like patterns
                if not phone or phone.lower() in ['nan', 'none', '']:
                    for col in df.columns:
                        value = row.get(col, '')
                        if pd.notna(value):
                            value_str = str(value).strip()
                            # Check if it looks like a phone number (at least 8 digits)
                            if re.search(r'\d{8,}', value_str):
                                phone = re.sub(r'[^0-9+]', '', value_str) # Keep only digits and '+'
                                if len(phone) >= 9:
                                    break
                                else:
                                    phone = None

                # Clean and validate phone number
                if phone and phone.lower() not in ['nan', 'none', '']:
                    # Clean phone number - keep + and digits
                    phone_clean = re.sub(r'[^0-9+]', '', phone)
                    if len(phone_clean) >= 9:  # Minimum valid phone
                        phone = phone_clean
                        rows_with_phone += 1
                    else:
                        phone = None
                        rows_skipped += 1
                else:
                    phone = None
                    rows_skipped += 1

                # Skip if no phone number (MANDATORY)
                if not phone or len(phone) < 9:
                    continue

                # Extract other fields - try to find company name in any column
                company_name = None

                # First try mapped 'company_name' column
                if 'company_name' in df.columns:
                    company_value = row.get('company_name', '')
                    if pd.notna(company_value):
                        company_name = str(company_value).strip()

                # If not found, try common column names
                if not company_name or company_name.lower() in ['nan', 'none', '']:
                    for col in df.columns:
                        if any(word in col.lower() for word in ['company', 'företag', 'name', 'namn', 'firma']):
                            value = row.get(col, '')
                            if pd.notna(value):
                                company_name = str(value).strip()
                                if company_name and company_name.lower() not in ['nan', 'none', '']:
                                    break

                # If still not found, use first non-empty text column
                if not company_name or company_name.lower() in ['nan', 'none', '']:
                    for col in df.columns:
                        if col not in ['phone', 'telefon']:  # Skip phone columns
                            value = row.get(col, '')
                            if pd.notna(value):
                                value_str = str(value).strip()
                                if value_str and len(value_str) > 2 and value_str.lower() not in ['nan', 'none', '']:
                                    company_name = value_str
                                    break

                # Skip if no company name (MANDATORY)
                if not company_name or company_name.lower() in ['nan', 'none', '']:
                    continue

                email = None
                if 'email' in df.columns:
                    email_value = row.get('email', '')
                    if pd.notna(email_value):
                        email = str(email_value).strip()
                        if email and email.lower() in ['nan', 'none', '']:
                            email = None

                website = None
                if 'website' in df.columns:
                    website_value = row.get('website', '')
                    if pd.notna(website_value):
                        website = str(website_value).strip()
                        if website and website.lower() in ['nan', 'none', '']:
                            website = None

                location = 'Sweden'
                if 'location' in df.columns:
                    location_value = row.get('location', '')
                    if pd.notna(location_value):
                        location = str(location_value).strip()
                        if not location or location.lower() in ['nan', 'none', '']:
                            location = 'Sweden'

                industry = 'General Business'
                if 'industry' in df.columns:
                    industry_value = row.get('industry', '')
                    if pd.notna(industry_value):
                        industry = str(industry_value).strip()
                        if not industry or industry.lower() in ['nan', 'none', '']:
                            industry = 'General Business'

                description = f"{company_name} - {location}"
                if 'description' in df.columns:
                    desc_value = row.get('description', '')
                    if pd.notna(desc_value):
                        desc = str(desc_value).strip()
                        if desc and desc.lower() not in ['nan', 'none', '']:
                            description = desc

                lead = {
                    'company_name': company_name,
                    'industry': industry,
                    'location': location,
                    'website': website,
                    'email': email,
                    'phone': phone,
                    'description': description[:300] if description else '',
                    'source': f'Excel: {excel_file}',
                    'created_at': datetime.now()
                }
                leads.append(lead)

        except Exception as e:
            continue

    return leads

def save_leads_from_excel():
    """Load leads from Excel and save to database (only new ones)"""
    _initialize_paths() # Ensure paths are initialized
    try:
        leads = load_leads_from_excel()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 0

    if not leads:
        return 0

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    saved_count = 0

    for lead in leads:
        try:
            # Check if lead already exists (by company name and phone)
            c.execute("SELECT id FROM leads WHERE company_name = ? AND phone = ?",
                     (lead['company_name'], lead['phone']))
            if c.fetchone():
                continue  # Lead already exists

            # Insert new lead
            c.execute('''INSERT INTO leads
                        (company_name, industry, location, website, email, phone,
                         description, source, status, created_at, last_updated, locked_until)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Ny', ?, ?, NULL)''',
                     (lead['company_name'], lead['industry'], lead['location'],
                      lead.get('website'), lead.get('email'), lead['phone'],
                      lead['description'], lead['source'], lead['created_at'], datetime.now()))
            saved_count += 1
        except Exception as e:
            continue

    try:
        conn.commit()
    except Exception as e:
        pass
    finally:
        conn.close()

    return saved_count


# Functions for scraping (commented out as per previous instructions to use Excel)
def scrape_allabolag():
    """Scrape Swedish companies from Allabolag.se (DISABLED)"""
    return []

def scrape_merinfo():
    """Scrape Swedish companies from Merinfo.se (DISABLED)"""
    return []


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
        'borlänge': 'Borlänge', 'falun': 'Falun', 'uddevalla',
        'visby': 'Visby', 'kalmar': 'Kalmar', 'skövde', 'kristianstad', 'huddinge',
        'botkyrka': 'Botkyrka', 'tyresö': 'Tyresö', 'sollentuna', 'haninge', 'nacka'
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
    _initialize_paths() # Ensure paths are initialized
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    saved_count = 0

    for lead in leads:
        c.execute("SELECT id FROM leads WHERE company_name = ? AND source = ?",
                 (lead['company_name'], lead['source']))
        if c.fetchone():
            continue

        try:
            c.execute('''INSERT INTO leads
                        (company_name, industry, location, website, email, phone,
                         description, source, status, created_at, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Ny', ?, ?)''',
                     (lead['company_name'], lead['industry'], lead['location'],
                      lead.get('website'), lead.get('email'), lead.get('phone'),
                      lead['description'], lead['source'], lead['created_at'], datetime.now()))
            saved_count += 1
        except Exception as e:
            continue

    conn.commit()
    conn.close()
    return saved_count

def update_leads():
    """Update leads from various sources - Allabolag and Merinfo only"""
    print(f"[{datetime.now()}] ===== STARTING LEAD UPDATE =====")
    print(f"[{datetime.now()}] Updating leads from Allabolag and Merinfo...")
    leads = []

    # Test if requests work at all
    print(f"[{datetime.now()}] Testing connection to Allabolag.se...")
    try:
        test_response = requests.get('https://www.allabolag.se', timeout=10)
        print(f"[{datetime.now()}] Allabolag.se response: {test_response.status_code}")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: Cannot connect to Allabolag.se: {e}")

    # Scrape from Allabolag.se
    try:
        print(f"[{datetime.now()}] Scraping Allabolag.se...")
        allabolag_leads = scrape_allabolag()
        if allabolag_leads:
            leads.extend(allabolag_leads)
            print(f"[{datetime.now()}] ✓ Scraped {len(allabolag_leads)} leads from Allabolag.se")
        else:
            print(f"[{datetime.now()}] ✗ No leads found on Allabolag.se")
    except Exception as e:
        print(f"[{datetime.now()}] ✗ ERROR scraping Allabolag.se: {e}")
        import traceback
        print(f"[{datetime.now()}] Traceback:")
        print(traceback.format_exc())

    # Test if requests work for Merinfo
    print(f"[{datetime.now()}] Testing connection to Merinfo.se...")
    try:
        test_response = requests.get('https://www.merinfo.se', timeout=10)
        print(f"[{datetime.now()}] Merinfo.se response: {test_response.status_code}")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: Cannot connect to Merinfo.se: {e}")

    # Scrape from Merinfo.se
    try:
        print(f"[{datetime.now()}] Scraping Merinfo.se...")
        merinfo_leads = scrape_merinfo()
        if merinfo_leads:
            leads.extend(merinfo_leads)
            print(f"[{datetime.now()}] ✓ Scraped {len(merinfo_leads)} leads from Merinfo.se")
        else:
            print(f"[{datetime.now()}] ✗ No leads found on Merinfo.se")
    except Exception as e:
        print(f"[{datetime.now()}] ✗ ERROR scraping Merinfo.se: {e}")
        import traceback
        print(f"[{datetime.now()}] Traceback:")
        print(traceback.format_exc())

    # Filter leads - ONLY keep those with phone numbers (MANDATORY)
    leads_with_phone = [lead for lead in leads if lead.get('phone')]
    print(f"[{datetime.now()}] Total leads found: {len(leads)}")
    print(f"[{datetime.now()}] Leads with phone numbers: {len(leads_with_phone)}")
    print(f"[{datetime.now()}] Leads without phone (skipped): {len(leads) - len(leads_with_phone)}")

    if leads_with_phone:
        saved_count = save_leads(leads_with_phone)
        print(f"[{datetime.now()}] ✓ Saved {saved_count} new leads (all with phone numbers)")
        print(f"[{datetime.now()}] ===== UPDATE COMPLETE =====")
        return saved_count

    print(f"[{datetime.now()}] ✗ No leads to save")
    print(f"[{datetime.now()}] Possible reasons:")
    print(f"[{datetime.now()}]   1. Sites may have changed HTML structure")
    print(f"[{datetime.now()}]   2. Sites may be blocking automated requests")
    print(f"[{datetime.now()}]   3. No companies found with visible phone numbers")
    print(f"[{datetime.now()}]   4. Network/connection issues")
    print(f"[{datetime.now()}] ===== UPDATE COMPLETE =====")
    return 0

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
    _initialize_paths() # Ensure paths are initialized on first request
    # If the database file doesn't exist, initialize it
    if not os.path.exists(DATABASE):
        init_db()
        # Also create an admin user if the database was just created
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", ('admin@example.com',))
        if not c.fetchone():
            password_hash = generate_password_hash('adminpassword') # Default admin password
            c.execute('''INSERT INTO users (email, password, credits, role, created_at)
                        VALUES (?, ?, 0, 'Admin', ?)''',
                     ('admin@example.com', password_hash, datetime.now()))
            conn.commit()
        conn.close()

    # Check if user is logged in
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/test')
def test():
    _initialize_paths() # Ensure paths are initialized on test route access
    try:
        # Test if database path is set correctly
        db_status = f"Database path: {DATABASE}"
        db_exists = os.path.exists(DATABASE)
        db_connection_status = ""
        if db_exists:
            try:
                conn = sqlite3.connect(DATABASE)
                conn.close()
                db_connection_status = "Database connection successful."
            except Exception as db_e:
                db_connection_status = f"Database connection FAILED: {db_e}"
        else:
            db_connection_status = "Database file DOES NOT EXIST."

        # Test if pandas is imported and working
        pandas_status = "pandas imported successfully." if pd else "pandas NOT imported."

        # Test if BeautifulSoup is imported and working
        bs4_status = "BeautifulSoup imported successfully." if BeautifulSoup else "BeautifulSoup NOT imported."

        # Test Leads folder path
        leads_folder_status = f"Leads folder path: {LEADS_FOLDER}"
        leads_folder_exists = os.path.exists(LEADS_FOLDER)
        leads_folder_content = ""
        if leads_folder_exists:
            try:
                leads_folder_content = f"Leads folder contents: {os.listdir(LEADS_FOLDER)[:5]}..."
            except Exception as lfc_e:
                leads_folder_content = f"Could not list Leads folder contents: {lfc_e}"
        else:
            leads_folder_content = "Leads folder DOES NOT EXIST."

        return jsonify({
            'status': 'ok',
            'message': 'Test route works',
            'db_info': db_status,
            'db_connection': db_connection_status,
            'pandas_status': pandas_status,
            'bs4_status': bs4_status,
            'leads_folder_info': leads_folder_status,
            'leads_folder_exists': leads_folder_exists,
            'leads_folder_content': leads_folder_content
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register new user"""
    if request.method == 'POST':
        try:
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

            # Create user with Customer role by default
            password_hash = generate_password_hash(password)
            c.execute('''INSERT INTO users (email, password, credits, role, created_at)
                        VALUES (?, ?, 0, 'Customer', ?)''',
                     (email, password_hash, datetime.now()))

            user_id = c.lastrowid
            conn.commit()
            conn.close()

            session['user_id'] = user_id
            session['email'] = email

            return jsonify({'status': 'success', 'redirect': '/dashboard'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Registration failed: {str(e)}'}), 500

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

@app.route('/leads')
def my_leads_page():
    """My leads page"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('my_leads.html')

@app.route('/api/lead/<int:lead_id>', methods=['GET'])
def get_lead_details(lead_id):
    """Get lead details by ID"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Get lead - only if it belongs to the user
    c.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id))
    lead = c.fetchone()
    conn.close()

    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    lead_data = {
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
        'created_at': lead[11],
        'locked_until': lead[13] if len(lead) > 13 else None
    }

    return jsonify(lead_data)

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
            'created_at': lead[11],
            'locked_until': lead[13] if len(lead) > 13 else None
        })

    return jsonify({'leads': leads_list, 'count': len(leads_list)})

@app.route('/api/generate-leads', methods=['POST'])
def generate_leads():
    """Generate new leads for user from Excel files"""
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

    # Load leads from Excel files if needed (only once, or periodically)
    # Check if we have enough unlocked leads first
    now = datetime.now()
    c.execute("""SELECT COUNT(*) FROM leads
                 WHERE (locked_until IS NULL OR locked_until < ?)
                 AND (user_id IS NULL OR user_id = 0)
                 AND phone IS NOT NULL AND phone != ''""", (now,))
    available_count = c.fetchone()[0]

    # If not enough leads, load from Excel
    if available_count < count:
        try:
            saved = save_leads_from_excel()
            # Re-check available count after loading
            c.execute("""SELECT COUNT(*) FROM leads
                         WHERE (locked_until IS NULL OR locked_until < ?)
                         AND (user_id IS NULL OR user_id = 0)
                         AND phone IS NOT NULL AND phone != ''""", (now,))
            available_count = c.fetchone()[0]
        except Exception as e:
            import traceback
            traceback.print_exc()

    # Get available leads that are NOT locked (locked_until is NULL or in the past)
    # AND have phone numbers (MANDATORY)
    # AND are not assigned to any user
    now = datetime.now()
    query = """SELECT * FROM leads
               WHERE (locked_until IS NULL OR locked_until < ?)
               AND (user_id IS NULL OR user_id = 0)
               AND phone IS NOT NULL AND phone != ''
               ORDER BY created_at DESC LIMIT ?"""

    c.execute(query, (now, count))
    leads = c.fetchall()

    if len(leads) < count:
        conn.close()
        return jsonify({
            'error': f'Only {len(leads)} available leads. Need {count} leads.',
            'available': len(leads),
            'requested': count
        }), 400

    # Calculate lock expiration date (180 days from now)
    lock_until = datetime.now() + timedelta(days=LOCK_DURATION_DAYS)

    # Assign leads to user and lock them for 180 days
    lead_ids = []
    for lead in leads:
        c.execute("""UPDATE leads
                    SET user_id = ?, status = 'Ny', last_updated = ?, locked_until = ?
                    WHERE id = ?""",
                 (user_id, datetime.now(), lock_until, lead[0]))
        lead_ids.append(lead[0])

    # Deduct credits
    c.execute("UPDATE users SET credits = credits - ? WHERE id = ?", (count, user_id))

    conn.commit()
    conn.close()

    return jsonify({
        'status': 'success',
        'leads_generated': len(lead_ids),
        'credits_remaining': credits - count,
        'lead_ids': lead_ids,
        'locked_until': lock_until.isoformat(),
        'message': f'Generated {len(lead_ids)} leads. Locked until {lock_until.strftime("%Y-%m-%d")}'
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
    import io
    import sys

    # Capture print output
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        count = update_leads()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return jsonify({
            'status': 'success',
            'leads_added': count,
            'message': f'Added {count} new leads',
            'log': output.split('\n')[-50:]  # Last 50 lines of output
        })
    except Exception as e:
        import traceback
        error_output = buffer.getvalue()
        traceback_output = traceback.format_exc()
        sys.stdout = old_stdout

        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': traceback_output,
            'log': error_output.split('\n')[-50:] if error_output else []
        }), 500

@app.route('/admin/add-credits', methods=['POST'])
def add_credits():
    """Add credits to user account (for testing)"""
    try:
        if not require_admin():
            return jsonify({'error': 'Admin access required'}), 403
    except Exception as e:
        return jsonify({'error': f'Access check failed: {str(e)}'}), 403
    try:
        user_id = request.json.get('user_id')
        credits = int(request.json.get('credits', 0))

        if not user_id or credits <= 0:
            return jsonify({'error': 'Invalid user_id or credits'}), 400

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        c.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (credits, user_id))

        if c.rowcount == 0:
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        c.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
        new_credits = c.fetchone()[0]

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'credits': new_credits, 'message': f'Added {credits} credits'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/get-user-id', methods=['GET'])
def get_user_id():
    """Get user ID by email (for testing)"""
    try:
        if not require_admin():
            return jsonify({'error': 'Admin access required'}), 403
    except Exception as e:
        return jsonify({'error': f'Access check failed: {str(e)}'}), 403
    if 'user_id' in session:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id, email, credits FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()

        if user:
            return jsonify({
                'user_id': user[0],
                'email': user[1],
                'credits': user[2]
            })
    return jsonify({'error': 'Not logged in'}), 401

@app.route('/admin/get-admin-info', methods=['GET'])
def get_admin_info():
    """Get admin user info"""
    try:
        if not require_admin():
            return jsonify({'error': 'Admin access required'}), 403
    except Exception as e:
        return jsonify({'error': f'Access check failed: {str(e)}'}), 403

    if 'admin_user_id' in session:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id, email, credits FROM users WHERE id = ?", (session['admin_user_id'],))
        user = c.fetchone()
        conn.close()

        if user:
            return jsonify({
                'user_id': user[0],
                'email': user[1],
                'credits': user[2]
            })
    return jsonify({'error': 'Not logged in'}), 401

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'GET':
        # If already logged in as admin, redirect to admin dashboard
        if 'admin_user_id' in session:
            try:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute("SELECT role FROM users WHERE id = ?", (session['admin_user_id'],))
                user = c.fetchone()
                conn.close()
                if user and user[0] == 'Admin':
                    return redirect(url_for('admin_page'))
            except:
                pass
        return render_template('admin_login.html')

    # POST - handle login
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        c.execute("SELECT id, password, role FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401

        # Check password
        if not check_password_hash(user[1], password):
            return jsonify({'error': 'Invalid email or password'}), 401

        # Check if user is admin
        if user[2] != 'Admin':
            return jsonify({'error': 'Access denied. Admin role required.'}), 403

        # Set admin session
        session['admin_user_id'] = user[0]
        session['admin_email'] = email

        return jsonify({'status': 'success', 'message': 'Login successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_user_id', None)
    session.pop('admin_email', None)
    return redirect(url_for('admin_login'))

def require_admin():
    """Check if user is admin"""
    try:
        if 'admin_user_id' not in session:
            return False

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE id = ?", (session['admin_user_id'],))
        user = c.fetchone()
        conn.close()

        if not user or user[0] != 'Admin':
            return False

        return True
    except Exception as e:
        # If there's any error, deny access
        return False

@app.route('/admin')
def admin_page():
    """Admin page for adding credits"""
    try:
        if not require_admin():
            return redirect(url_for('admin_login'))
        return render_template('admin_add_credits.html')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return redirect(url_for('admin_login'))

@app.route('/admin/load-excel', methods=['POST'])
def load_excel_manually():
    """Manually trigger Excel file loading"""
    try:
        if not require_admin():
            return jsonify({'error': 'Admin access required'}), 403
    except Exception as e:
        return jsonify({'error': f'Access check failed: {str(e)}'}), 403

    import io
    import sys

    # Capture print output
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        count = save_leads_from_excel()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return jsonify({
            'status': 'success',
            'leads_loaded': count,
            'message': f'Loaded {count} new leads from Excel files',
            'log': output.split('\n')[-50:]  # Last 50 lines
        })
    except Exception as e:
        import traceback
        error_output = buffer.getvalue()
        traceback_output = traceback.format_exc()
        sys.stdout = old_stdout

        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': traceback_output,
            'log': error_output.split('\n')[-50:] if error_output else []
        }), 500

@app.route('/admin/check-leads', methods=['GET'])
def check_leads():
    """Check how many leads are available"""
    try:
        if not require_admin():
            return jsonify({'error': 'Admin access required'}), 403
    except Exception as e:
        return jsonify({'error': f'Access check failed: {str(e)}'}), 403
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    now = datetime.now()

    # Total leads in database
    c.execute("SELECT COUNT(*) FROM leads")
    total = c.fetchone()[0]

    # Leads with phone numbers
    c.execute("SELECT COUNT(*) FROM leads WHERE phone IS NOT NULL AND phone != ''")
    with_phone = c.fetchone()[0]

    # Unlocked leads (available for assignment)
    c.execute("""SELECT COUNT(*) FROM leads
                 WHERE (locked_until IS NULL OR locked_until < ?) 
                 AND (user_id IS NULL OR user_id = 0)
                 AND phone IS NOT NULL AND phone != ''""", (now,))
    available = c.fetchone()[0]

    # Locked leads
    c.execute("""SELECT COUNT(*) FROM leads
                 WHERE locked_until IS NOT NULL AND locked_until >= ?""", (now,))
    locked = c.fetchone()[0]

    # Assigned leads
    c.execute("SELECT COUNT(*) FROM leads WHERE user_id IS NOT NULL AND user_id != 0")
    assigned = c.fetchone()[0]

    conn.close()

    return jsonify({
        'total_leads': total,
        'leads_with_phone': with_phone,
        'available_leads': available,
        'locked_leads': locked,
        'assigned_leads': assigned
    })


# Removed pages "Rapporter" and "Mallar" (as per previous instructions)

# Main entry point
if __name__ == '__main__':
    _initialize_paths()
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True)
