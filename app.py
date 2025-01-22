    import mysql.connector
    from mysql.connector import Error
    from flask import Flask, render_template, request, redirect, url_for, flash, session
    from functools import wraps
    import hashlib
    import os
    from werkzeug.utils import secure_filename

    app = Flask(__name__)
    app.secret_key = 'your_secret_key_here'

    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    db_config = {
        'host': '6-1sh.h.filess.io',
        'database': 'tokoku_digluckygo',
        'user': 'tokoku_digluckygo',
        'password': '5f59f8e9ac5170f2b1d9ec42397133766b7eb894',
        'port': '3307'
    }

    def get_db_connection():
        try:
            connection = mysql.connector.connect(**db_config)
            if connection.is_connected():
                return connection
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return None

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'error')
                return redirect(url_for('login'))
            
            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return redirect(url_for('login'))
                
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
        if not conn:
            flash('Database connection error', 'error')
            return render_template('index.html', products=[], total_products=0, promos=[])
            
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT COUNT(*) as total FROM products')
        total_products = cursor.fetchone()['total']
        
        cursor.execute('''
            SELECT id, name, CAST(price AS DECIMAL(10,2)) as price, 
                   description, category, image, created_at 
            FROM products 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        products = cursor.fetchall()
        
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
        if not conn:
            flash('Database connection error', 'error')
            return render_template('products.html', products=[], page=1, total_pages=0, total_products=0)
            
        cursor = conn.cursor(dictionary=True)
        
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        sort = request.args.get('sort', 'newest')
        
        per_page = 12
        query = 'SELECT id, name, CAST(price AS DECIMAL(10,2)) as price, description, category, image FROM products WHERE 1=1'
        params = []
        
        if search:
            query += ' AND (name LIKE %s OR description LIKE %s)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term])
        
        if category:
            query += ' AND category = %s'
            params.append(category)
        
        if min_price is not None:
            query += ' AND price >= %s'
            params.append(min_price)
        if max_price is not None:
            query += ' AND price <= %s'
            params.append(max_price)
        
        if sort == 'price_low':
            query += ' ORDER BY price ASC'
        elif sort == 'price_high':
            query += ' ORDER BY price DESC'
        else:
            query += ' ORDER BY created_at DESC'
        
        count_query = f"SELECT COUNT(*) as total FROM ({query}) as filtered_products"
        cursor.execute(count_query, params)
        total_products = cursor.fetchone()['total']
        
        total_pages = (total_products + per_page - 1) // per_page
        
        query += ' LIMIT %s OFFSET %s'
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        products = cursor.fetchall()
        
        conn.close()
        return render_template('products.html',
                             products=products,
                             page=page,
                             total_pages=total_pages,
                             total_products=total_products)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = hashlib.md5(request.form['password'].encode()).hexdigest()

            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('login.html')
                
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', 
                           (username, password))
            user = cursor.fetchone()
            conn.close()

            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['permission'] = user['permission']
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password!', 'error')

        return render_template('login.html')

    @app.route('/loginadm', methods=['GET', 'POST'])
    def loginadm():
        if request.method == 'POST':
            username = request.form['username']
            password = hashlib.md5(request.form['password'].encode()).hexdigest()

            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('loginadmin.html')
                
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', 
                           (username, password))
            user = cursor.fetchone()
            conn.close()

            if user and user['permission'] == 50:
                session['user_id'] = user['id']
                flash('Login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid credentials or insufficient permissions!', 'error')

        return render_template('loginadmin.html')

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

        cursor.execute('SELECT id, name, CAST(price AS DECIMAL(10,2)) as price, description, category, image FROM products')
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
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        
                        cursor.execute('''
                            INSERT INTO products (name, price, description, category, image) 
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (name, price, description, category, filename))
                        conn.commit()
                        flash('Product added successfully!', 'success')
                    else:
                        flash('Invalid file type!', 'error')
                else:
                    flash('No file uploaded!', 'error')

            elif action == 'delete_product':
                product_id = request.form['product_id']
                cursor.execute('SELECT image FROM products WHERE id = %s', (product_id,))
                product = cursor.fetchone()
                if product and product['image']:
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image'])
                    if os.path.exists(image_path):
                        os.remove(image_path)
                
                cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
                conn.commit()
                flash('Product deleted successfully!', 'success')

            elif action == 'add_promo':
                name = request.form['promo_name']
                discount = request.form['promo_discount']
                product_id = request.form['promo_product_id']
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
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('login'))
            
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
        return render_template('user_list.html', users=users, user=current_user)

    @app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
    @admin_required
    def delete_user(user_id):
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('user_list'))
            
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
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('user_list'))
            
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
            
            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('register.html')
                
            cursor = conn.cursor(dictionary=True)
            
            try:
                cursor.execute('''
                    INSERT INTO users (username, email, password, permission) 
                    VALUES (%s, %s, %s, %s)
                ''', (username, email, password, 1))
                
                conn.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
                
            except Error as e:
                conn.rollback()
                flash('Registration failed: ' + str(e), 'error')
                return render_template('register.html')
                
            finally:
                conn.close()
                
        return render_template('register.html')

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


    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    if __name__ == '__main__':
        app.run(debug=True)