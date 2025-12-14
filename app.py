from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import sqlite3
import uuid
import html
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
            content_html TEXT NOT NULL
        )
    ''')
    
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
        
        cursor.execute('''
            INSERT INTO articles (title, slug, author_name, category, published_date, cover_image_filename, content_html)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, slug, author_name, category, published_date, cover_image_filename, content_html))
        
        conn.commit()
        conn.close()
        
        flash('Article created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_new.html')

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
                cover_image_filename = ?, content_html = ?
            WHERE id = ?
        ''', (title, slug, author_name, category, published_date, cover_image_filename, content_html, article_id))
        
        conn.commit()
        conn.close()
        
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
    
    # Seed database with placeholder articles if empty
    conn = get_db()
    cursor = conn.cursor()
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
                INSERT INTO articles (title, slug, author_name, category, published_date, cover_image_filename, content_html)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (article['title'], slug, article['author_name'], article['category'], 
                  article['published_date'], article['cover_image_filename'], article['content_html']))
        
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
    
    app.run(debug=True)
