from flask import Flask, render_template, request, flash, session, url_for, redirect 
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

def get_db():
    conn = sqlite3.connect('creators.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    return hash_password(password) == password_hash


def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      VARCHAR(50) UNIQUE NOT NULL,
            display_name  VARCHAR(100) NOT NULL,
            email        VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            bio TEXT,
            profile_picture_url TEXT,
            banner_url TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id    BIGINT NOT NULL,
            content       TEXT,
            is_private    BOOLEAN DEFAULT FALSE, -- FALSE = public, TRUE = followers only
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS followers (
            follower_id   BIGINT NOT NULL,
            following_id  BIGINT NOT NULL, -- the creator they follow
            followed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
            PRIMARY KEY (follower_id, following_id),
            FOREIGN KEY (follower_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (following_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            creator_id    BIGINT NOT NULL,
            blocked_id    BIGINT NOT NULL,
            blocked_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
            PRIMARY KEY (creator_id, blocked_id),
            FOREIGN KEY (creator_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (blocked_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            user_id       INTEGER NOT NULL,
            post_id       INTEGER NOT NULL,
            liked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (user_id, post_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS social_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            platform VARCHAR(50) NOT NULL,
            url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    ''')

    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_likes_post ON likes(post_id);''')

    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_likes_liked_at ON likes(liked_at);''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_comments (
            comment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id       BIGINT NOT NULL,
            user_id       BIGINT NOT NULL,
            parent_id     BIGINT NULL,
            content       TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES post_comments(comment_id) ON DELETE SET NULL
        );
    ''')

    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_post_comments_post ON post_comments(post_id);''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_post_comments_created ON post_comments(created_at);''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_post_comments_parent ON post_comments(parent_id);''')

    conn.commit()
    conn.close()   

@app.route('/')
def index():
    return render_template('index.html')
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, password_hash FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        conn.close()

        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['user_id']
            flash('Logged in succesfully', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username and/or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/search', methods=['GET', 'POST'])
def search():
    return render_template('search.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    # FIX: Add profile_picture_url and banner_url to SELECT statement
    cursor.execute("""
        SELECT username, display_name, email, bio, 
               profile_picture_url, banner_url, created_at 
        FROM users WHERE user_id=?
    """, (user_id,))
    user = cursor.fetchone()
    
    # Get social links
    cursor.execute("SELECT platform, url FROM social_links WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    social_links = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', user=user, social_links=social_links)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    display_name = request.form.get('display_name')
    bio = request.form.get('bio')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET display_name = ?, bio = ?
        WHERE user_id = ?
    ''', (display_name, bio, user_id))
    
    conn.commit()
    conn.close()
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_banner', methods=['POST'])
@login_required
def update_banner():
    """Update profile banner by URL"""
    user_id = session['user_id']
    banner_url = request.form.get('banner_url', '').strip()
    
    if not banner_url:
        flash('Please enter a banner URL', 'warning')
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Add column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN banner_url TEXT')
    except sqlite3.OperationalError:
        pass  
    
    cursor.execute('''
        UPDATE users 
        SET banner_url = ?
        WHERE user_id = ?
    ''', (banner_url, user_id))
    
    conn.commit()
    conn.close()
    
    flash('Banner updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/add_social_link', methods=['POST'])
@login_required
def add_social_link():
    """Add a social media link to user's profile"""
    user_id = session['user_id']
    platform = request.form.get('platform', '').strip()
    url = request.form.get('url', '').strip()
    
    if not platform or not url:
        flash('Please fill in both platform and URL', 'warning')
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if link already exists
    cursor.execute('SELECT * FROM social_links WHERE user_id=? AND platform=?', 
                   (user_id, platform))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing link
        cursor.execute('UPDATE social_links SET url=? WHERE user_id=? AND platform=?',
                       (url, user_id, platform))
        message = 'Social link updated!'
    else:
        # Insert new link
        cursor.execute('INSERT INTO social_links (user_id, platform, url) VALUES (?, ?, ?)',
                       (user_id, platform, url))
        message = 'Social link added!'
    
    conn.commit()
    conn.close()
    
    flash(message, 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_profile_picture', methods=['POST'])
@login_required
def update_profile_picture():
    """Update profile picture by URL"""
    user_id = session['user_id']
    profile_picture_url = request.form.get('profile_picture_url', '').strip()
    
    if not profile_picture_url:
        flash('Please enter a photo URL', 'warning')
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Add column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN profile_picture_url TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    cursor.execute('''
        UPDATE users 
        SET profile_picture_url = ?
        WHERE user_id = ?
    ''', (profile_picture_url, user_id))
    
    conn.commit()
    conn.close()
    
    flash('Profile picture updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        display_name = request.form['display_name']
        bio = request.form.get('bio', '')

        #Validation
        if password != confirm_password:
            flash("Passwords do not match",'danger')
            return redirect(url_for('register'))
        if len(password) < 8:
            flash("Password must be at least 8 characters long",'danger')
            return redirect(url_for('register'))
        
        conn = get_db()
        cursor = conn.cursor()
        
        user = cursor.execute('SELECT * FROM users WHERE username=? OR email=?', (username, email)).fetchone()
        if user:
            flash("Username or email already exists",'danger')
            conn.close()
            return redirect(url_for('register'))
        
        #OK, user created
        password_hash = hash_password(password)
        cursor.execute('''
                       INSERT INTO users (username, display_name, email, password_hash, bio) 
                       VALUES (?, ?, ?, ?, ?)
                       ''', (username, display_name, email, password_hash, bio))
        
        conn.commit()
        conn.close()

        flash("Your account has been created, please log in",'success')
        return redirect(url_for('login'))

    return render_template('register.html')
    

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
