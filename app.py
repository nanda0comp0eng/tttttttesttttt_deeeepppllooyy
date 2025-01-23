import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import hashlib
import os
import time
import urllib.parse
from werkzeug.utils import secure_filename
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Database Configuration
db_config = {
    'host': '6-1sh.h.filess.io',
    'database': 'tokoku_digluckygo',
    'user': 'tokoku_digluckygo',
    'password': '5f59f8e9ac5170f2b1d9ec42397133766b7eb894',
    'port': '3307'
}

# File Upload Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'static/uploads'
PROFILE_UPLOAD_FOLDER = 'static/uploads/user'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    """Connect to the database and return the connection."""
    return mysql.connector.connect(**db_config)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_resolution(image_path, min_width, min_height):
    """Check image resolution."""
    with Image.open(image_path) as img:
        width, height = img.size
        return width >= min_width and height >= min_height

def admin_required(f):
    """Decorator to restrict access to admin users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        conn.close()

        if not user or user['permission'] != 50:
            flash('Access Denied. Admin privileges required.', 'error')
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total number of products
    cursor.execute('SELECT COUNT(*) as total FROM products')
    total_products = cursor.fetchone()['total']
    
    # Get latest 10 products with price cast to float
    cursor.execute('''
        SELECT 
            id, 
            name, 
            CAST(REPLACE(REPLACE(price, 'Rp', ''), '.', '') AS FLOAT) as price, 
            description, 
            category, 
            image, 
            created_at 
        FROM products 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    products = cursor.fetchall()
    
    # Get promo data with fallback for missing product images
    cursor.execute('''
        SELECT 
            promos.name AS promo_name, 
            promos.discount, 
            products.name AS product_name, 
            COALESCE(products.image, 'default_promo.png') AS product_image
        FROM promos
        LEFT JOIN products ON promos.product_id = products.id
    ''')
    promos = cursor.fetchall()
    
    conn.close()
    return render_template('index.html', products=products, total_products=total_products, promos=promos)

@app.route('/products')
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'newest')
    
    per_page = 12  # Products per page
    
    # Base query with price cast to float
    query = '''
        SELECT 
            id, 
            name, 
            CAST(REPLACE(REPLACE(price, 'Rp', ''), '.', '') AS FLOAT) as price, 
            description, 
            category, 
            image, 
            created_at 
        FROM products 
        WHERE 1=1
    '''
    params = []
    
    # Add search condition
    if search:
        query += ' AND (name LIKE %s OR description LIKE %s)'
        search_term = f'%{search}%'
        params.extend([search_term, search_term])
    
    # Add category filter
    if category:
        query += ' AND category = %s'
        params.append(category)
    
    # Add price range filter
    if min_price is not None:
        query += ' AND price >= %s'
        params.append(min_price)
    if max_price is not None:
        query += ' AND price <= %s'
        params.append(max_price)
    
    # Add sorting
    if sort == 'price_low':
        query += ' ORDER BY price ASC'
    elif sort == 'price_high':
        query += ' ORDER BY price DESC'
    else:  # newest
        query += ' ORDER BY created_at DESC'
    
    # Count total products
    count_query = f"SELECT COUNT(*) as total FROM ({query}) as filtered_products"
    cursor.execute(count_query, params)
    total_products = cursor.fetchone()['total']
    
    # Calculate total pages
    total_pages = (total_products + per_page - 1) // per_page
    
    # Add pagination
    query += ' LIMIT %s OFFSET %s'
    offset = (page - 1) * per_page
    params.extend([per_page, offset])
    
    # Execute final query
    cursor.execute(query, params)
    products = cursor.fetchall()
    
    # Calculate page range
    page_range_start = max(1, page - 2)
    page_range_end = min(total_pages + 1, page + 3)
    
    conn.close()
    
    return render_template('products.html',
                         products=products,
                         page=page,
                         total_pages=total_pages,
                         total_products=total_products,
                         page_range_start=page_range_start,
                         page_range_end=page_range_end)
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT username FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        cursor.execute('''
            SELECT 
                id, 
                name, 
                CAST(REPLACE(REPLACE(price, 'Rp', ''), '.', '') AS FLOAT) as price, 
                description, 
                category, 
                image 
            FROM products
        ''')
        products = cursor.fetchall()
        cursor.execute('''
            SELECT promos.id, promos.name AS promo_name, promos.discount, 
                   products.name AS product_name, products.image AS product_image
            FROM promos
            LEFT JOIN products ON promos.product_id = products.id
        ''')
        promos = cursor.fetchall()
        if request.method == 'POST':
            action = request.form['action']
            if action == 'add_product':
                name = request.form['product_name']
                price = request.form['product_price'].replace('Rp', '').replace(',', '').replace('.', '')[:-3]
                description = request.form['product_description']
                category = request.form['product_category']
                
                # Handle image upload
                image_file = request.files['product_image']
                if image_file and allowed_file(image_file.filename):
                    filename = f"{int(time.time())}_{secure_filename(image_file.filename)}"
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image_file.save(image_path)
                    
                    # Check image resolution
                    if check_resolution(image_path, 400, 300):
                        image_url = f"/uploads/{filename}"
                        cursor.execute('''
                            INSERT INTO products (name, price, description, category, image) 
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (name, price, description, category, image_url))
                        conn.commit()
                        flash('Product added successfully!', 'success')
                    else:
                        os.remove(image_path)
                        flash('Image dimensions must be at least 400x300 pixels.', 'error')
                else:
                    flash('No file uploaded or invalid file type.', 'error')
        return render_template('admin_dashboard.html', user=user, products=products, promos=promos)
    except Exception as e:
        flash('An error occurred while processing your request.', 'error')
        app.logger.error(f'Error in admin_dashboard: {e}')
        return redirect(url_for('login'))
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def user_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT username FROM users WHERE id = %s', (session['user_id'],))
    current_user = cursor.fetchone()
    
    if request.method == 'POST':
        action = request.form['action']
        if action == 'add_user':
            username = request.form['username']
            password = hashlib.md5(request.form['password'].encode()).hexdigest()
            permission = int(request.form['permission'])
            cursor.execute('INSERT INTO users (username, password, permission) VALUES (%s, %s, %s)', 
                           (username, password, permission))
            conn.commit()
            flash('User added successfully!', 'success')
        elif action == 'update_user':
            user_id = request.form['user_id']
            username = request.form['username']
            permission = int(request.form['permission'])
            cursor.execute('UPDATE users SET username = %s, permission = %s WHERE id = %s', 
                           (username, permission, user_id))
            conn.commit()
            flash('User updated successfully!', 'success')

    cursor.execute('SELECT id, username, permission FROM users')
    users = cursor.fetchall()
    conn.close()
    return render_template('user_list.html', users=users, user=current_user)  # Add user=current_user here

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('user_list'))

@app.route('/admin/users/update', methods=['POST'])
@admin_required
def update_user():
    user_id = request.form['user_id']
    username = request.form['username']
    permission = int(request.form['permission'])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET username = %s, permission = %s WHERE id = %s', 
                   (username, permission, user_id))
    conn.commit()
    conn.close()
    flash('User updated successfully!', 'success')
    return redirect(url_for('user_list'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if username already exists
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            conn.close()
            flash('Username already exists!', 'error')
            return render_template('register.html')
        
        # Check if email already exists
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        if cursor.fetchone():
            conn.close()
            flash('Email already registered!', 'error')
            return render_template('register.html')
        
        try:
            # Insert new user
            cursor.execute('''
                INSERT INTO users (username, email, password, permission) 
                VALUES (%s, %s, %s, %s)
            ''', (username, email, password, 1))  # permission 1 for regular users
            
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Error as e:
            flash('An error occurred during registration.', 'error')
            print(f"Database error: {e}")
            return render_template('register.html')
            
        finally:
            conn.close()
            
    # If GET request, just show the registration form
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', 
                       (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['permission'] = user['permission']  # Save permission level in session
            flash('Login berhasil!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profil():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT username, email FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('index'))

    # Use the predefined PROFILE_UPLOAD_FOLDER from your configuration
    default_picture = 'static/default_picture.png'
    profile_picture_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], f"{user['username']}.png")

    return render_template('profile.html', 
                           user=user, 
                           profile_picture=default_picture)

# Pesan
@app.route('/order', methods=['GET', 'POST'])
def order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT id, name, CAST(price AS FLOAT) as price, description, category, image FROM products')
    products = cursor.fetchall()
    conn.close()

    # Initialize cart if not exists
    if 'order' not in session:
        session['order'] = []

    if request.method == 'POST':
        action = request.form['action']

        if action == 'add_to_cart':
            product_id = request.form['product_id']
            quantity = int(request.form['quantity'])

            # Get product details from database
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT id, name, CAST(price AS FLOAT) as price, image FROM products WHERE id = %s', (product_id,))
            product = cursor.fetchone()
            conn.close()

            # Add product to cart
            if product:
                item = {
                    'product_id': product['id'],
                    'name': product['name'],
                    'price': product['price'],
                    'quantity': quantity,
                    'image': product['image']
                }
                session['order'].append(item)
                flash(f'Added {product["name"]} to cart', 'success')

        elif action == 'remove_from_cart':
            product_id = request.form['product_id']
            session['order'] = [item for item in session['order'] if item['product_id'] != int(product_id)]
            flash('Item removed from cart', 'success')

        elif action == 'checkout':
            # Calculate total price
            total_price = sum(item['price'] * item['quantity'] for item in session['order'])
            flash(f'Total price: Rp {total_price}', 'success')
            session['order'] = []  # Clear cart after checkout

    return render_template('order.html', products=products)

if __name__ == '__main__':
    app.run(debug=True)