from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import sqlite3
import uuid
import html
import json
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Email configuration (set via environment variables or database)
def load_email_config():
    """Load email configuration from database or environment variables"""
    # First try environment variables (takes precedence)
    if os.environ.get('MAIL_USERNAME') and os.environ.get('MAIL_PASSWORD'):
        app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
        app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
        app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
        app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
        app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '')
    else:
        # Try loading from database
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM email_config LIMIT 1')
            config = cursor.fetchone()
            conn.close()
            
            if config and config['mail_username'] and config['mail_password']:
                app.config['MAIL_SERVER'] = config['mail_server'] or 'smtp.gmail.com'
                app.config['MAIL_PORT'] = config['mail_port'] or 587
                app.config['MAIL_USE_TLS'] = bool(config['mail_use_tls'])
                app.config['MAIL_USE_SSL'] = bool(config['mail_use_ssl'])
                app.config['MAIL_USERNAME'] = config['mail_username'] or ''
                app.config['MAIL_PASSWORD'] = config['mail_password'] or ''
                app.config['MAIL_DEFAULT_SENDER'] = config['mail_default_sender'] or ''
            else:
                # Defaults
                app.config['MAIL_SERVER'] = 'smtp.gmail.com'
                app.config['MAIL_PORT'] = 587
                app.config['MAIL_USE_TLS'] = True
                app.config['MAIL_USE_SSL'] = False
                app.config['MAIL_USERNAME'] = ''
                app.config['MAIL_PASSWORD'] = ''
                app.config['MAIL_DEFAULT_SENDER'] = ''
        except:
            # Defaults if database not ready
            app.config['MAIL_SERVER'] = 'smtp.gmail.com'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            app.config['MAIL_USERNAME'] = ''
            app.config['MAIL_PASSWORD'] = ''
            app.config['MAIL_DEFAULT_SENDER'] = ''

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    """Get database connection"""
    conn = sqlite3.connect('blog.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            author_name TEXT NOT NULL,
            category TEXT NOT NULL,
            published_date DATE NOT NULL,
            cover_image_filename TEXT NOT NULL,
            content_html TEXT NOT NULL,
            short_summary TEXT DEFAULT 'Short summary of the article will go here eventually'
        )
    ''')
    
    # Add short_summary column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE articles ADD COLUMN short_summary TEXT DEFAULT "Short summary of the article will go here eventually"')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS about_page (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_name TEXT NOT NULL,
            author_photo_filename TEXT NOT NULL,
            author_bio_text TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            display_name TEXT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_approved INTEGER DEFAULT 1,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            viewer_token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            UNIQUE(article_id, viewer_token)
        )
    ''')
    
    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_article_id ON comments(article_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_likes_article_id ON likes(article_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_likes_viewer_token ON likes(viewer_token)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viewer_token TEXT NOT NULL,
            path TEXT NOT NULL,
            referrer TEXT,
            user_agent TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS article_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            viewer_token TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
    ''')
    
    # Create indexes for analytics
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_page_views_viewer_token ON page_views(viewer_token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_page_views_path ON page_views(path)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_page_views_started_at ON page_views(started_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_views_article_id ON article_views(article_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_views_viewer_token ON article_views(viewer_token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_views_started_at ON article_views(started_at)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add name column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE subscribers ADD COLUMN name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail_server TEXT DEFAULT 'smtp.gmail.com',
            mail_port INTEGER DEFAULT 587,
            mail_use_tls INTEGER DEFAULT 1,
            mail_use_ssl INTEGER DEFAULT 0,
            mail_username TEXT DEFAULT '',
            mail_password TEXT DEFAULT '',
            mail_default_sender TEXT DEFAULT ''
        )
    ''')
    
    # Initialize email config if it doesn't exist
    cursor.execute('SELECT COUNT(*) as count FROM email_config')
    config_count = cursor.fetchone()['count']
    if config_count == 0:
        cursor.execute('''
            INSERT INTO email_config (mail_server, mail_port, mail_use_tls, mail_use_ssl)
            VALUES ('smtp.gmail.com', 587, 1, 0)
        ''')
    
    conn.commit()
    conn.close()

def generate_slug(title):
    """Generate URL-friendly slug from title"""
    slug = title.lower()
    slug = ''.join(c if c.isalnum() or c in (' ', '-') else '' for c in slug)
    slug = '-'.join(slug.split())
    return slug

def get_or_create_viewer_token():
    """Get viewer token from cookie or create a new one"""
    viewer_token = request.cookies.get('viewer_token')
    if not viewer_token:
        viewer_token = str(uuid.uuid4())
    return viewer_token

def set_viewer_token_cookie(response, viewer_token):
    """Set viewer token cookie"""
    response.set_cookie('viewer_token', viewer_token, max_age=365*24*60*60)  # 1 year
    return response

@app.template_filter('cover_image_url')
def cover_image_url(filename):
    """Get the URL for a cover image"""
    if filename == 'cover_image.png':
        return url_for('static', filename='graphics/cover_image.png')
    else:
        return url_for('static', filename=f'uploads/{filename}')

@app.template_filter('author_photo_url')
def author_photo_url(filename):
    """Get the URL for an author photo"""
    if filename == 'cover_image.png':
        return url_for('static', filename='graphics/cover_image.png')
    else:
        return url_for('static', filename=f'uploads/{filename}')

@app.template_filter('safe_get')
def safe_get(row, key, default=''):
    """Safely get a value from a sqlite3.Row object"""
    try:
        value = row[key]
        return value if value is not None else default
    except (KeyError, IndexError, TypeError):
        return default

def validate_email(email):
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_email_to_subscribers(subject, body):
    """Send email to all subscribers"""
    # Reload config in case it was updated
    load_email_config()
    
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        return {'success': False, 'message': 'Email configuration not set. Please configure email settings in the admin panel (Admin Dashboard > Email Configuration).'}
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT email FROM subscribers')
        subscribers = cursor.fetchall()
        conn.close()
        
        if not subscribers:
            return {'success': False, 'message': 'No subscribers found'}
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = app.config['MAIL_DEFAULT_SENDER'] or app.config['MAIL_USERNAME']
        
        # Convert body to HTML if it's plain text
        html_body = body.replace('\n', '<br>')
        
        # Create both plain text and HTML versions
        text_part = MIMEText(body, 'plain')
        html_part = MIMEText(html_body, 'html')
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Use BCC to send to all subscribers
        bcc_list = [sub['email'] for sub in subscribers]
        
        # Connect to SMTP server
        if app.config['MAIL_USE_SSL']:
            server = smtplib.SMTP_SSL(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        else:
            server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
            if app.config['MAIL_USE_TLS']:
                server.starttls()
        
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        
        # Send to each subscriber (using BCC in sendmail)
        server.sendmail(
            app.config['MAIL_DEFAULT_SENDER'] or app.config['MAIL_USERNAME'],
            bcc_list,
            msg.as_string()
        )
        server.quit()
        
        return {'success': True, 'message': f'Email sent to {len(subscribers)} subscribers'}
    except Exception as e:
        return {'success': False, 'message': f'Error sending email: {str(e)}'}

def admin_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes

@app.route('/')
def home():
    """Home page with logo, description, and latest articles carousel"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM articles 
        ORDER BY published_date DESC 
        LIMIT 10
    ''')
    articles = cursor.fetchall()
    conn.close()
    return render_template('home.html', articles=articles)

@app.route('/songbird-magazine')
def songbird_magazine():
    """Category page for Songbird Magazine"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM articles 
        WHERE category = 'Songbird Magazine'
        ORDER BY published_date DESC
    ''')
    articles = cursor.fetchall()
    conn.close()
    return render_template('category.html', articles=articles, category='Songbird Magazine')

@app.route('/angsty-entries')
def angsty_entries():
    """Category page for Angsty Entries"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM articles 
        WHERE category = 'Angsty Entries'
        ORDER BY published_date DESC
    ''')
    articles = cursor.fetchall()
    conn.close()
    return render_template('category.html', articles=articles, category='Angsty Entries')

@app.route('/quick-reads')
def quick_reads():
    """Category page for Quick Reads"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM articles 
        WHERE category = 'Quick Reads'
        ORDER BY published_date DESC
    ''')
    articles = cursor.fetchall()
    conn.close()
    return render_template('category.html', articles=articles, category='Quick Reads')

@app.route('/archive')
def archive():
    """Complete archive page"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM articles 
        ORDER BY published_date DESC
    ''')
    articles = cursor.fetchall()
    conn.close()
    return render_template('archive.html', articles=articles)

@app.route('/about')
def about():
    """About the Author page"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM about_page LIMIT 1')
    about_data = cursor.fetchone()
    conn.close()
    
    # Use defaults if no data exists
    if not about_data:
        about_data = {
            'author_name': 'Kylee',
            'author_photo_filename': 'cover_image.png',
            'author_bio_text': 'Welcome to my blog! I\'m a twenty-something journalist passionate about storytelling, writing, and sharing experiences through words.\n\nThis space is where I explore topics that matter to me, from in-depth features to quick thoughts and everything in between.\n\nThank you for joining me on this journey.'
        }
    
    return render_template('about.html', about_data=about_data)

@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    """Subscribe page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        
        if not email:
            flash('Email address is required.', 'error')
            return render_template('subscribe.html')
        
        if not validate_email(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('subscribe.html')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT id FROM subscribers WHERE email = ?', (email,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            flash('You\'re already subscribed!', 'info')
            return render_template('subscribe.html', subscribed=True, existing=True)
        
        # Insert new subscriber
        try:
            cursor.execute('INSERT INTO subscribers (email, name) VALUES (?, ?)', (email, name if name else None))
            conn.commit()
            conn.close()
            flash('Thanks for subscribing!', 'success')
            return render_template('subscribe.html', subscribed=True, existing=False)
        except sqlite3.IntegrityError:
            conn.close()
            flash('You\'re already subscribed!', 'info')
            return render_template('subscribe.html', subscribed=True, existing=True)
    
    return render_template('subscribe.html')

@app.route('/article/<slug>')
def article_detail(slug):
    """Article detail page"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM articles WHERE slug = ?', (slug,))
    article = cursor.fetchone()
    
    if not article:
        conn.close()
        flash('Article not found.', 'error')
        return redirect(url_for('home'))
    
    article_id = article['id']
    
    # Get likes count
    cursor.execute('SELECT COUNT(*) as count FROM likes WHERE article_id = ?', (article_id,))
    like_count = cursor.fetchone()['count']
    
    # Check if current viewer has liked
    viewer_token = get_or_create_viewer_token()
    cursor.execute('SELECT id FROM likes WHERE article_id = ? AND viewer_token = ?', (article_id, viewer_token))
    has_liked = cursor.fetchone() is not None
    
    # Get approved comments (newest first)
    cursor.execute('''
        SELECT * FROM comments 
        WHERE article_id = ? AND is_approved = 1
        ORDER BY created_at DESC
    ''', (article_id,))
    comments = cursor.fetchall()
    
    conn.close()
    
    # Create response and set cookie if needed
    response = make_response(render_template('article.html', 
        article=article, 
        like_count=like_count, 
        has_liked=has_liked,
        comments=comments))
    
    if not request.cookies.get('viewer_token'):
        response = set_viewer_token_cookie(response, viewer_token)
    
    return response

@app.route('/article/<slug>/like', methods=['POST'])
def toggle_like(slug):
    """Toggle like for an article"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get article
    cursor.execute('SELECT id FROM articles WHERE slug = ?', (slug,))
    article = cursor.fetchone()
    
    if not article:
        conn.close()
        return jsonify({'error': 'Article not found'}), 404
    
    article_id = article['id']
    viewer_token = get_or_create_viewer_token()
    
    # Check if already liked
    cursor.execute('SELECT id FROM likes WHERE article_id = ? AND viewer_token = ?', (article_id, viewer_token))
    existing_like = cursor.fetchone()
    
    if existing_like:
        # Remove like
        cursor.execute('DELETE FROM likes WHERE article_id = ? AND viewer_token = ?', (article_id, viewer_token))
        has_liked = False
    else:
        # Add like
        cursor.execute('INSERT INTO likes (article_id, viewer_token) VALUES (?, ?)', (article_id, viewer_token))
        has_liked = True
    
    # Get updated count
    cursor.execute('SELECT COUNT(*) as count FROM likes WHERE article_id = ?', (article_id,))
    like_count = cursor.fetchone()['count']
    
    conn.commit()
    conn.close()
    
    response = jsonify({'has_liked': has_liked, 'like_count': like_count})
    if not request.cookies.get('viewer_token'):
        response = set_viewer_token_cookie(response, viewer_token)
    return response

@app.route('/article/<slug>/comment', methods=['POST'])
def post_comment(slug):
    """Post a comment on an article"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get article
    cursor.execute('SELECT id FROM articles WHERE slug = ?', (slug,))
    article = cursor.fetchone()
    
    if not article:
        conn.close()
        flash('Article not found.', 'error')
        return redirect(url_for('home'))
    
    article_id = article['id']
    viewer_token = get_or_create_viewer_token()
    
    # Simple rate limiting: check last comment (basic protection)
    cursor.execute('''
        SELECT created_at FROM comments 
        ORDER BY created_at DESC LIMIT 1
    ''')
    last_comment = cursor.fetchone()
    
    if last_comment:
        try:
            last_time = datetime.fromisoformat(last_comment['created_at'].replace(' ', 'T'))
        except:
            try:
                last_time = datetime.strptime(last_comment['created_at'], '%Y-%m-%d %H:%M:%S')
            except:
                last_time = datetime.now()
        time_diff = (datetime.now() - last_time).total_seconds()
        if time_diff < 15:
            conn.close()
            flash('Please wait a moment before posting another comment.', 'error')
            return redirect(url_for('article_detail', slug=slug))
    
    # Get form data
    display_name = request.form.get('display_name', '').strip()
    content = request.form.get('content', '').strip()
    honeypot = request.form.get('website', '')  # Honeypot field
    
    # Validation
    if honeypot:  # If honeypot is filled, it's a bot
        conn.close()
        flash('Invalid submission.', 'error')
        return redirect(url_for('article_detail', slug=slug))
    
    if not content or len(content) < 1:
        conn.close()
        flash('Comment content is required.', 'error')
        return redirect(url_for('article_detail', slug=slug))
    
    if len(content) > 2000:
        conn.close()
        flash('Comment is too long. Maximum 2000 characters.', 'error')
        return redirect(url_for('article_detail', slug=slug))
    
    if len(display_name) > 40:
        conn.close()
        flash('Name is too long. Maximum 40 characters.', 'error')
        return redirect(url_for('article_detail', slug=slug))
    
    # Set default name if empty
    if not display_name:
        display_name = 'Anonymous'
    
    # Escape HTML to prevent XSS
    display_name = html.escape(display_name)
    content = html.escape(content)
    
    # Insert comment
    cursor.execute('''
        INSERT INTO comments (article_id, display_name, content, is_approved)
        VALUES (?, ?, ?, 1)
    ''', (article_id, display_name, content))
    
    conn.commit()
    conn.close()
    
    flash('Comment posted successfully!', 'success')
    response = redirect(url_for('article_detail', slug=slug))
    if not request.cookies.get('viewer_token'):
        response = set_viewer_token_cookie(response, viewer_token)
    return response

# Admin routes

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'kyleekallick2002':
            session['admin_logged_in'] = True
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password.', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('Successfully logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM articles ORDER BY published_date DESC')
    articles = cursor.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', articles=articles)

@app.route('/admin/new', methods=['GET', 'POST'])
@admin_required
def admin_new_article():
    """Create new article"""
    if request.method == 'POST':
        title = request.form.get('title')
        author_name = request.form.get('author_name')
        published_date = request.form.get('published_date')
        category = request.form.get('category')
        content_html = request.form.get('content_html')
        
        # Handle cover image upload
        cover_image_filename = 'cover_image.png'  # default
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                cover_image_filename = filename
        
        slug = generate_slug(title)
        
        # Ensure slug is unique
        conn = get_db()
        cursor = conn.cursor()
        counter = 1
        original_slug = slug
        while True:
            cursor.execute('SELECT id FROM articles WHERE slug = ?', (slug,))
            if cursor.fetchone():
                slug = f"{original_slug}-{counter}"
                counter += 1
            else:
                break
        
        short_summary = request.form.get('short_summary', 'Short summary of the article will go here eventually').strip()
        if not short_summary:
            short_summary = 'Short summary of the article will go here eventually'
        
        cursor.execute('''
            INSERT INTO articles (title, slug, author_name, category, published_date, cover_image_filename, content_html, short_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, slug, author_name, category, published_date, cover_image_filename, content_html, short_summary))
        
        conn.commit()
        conn.close()
        
        # Handle email to subscribers if requested
        send_email = request.form.get('send_email_to_subscribers') == 'on'
        if send_email:
            email_subject = request.form.get('email_subject', f'New Article: {title}')
            email_body = request.form.get('email_body', '')
            if email_body:
                email_result = send_email_to_subscribers(email_subject, email_body)
                if email_result['success']:
                    flash(f'Article created successfully! {email_result["message"]}', 'success')
                else:
                    flash(f'Article created successfully, but email sending failed: {email_result["message"]}', 'error')
            else:
                flash('Article created successfully! Email body was empty, so no email was sent.', 'info')
        else:
            flash('Article created successfully!', 'success')
        
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_new.html')

