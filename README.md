# Twenty-Something Year Old Journalist

A modern, artsy Flask-based blog application for the "Twenty-Something Year Old Journalist" blog.

## Features

- **Modern, Artsy Design**: Clean, readable interface with a creative aesthetic
- **Article Management**: Full CRUD operations for blog articles
- **Rich Text Editor**: Quill.js integration for creating formatted content
- **Image Uploads**: Support for cover images and embedded images in articles
- **Category Organization**: Articles organized into three categories:
  - Songbird Magazine
  - Angsty Entries
  - Quick Reads
- **Responsive Design**: Mobile-friendly layout that works on all devices
- **Admin Dashboard**: Hidden admin interface for content management

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the blog**:
   - Homepage: http://localhost:5000
   - Admin login: Click "Old" on the About page, or go to http://localhost:5000/admin/login
   - Admin password: `kyleekallick2002`

## Project Structure

```
BlogTSYOJ/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── blog.db               # SQLite database (created automatically)
├── templates/            # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── category.html
│   ├── archive.html
│   ├── about.html
│   ├── article.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── admin_new.html
│   └── admin_edit.html
├── static/
│   ├── css/
│   │   └── style.css     # Main stylesheet
│   ├── js/
│   │   └── carousel.js   # Carousel functionality
│   ├── graphics/         # Images and logos
│   └── uploads/          # User-uploaded images (created automatically)
```

## Database

The application uses SQLite and automatically creates the database and schema on first run. Three placeholder articles are seeded automatically if the database is empty.

## Admin Features

### Accessing Admin
1. Navigate to the "About the Author" page
2. Click on the word "Old" in "Twenty-Something Year Old Journalist"
3. Enter the password: `kyleekallick2002`

### Admin Capabilities
- Create new articles with rich text formatting
- Edit existing articles
- Upload cover images and embedded images
- Manage article metadata (title, author, date, category)

## Color Scheme

- **Background**: `#f3eee2ff` (Cream/Beige)
- **Accent 1**: `#c97a63ff` (Burnt Orange/Terracotta)
- **Text/Primary Dark**: `#3c4c5aff` (Dark Blue-Grey)
- **Accent 2**: `#476968ff` (Teal/Dark Green)

## Technologies Used

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Rich Text Editor**: Quill.js (via CDN)
- **Fonts**: Google Fonts (Averia Serif Libre, Pacifico) with Arial fallback

## Development

The application runs in debug mode by default. For production, set `debug=False` in `app.py` and use a production WSGI server like Gunicorn.

## Notes

- All cover images are expected to be square
- Images are stored in `static/uploads/` with timestamped filenames
- The database is automatically initialized on first run
- Session-based authentication is used for admin access

## License

This project is for personal use.

