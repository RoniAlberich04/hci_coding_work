from flask import Flask, render_template, request, flash, session, url_for 
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

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      VARCHAR(50) UNIQUE NOT NULL,
            display_name  VARCHAR(100),
            email        VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
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
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form['full_name']
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
        
        user = cursor.execute('SELECT * FROM users WHERE username==? OR email==?', (username, email)).fetchone
        if user:
            flash("Username or email already exists",'danger')
            conn.close()
            return redirect(url_for('register'))
        
        #OK, user created
        password_hash = hash_password(password)
        cursor.execute('''INSERT INTO users (username, full_name, email, password_hash, bio) 
                       VALUES (?, ?, ?, ?, ?)
                       '''(username, full_name, email, password_hash, bio))
        
        flash("Your account has been created, please log in",'success')
        redirect(url_for('login'))


        conn.commit()
        conn.close()

        return render_template('register.html')

if __name__ == '__main__':
init_db()
app.run(debug=True)