@app.route('/admin/preview', methods=['POST'])
@admin_required
def admin_preview_article():
    """Preview article before saving"""
    # Get form data
    title = request.form.get('title', 'Untitled Article')
    author_name = request.form.get('author_name', 'Author')
    published_date = request.form.get('published_date', date.today().isoformat())
    category = request.form.get('category', 'Uncategorized')
    content_html = request.form.get('content_html', '')
    short_summary = request.form.get('short_summary', 'Short summary of the article will go here eventually')
    
    # Handle cover image - use default for preview, or upload if provided
    cover_image_filename = 'cover_image.png'
    if 'cover_image' in request.files:
        file = request.files['cover_image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            cover_image_filename = filename
    
    # Create a mock article object for preview
    preview_article = {
        'id': 0,
        'title': title,
        'slug': 'preview',
        'author_name': author_name,
        'category': category,
        'published_date': published_date,
        'cover_image_filename': cover_image_filename,
        'content_html': content_html,
        'short_summary': short_summary
    }
    
    return render_template('article.html', 
                         article=preview_article,
                         like_count=0,
                         has_liked=False,
                         comments=[])

@app.route('/admin/edit/<int:article_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_article(article_id):
    """Edit existing article"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        author_name = request.form.get('author_name')
        published_date = request.form.get('published_date')
        category = request.form.get('category')
        content_html = request.form.get('content_html')
        short_summary = request.form.get('short_summary', 'Short summary of the article will go here eventually').strip()
        if not short_summary:
            short_summary = 'Short summary of the article will go here eventually'
        
        # Handle cover image upload (optional)
        cursor.execute('SELECT cover_image_filename FROM articles WHERE id = ?', (article_id,))
        existing = cursor.fetchone()
        cover_image_filename = existing['cover_image_filename']
        
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                cover_image_filename = filename
        
        slug = generate_slug(title)
        
        # Ensure slug is unique (except for current article)
        counter = 1
        original_slug = slug
        while True:
            cursor.execute('SELECT id FROM articles WHERE slug = ? AND id != ?', (slug, article_id))
            if cursor.fetchone():
                slug = f"{original_slug}-{counter}"
                counter += 1
            else:
                break
        
        cursor.execute('''
            UPDATE articles 
            SET title = ?, slug = ?, author_name = ?, category = ?, published_date = ?, 
                cover_image_filename = ?, content_html = ?, short_summary = ?
            WHERE id = ?
        ''', (title, slug, author_name, category, published_date, cover_image_filename, content_html, short_summary, article_id))
        
        conn.commit()
        conn.close()
        
        # Handle email to subscribers if requested
        send_email = request.form.get('send_email_to_subscribers') == 'on'
        if send_email:
            email_subject = request.form.get('email_subject', f'Updated Article: {title}')
            email_body = request.form.get('email_body', '')
            if email_body:
                email_result = send_email_to_subscribers(email_subject, email_body)
                if email_result['success']:
                    flash(f'Article updated successfully! {email_result["message"]}', 'success')
                else:
                    flash(f'Article updated successfully, but email sending failed: {email_result["message"]}', 'error')
            else:
                flash('Article updated successfully! Email body was empty, so no email was sent.', 'info')
        else:
            flash('Article updated successfully!', 'success')
        
        return redirect(url_for('admin_dashboard'))
    
    cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
    article = cursor.fetchone()
    conn.close()
    
    if not article:
        flash('Article not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_edit.html', article=article)

@app.route('/admin/upload_image', methods=['POST'])
@admin_required
def upload_image():
    """Handle image uploads from rich text editor"""
    if 'image' not in request.files:
        return {'error': 'No file provided'}, 400
    
    file = request.files['image']
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Return URL relative to static folder
        url = url_for('static', filename=f'uploads/{filename}')
        return {'url': url}
    
    return {'error': 'Invalid file type'}, 400

@app.route('/admin/edit-about', methods=['GET', 'POST'])
@admin_required
def admin_edit_about():
    """Edit About the Author page"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        author_name = request.form.get('author_name')
        author_bio_text = request.form.get('author_bio_text')
        
        # Handle author photo upload
        cursor.execute('SELECT author_photo_filename FROM about_page LIMIT 1')
        existing = cursor.fetchone()
        author_photo_filename = 'cover_image.png'  # default
        
        if existing:
            author_photo_filename = existing['author_photo_filename']
        
        if 'author_photo' in request.files:
            file = request.files['author_photo']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                author_photo_filename = filename
        
        # Check if about_page record exists
        cursor.execute('SELECT id FROM about_page LIMIT 1')
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
                UPDATE about_page 
                SET author_name = ?, author_photo_filename = ?, author_bio_text = ?
                WHERE id = ?
            ''', (author_name, author_photo_filename, author_bio_text, exists['id']))
        else:
            cursor.execute('''
                INSERT INTO about_page (author_name, author_photo_filename, author_bio_text)
                VALUES (?, ?, ?)
            ''', (author_name, author_photo_filename, author_bio_text))
        
        conn.commit()
        conn.close()
        
        flash('About page updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    # GET request - load existing data
    cursor.execute('SELECT * FROM about_page LIMIT 1')
    about_data = cursor.fetchone()
    conn.close()
    
    # Use defaults if no data exists
    if not about_data:
        about_data = {
            'author_name': 'Kylee',
            'author_photo_filename': 'cover_image.png',
            'author_bio_text': 'Welcome to my blog! I\'m a twenty-something journalist passionate about storytelling, writing, and sharing experiences through words.\n\nThis space is where I explore topics that matter to me, from in-depth features to quick thoughts and everything in between.\n\nThank you for joining me on this journey.'
        }
    
    return render_template('admin_edit_about.html', about_data=about_data)

@app.route('/admin/comments')
@admin_required
def admin_comments():
    """Admin page to manage comments"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, a.title, a.slug 
        FROM comments c
        JOIN articles a ON c.article_id = a.id
        ORDER BY c.created_at DESC
        LIMIT 100
    ''')
    comments = cursor.fetchall()
    conn.close()
    return render_template('admin_comments.html', comments=comments)

@app.route('/admin/comments/delete/<int:comment_id>', methods=['POST'])
@admin_required
def admin_delete_comment(comment_id):
    """Delete a comment"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()
    flash('Comment deleted successfully.', 'success')
    return redirect(url_for('admin_comments'))

@app.route('/admin/subscribers')
@admin_required
def admin_subscribers():
    """Admin page to view subscribers"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM subscribers ORDER BY created_at DESC')
    subscribers = cursor.fetchall()
    conn.close()
    return render_template('admin_subscribers.html', subscribers=subscribers)

# Tracking endpoints
@app.route('/track/view/start', methods=['POST'])
def track_view_start():
    """Start tracking a page view"""
    viewer_token = get_or_create_viewer_token()
    path = request.json.get('path', request.path)
    referrer = request.json.get('referrer', request.referrer)
    user_agent = request.json.get('user_agent', request.headers.get('User-Agent'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO page_views (viewer_token, path, referrer, user_agent)
        VALUES (?, ?, ?, ?)
    ''', (viewer_token, path, referrer, user_agent))
    view_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    response = jsonify({'view_id': view_id})
    if not request.cookies.get('viewer_token'):
        response = set_viewer_token_cookie(response, viewer_token)
    return response

@app.route('/track/view/end', methods=['POST'])
def track_view_end():
    """End tracking a page view"""
    if not request.is_json:
        # Handle sendBeacon (which sends as text/plain)
        try:
            data = json.loads(request.data)
        except:
            return jsonify({'error': 'Invalid request'}), 400
    else:
        data = request.json
    
    view_id = data.get('view_id')
    duration = data.get('duration_seconds', 0)
    
    # Validate and clamp duration
    if not view_id or duration < 0:
        return jsonify({'error': 'Invalid request'}), 400
    
    duration = min(max(int(duration), 0), 7200)  # Clamp 0-7200 seconds
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE page_views 
        SET duration_seconds = ?
        WHERE id = ?
    ''', (duration, view_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/track/article/start', methods=['POST'])
def track_article_start():
    """Start tracking an article view"""
    viewer_token = get_or_create_viewer_token()
    article_id = request.json.get('article_id')
    
    if not article_id:
        return jsonify({'error': 'article_id required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO article_views (article_id, viewer_token)
        VALUES (?, ?)
    ''', (article_id, viewer_token))
    view_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    response = jsonify({'view_id': view_id})
    if not request.cookies.get('viewer_token'):
        response = set_viewer_token_cookie(response, viewer_token)
    return response

@app.route('/track/article/end', methods=['POST'])
def track_article_end():
    """End tracking an article view"""
    if not request.is_json:
        # Handle sendBeacon (which sends as text/plain)
        try:
            data = json.loads(request.data)
        except:
            return jsonify({'error': 'Invalid request'}), 400
    else:
        data = request.json
    
    view_id = data.get('view_id')
    duration = data.get('duration_seconds', 0)
    
    if not view_id or duration < 0:
        return jsonify({'error': 'Invalid request'}), 400
    
    duration = min(max(int(duration), 0), 7200)  # Clamp 0-7200 seconds
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE article_views 
        SET duration_seconds = ?
        WHERE id = ?
    ''', (duration, view_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/email-config', methods=['GET', 'POST'])
@admin_required
def admin_email_config():
    """Admin page to configure email settings"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        mail_server = request.form.get('mail_server', 'smtp.gmail.com')
        mail_port = int(request.form.get('mail_port', 587))
        mail_use_tls = 1 if request.form.get('mail_use_tls') == 'on' else 0
        mail_use_ssl = 1 if request.form.get('mail_use_ssl') == 'on' else 0
        mail_username = request.form.get('mail_username', '')
        mail_password = request.form.get('mail_password', '')
        mail_default_sender = request.form.get('mail_default_sender', '')
        
        # Check if config exists
        cursor.execute('SELECT id FROM email_config LIMIT 1')
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE email_config 
                SET mail_server = ?, mail_port = ?, mail_use_tls = ?, mail_use_ssl = ?,
                    mail_username = ?, mail_password = ?, mail_default_sender = ?
                WHERE id = ?
            ''', (mail_server, mail_port, mail_use_tls, mail_use_ssl, 
                  mail_username, mail_password, mail_default_sender, existing['id']))
        else:
            cursor.execute('''
                INSERT INTO email_config (mail_server, mail_port, mail_use_tls, mail_use_ssl,
                                         mail_username, mail_password, mail_default_sender)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (mail_server, mail_port, mail_use_tls, mail_use_ssl,
                  mail_username, mail_password, mail_default_sender))
        
        conn.commit()
        conn.close()
        
        # Reload email config
        load_email_config()
        
        flash('Email configuration saved successfully!', 'success')
        return redirect(url_for('admin_email_config'))
    
    # GET request - load current config
    cursor.execute('SELECT * FROM email_config LIMIT 1')
    config = cursor.fetchone()
    conn.close()
    
    if not config:
        config = {
            'mail_server': 'smtp.gmail.com',
            'mail_port': 587,
            'mail_use_tls': 1,
            'mail_use_ssl': 0,
            'mail_username': '',
            'mail_password': '',
            'mail_default_sender': ''
        }
    
    return render_template('admin_email_config.html', config=config)

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    """Admin analytics dashboard"""
    days = request.args.get('days', 60, type=int)
    if days not in [30, 60, 90]:
        days = 60
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Website views over time (last N days)
    cursor.execute(f'''
        SELECT DATE(started_at) as date, COUNT(*) as count
        FROM page_views
        WHERE started_at >= datetime('now', '-{days} days')
        GROUP BY DATE(started_at)
        ORDER BY date ASC
    ''')
    views_over_time = cursor.fetchall()
    
    # Views per article (all-time and last 30 days)
    cursor.execute('''
        SELECT a.id, a.title, a.slug,
               COUNT(av.id) as total_views,
               COUNT(CASE WHEN av.started_at >= datetime('now', '-30 days') THEN 1 END) as views_30d
        FROM articles a
        LEFT JOIN article_views av ON a.id = av.article_id
        GROUP BY a.id, a.title, a.slug
        ORDER BY total_views DESC
    ''')
    article_stats = cursor.fetchall()
    
    # Time on site stats
    cursor.execute(f'''
        SELECT 
            AVG(duration_seconds) as avg_duration,
            COUNT(*) as total_views,
            SUM(duration_seconds) as total_time
        FROM page_views
        WHERE duration_seconds IS NOT NULL
        AND started_at >= datetime('now', '-{days} days')
    ''')
    time_stats = cursor.fetchone()
    
    # Time on each article
    cursor.execute('''
        SELECT 
            a.id,
            a.title,
            a.slug,
            COUNT(av.id) as total_views,
            AVG(av.duration_seconds) as avg_duration
        FROM articles a
        LEFT JOIN article_views av ON a.id = av.article_id AND av.duration_seconds IS NOT NULL
        GROUP BY a.id, a.title, a.slug
        HAVING total_views > 0
        ORDER BY total_views DESC
    ''')
    article_time_stats = cursor.fetchall()
    
    conn.close()
    
    # Format data for charts
    views_chart_data = {
        'labels': [row['date'] for row in views_over_time],
        'data': [row['count'] for row in views_over_time]
    }
    
    article_views_data = {
        'labels': [row['title'][:30] + '...' if len(row['title']) > 30 else row['title'] for row in article_stats],
        'data': [row['total_views'] for row in article_stats]
    }
    
    return render_template('admin_analytics.html', 
                         views_chart_data=views_chart_data,
                         article_views_data=article_views_data,
                         article_stats=article_stats,
                         time_stats=time_stats,
                         article_time_stats=article_time_stats,
                         days=days)

if __name__ == '__main__':
    init_db()
    
    # Reload email config after database is initialized
    load_email_config()
    
    # Migrate existing articles to have short_summary if missing
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE articles SET short_summary = ? WHERE short_summary IS NULL OR short_summary = ""', 
                   ('Short summary of the article will go here eventually',))
    conn.commit()
    
    # Seed database with placeholder articles if empty
    cursor.execute('SELECT COUNT(*) as count FROM articles')
    count = cursor.fetchone()['count']
    
    if count == 0:
        seed_articles = [
            {
                'title': 'Finding My Voice: A Journey Through Journalism',
                'author_name': 'Kylee',
                'category': 'Songbird Magazine',
                'published_date': '2024-01-15',
                'cover_image_filename': 'cover_image.png',
                'content_html': '''
                    <h2>Starting Out</h2>
                    <p>When I first began my journey as a <strong>journalist</strong>, I had no idea where it would lead me. The world of storytelling opened up in ways I never imagined.</p>
                    <p>Here are some key lessons I've learned:</p>
                    <ul>
                        <li>Always verify your sources</li>
                        <li>Write with empathy and understanding</li>
                        <li>Never stop learning</li>
                    </ul>
                    <p><em>Journalism is not just about reporting facts—it's about connecting with people and sharing their stories.</em></p>
                    <img src="/static/uploads/placeholder.jpg" alt="Article image" style="max-width: 100%; height: auto; margin: 20px 0;">
                    <p>This journey has been transformative, and I'm excited to share more stories with you.</p>
                '''
            },
            {
                'title': 'The Weight of Words: Reflections on Writing',
                'author_name': 'Kylee',
                'category': 'Angsty Entries',
                'published_date': '2024-02-20',
                'cover_image_filename': 'cover_image.png',
                'content_html': '''
                    <h2>Late Night Thoughts</h2>
                    <p>Sometimes, the words don't come easily. There's a <u>weight</u> to what we write, especially when it comes from a place of vulnerability.</p>
                    <p>I've been thinking a lot about:</p>
                    <ol>
                        <li>How our words impact others</li>
                        <li>The responsibility that comes with storytelling</li>
                        <li>Finding balance between honesty and kindness</li>
                    </ol>
                    <p style="color: #c97a63ff;"><strong>Writing is both a gift and a burden.</strong></p>
                    <p>But it's a burden I'm grateful to carry.</p>
                '''
            },
            {
                'title': 'Quick Tips for Aspiring Journalists',
                'author_name': 'Kylee',
                'category': 'Quick Reads',
                'published_date': '2024-03-10',
                'cover_image_filename': 'cover_image.png',
                'content_html': '''
                    <h2>Five Essential Tips</h2>
                    <p>Here are some <strong>quick tips</strong> for anyone starting their journalism journey:</p>
                    <ol>
                        <li><strong>Read widely:</strong> Expand your horizons beyond your beat</li>
                        <li><strong>Practice daily:</strong> Write something every day, even if it's just a paragraph</li>
                        <li><strong>Build relationships:</strong> Networking is crucial in this field</li>
                        <li><strong>Stay curious:</strong> Ask questions, always</li>
                        <li><strong>Be ethical:</strong> Your integrity is your most valuable asset</li>
                    </ol>
                    <p><em>Remember: Every great journalist started somewhere. Your voice matters.</em></p>
                '''
            }
        ]
        
        for article in seed_articles:
            slug = generate_slug(article['title'])
            cursor.execute('''
                INSERT INTO articles (title, slug, author_name, category, published_date, cover_image_filename, content_html, short_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (article['title'], slug, article['author_name'], article['category'], 
                  article['published_date'], article['cover_image_filename'], article['content_html'], 
                  'Short summary of the article will go here eventually'))
        
        conn.commit()
        print("Database seeded with placeholder articles!")
    
    # Seed about_page with default data if empty
    cursor.execute('SELECT COUNT(*) as count FROM about_page')
    about_count = cursor.fetchone()['count']
    
    if about_count == 0:
        cursor.execute('''
            INSERT INTO about_page (author_name, author_photo_filename, author_bio_text)
            VALUES (?, ?, ?)
        ''', ('Kylee', 'cover_image.png', 
              'Welcome to my blog! I\'m a twenty-something journalist passionate about storytelling, writing, and sharing experiences through words.\n\nThis space is where I explore topics that matter to me, from in-depth features to quick thoughts and everything in between.\n\nThank you for joining me on this journey.'))
        conn.commit()
        print("Database seeded with default about page data!")
    
    conn.close()
    
    # Only run with debug in development
    if __name__ == '__main__':
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
