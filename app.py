import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import hashlib
import os
import time
import urllib.parse
from werkzeug.utils import secure_filename
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
    
    # Get promo data
    cursor.execute('''
        SELECT 
            promos.name AS promo_name, 
            promos.discount, 
            products.name AS product_name, 
            products.image AS product_image
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
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('login'))
        
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
            
            if 'product_image' in request.files:
                file = request.files['product_image']
                if file and allowed_file(file.filename):
                    # Use a unique filename
                    filename = f"{int(time.time())}_{secure_filename(file.filename)}"
                    
                    # Save to a storage service or generate a placeholder URL
                    image_url = f"https://via.placeholder.com/400x300.png?text={urllib.parse.quote(name)}"
                    
                    cursor.execute('''
                        INSERT INTO products (name, price, description, category, image) 
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (name, price, description, category, image_url))
                    conn.commit()
                    flash('Product added successfully!', 'success')
                else:
                    flash('Invalid file type!', 'error')
            else:
                flash('No file uploaded!', 'error')

        elif action == 'delete_product':
            product_id = request.form['product_id']
            
            # Get the image filename before deleting the product
            cursor.execute('SELECT image FROM products WHERE id = %s', (product_id,))
            product = cursor.fetchone()
            if product and product['image']:
                # Delete the image file
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image'])
                if os.path.exists(image_path):
                    os.remove(image_path)
            
            cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
            conn.commit()
            flash('Product deleted successfully!', 'success')

        elif action == 'add_promo':
            name = request.form['promo_name']
            discount = request.form['promo_discount']
            product_id = request.form['promo_product_id']  # Get selected product ID
            cursor.execute(
                'INSERT INTO promos (name, discount, product_id) VALUES (%s, %s, %s)', 
                (name, discount, product_id)
            )
            conn.commit()
            flash('Promo added successfully!', 'success')

        elif action == 'delete_promo':
            promo_id = request.form['promo_id']
            cursor.execute('DELETE FROM promos WHERE id = %s', (promo_id,))
            conn.commit()
            flash('Promo deleted successfully!', 'success')
    conn.close()
    return render_template('admin_dashboard.html', user=user, products=products, promos=promos)


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

    # Direktori penyimpanan untuk file
    profile_dir = os.path.join(app.root_path, 'static/uploads/user')
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    profile_picture_path = os.path.join(profile_dir, f"{user['username']}.png")
    default_picture_path = os.path.join(app.root_path, 'static', 'default_picture.png')

    # Jika tidak ada file profil, gunakan default gambar
    if not os.path.exists(profile_picture_path):
        profile_picture_path = default_picture_path

    if request.method == 'POST':
        # Periksa apakah file diunggah
        if 'profile_picture' not in request.files or request.files['profile_picture'].filename == '':
            flash('No file uploaded.', 'error')
            return redirect(url_for('profil'))

        file = request.files['profile_picture']

        # Validasi file (hanya PNG diperbolehkan)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            temp_file_path = os.path.join(profile_dir, filename)
            file.save(temp_file_path)

            # Periksa resolusi gambar
            if not check_resolution(temp_file_path, 300, 300):
                os.remove(temp_file_path)
                flash('Image resolution must be at least 300x300 pixels!', 'error')
                return redirect(url_for('profil'))

            # Hapus file profil lama jika ada
            if os.path.exists(profile_picture_path) and profile_picture_path != default_picture_path:
                os.remove(profile_picture_path)

            # Pindahkan file ke path sesuai username
            new_profile_picture_path = os.path.join(profile_dir, f"{user['username']}.png")
            os.rename(temp_file_path, new_profile_picture_path)
            flash('Profile picture updated successfully!', 'success')
        else:
            flash('Invalid file type! Only PNG files are allowed.', 'error')

    # URL untuk gambar profil (frontend)
    profile_picture_url = (
        url_for('static', filename=f"uploads/user/{user['username']}.png")
        if os.path.exists(os.path.join(profile_dir, f"{user['username']}.png"))
        else url_for('static', filename='default_picture.png')
    )

    return render_template('profile.html', user=user, profile_picture=profile_picture_url)

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