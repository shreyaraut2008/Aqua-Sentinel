from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os
import base64
import json
import google.generativeai as genai

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static',
            static_url_path='/static')

# Configuration - use environment variables on Render
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'aqua-sentinel-secret-key-dev-only')
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Render PostgreSQL uses "postgres://" but SQLAlchemy 1.4+ expects "postgresql://"
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///auth.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Gemini API Configuration - set GEMINI_API_KEY in Render Environment
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    genai.configure(api_key='')  # Will fail on scan if not set

# Initialize database
db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    scans = db.relationship('ScanHistory', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Scan History Model
class ScanHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    species_name = db.Column(db.String(200), nullable=False)
    scientific_name = db.Column(db.String(200))
    confidence = db.Column(db.String(20))
    rarity = db.Column(db.String(50))
    danger_level = db.Column(db.String(50))
    habitat_match = db.Column(db.String(100))
    conservation_status = db.Column(db.String(100))
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    image_data = db.Column(db.Text)  # Base64 encoded
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create database tables
with app.app_context():
    db.create_all()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'error')
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

# Enable static file serving with cache control
@app.after_request
def set_cache_control(response):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

@app.route('/')
def index():
    """Serve the main homepage"""
    return render_template('index.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    """Handle user sign in"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Welcome back, ' + user.username + '!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle user registration"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('signup.html')
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('signup.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('signup.html')
        
        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please sign in.', 'success')
        return redirect(url_for('signin'))
    
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Serve the dashboard page after login"""
    username = session.get('username', 'Explorer')
    return render_template('dashboard.html', username=username)

@app.route('/scan')
@login_required
def scan():
    """Serve the scan species page"""
    username = session.get('username', 'Explorer')
    return render_template('scan.html', username=username)

@app.route('/report')
@login_required
def report():
    """Serve the scan report page"""
    username = session.get('username', 'Explorer')
    return render_template('report.html', username=username)

@app.route('/api/scan', methods=['POST'])
@login_required
def api_scan():
    """Process image scan with Gemini AI"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        image_data = data.get('image')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        region = data.get('region', 'Unknown')
        country = data.get('country', 'Unknown')
        full_address = data.get('fullAddress', 'Unknown location')
        
        if not image_data:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        # Extract base64 image data
        if ',' in image_data:
            image_base64 = image_data.split(',')[1]
        else:
            image_base64 = image_data
        
        # Prepare the prompt for Gemini
        prompt = f"""You are a marine biology expert AI. Analyze this image of a marine species and provide detailed information.

Location Context:
- Coordinates: {latitude}°, {longitude}°
- Region: {region}
- Country: {country}
- Full Location: {full_address}

Please analyze the image and respond with ONLY a valid JSON object (no markdown, no code blocks, just pure JSON) with the following structure:
{{
    "species_name": "Common name of the species",
    "scientific_name": "Scientific/Latin name",
    "confidence": "XX%" (your confidence level in the identification),
    "rarity": "Common" or "Uncommon" or "Rare" or "Endangered",
    "danger_level": "None" or "Low" or "Moderate" or "High" or "Extremely Dangerous",
    "habitat_match": "High Match" or "Moderate Match" or "Low Match" or "Outside Typical Habitat" (based on the location provided),
    "conservation_status": "Least Concern" or "Near Threatened" or "Vulnerable" or "Endangered" or "Critically Endangered" or "Data Deficient",
    "description": "A detailed 2-3 sentence description of the species, its characteristics, behavior, and interesting facts."
}}

If you cannot identify a marine species in the image, respond with:
{{
    "species_name": "Unidentified",
    "scientific_name": "N/A",
    "confidence": "0%",
    "rarity": "Unknown",
    "danger_level": "Unknown",
    "habitat_match": "Unknown",
    "conservation_status": "Unknown",
    "description": "Unable to identify a marine species in this image. Please ensure the image clearly shows a marine organism."
}}"""

        # Initialize Gemini model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Decode image for Gemini
        image_bytes = base64.b64decode(image_base64)
        
        # Create image part for Gemini
        image_part = {
            'mime_type': 'image/jpeg',
            'data': image_bytes
        }
        
        # Generate response
        response = model.generate_content([prompt, image_part])
        
        # Parse the response
        response_text = response.text.strip()
        
        # Clean up response if it contains markdown code blocks
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("Could not parse AI response")
        
        # Add location info to result
        result['location'] = full_address
        result['latitude'] = latitude
        result['longitude'] = longitude
        
        # Auto-save the scan to database
        try:
            scan = ScanHistory(
                user_id=session.get('user_id'),
                species_name=result.get('species_name', 'Unknown'),
                scientific_name=result.get('scientific_name', ''),
                confidence=result.get('confidence', ''),
                rarity=result.get('rarity', ''),
                danger_level=result.get('danger_level', ''),
                habitat_match=result.get('habitat_match', ''),
                conservation_status=result.get('conservation_status', ''),
                description=result.get('description', ''),
                location=result.get('location', ''),
                latitude=latitude,
                longitude=longitude,
                image_data=image_data[:500000] if image_data else None
            )
            db.session.add(scan)
            db.session.commit()
            result['scan_id'] = scan.id
        except Exception as save_error:
            print(f"Auto-save error: {str(save_error)}")
            db.session.rollback()
        
        return jsonify({'success': True, 'result': result})
        
    except Exception as e:
        print(f"Scan error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/scan-report/<int:scan_id>')
@login_required
def view_scan_report(scan_id):
    """View a specific saved scan report"""
    username = session.get('username', 'Explorer')
    user_id = session.get('user_id')
    
    scan = ScanHistory.query.filter_by(id=scan_id, user_id=user_id).first()
    
    if not scan:
        flash('Scan not found.', 'error')
        return redirect(url_for('recent_scans'))
    
    return render_template('view_report.html', username=username, scan=scan)

@app.route('/recent-scans')
@login_required
def recent_scans():
    """View recent scan history"""
    username = session.get('username', 'Explorer')
    user_id = session.get('user_id')
    scans = ScanHistory.query.filter_by(user_id=user_id).order_by(ScanHistory.scanned_at.desc()).limit(20).all()
    return render_template('recent_scans.html', username=username, scans=scans)

@app.route('/signout')
def signout():
    """Handle user sign out"""
    session.clear()
    flash('You have been signed out.', 'success')
    return redirect(url_for('index'))

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'AquaSentinel is running'}), 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('index.html'), 200

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Development: python app.py. Production: use gunicorn (see Render)
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
