from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, is_admin, can_delete):
        self.id = id
        self.username = username
        self.is_admin = is_admin
        self.can_delete = can_delete

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['is_admin'], user['can_delete'])
    return None

def get_db_connection():
    conn = sqlite3.connect('alerts.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories')
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('index.html', categories=categories)

@app.route('/uploads/<filename>')
def serve_image(filename):
    return send_from_directory('uploads', filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            login_user(User(user['id'], user['username'], user['is_admin'], user['can_delete']))
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        if not email:
            flash('El email es obligatorio.')
            return render_template('register.html')
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password, email, is_admin, can_delete) VALUES (?, ?, ?, 0, 0)',
                           (username, generate_password_hash(password), email))
            conn.commit()
            conn.close()
            flash('Registro exitoso. Por favor, inicia sesión.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('El usuario o email ya existe.')
            conn.close()
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/submit_alert', methods=['POST'])
@login_required
def submit_alert():
    photo = request.files.get('photo')
    description = request.form.get('description')
    category_id = request.form.get('category_id')
    latitude = float(request.form.get('latitude'))
    longitude = float(request.form.get('longitude'))
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if photo:
        photo_path = os.path.join('uploads', photo.filename)
        photo.save(photo_path)
    else:
        photo_path = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (photo_path, description, category_id, latitude, longitude, user_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (photo_path, description, category_id, latitude, longitude, current_user.id, timestamp))
    conn.commit()
    
    cursor.execute('SELECT a.*, c.name as category FROM alerts a JOIN categories c ON a.category_id = c.id WHERE a.id = last_insert_rowid()')
    new_alert = dict(cursor.fetchone())
    conn.close()

    return jsonify({'message': 'Alerta registrada con éxito'})

@app.route('/alerts', methods=['GET'])
def get_alerts():
    page = int(request.args.get('page', 1))
    per_page = 5
    category_filter = request.args.get('category', '')
    date_start_filter = request.args.get('date_start', '')
    date_end_filter = request.args.get('date_end', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = 'SELECT a.*, c.name as category FROM alerts a JOIN categories c ON a.category_id = c.id WHERE 1=1'
    params = []
    if category_filter:
        query += ' AND c.name = ?'
        params.append(category_filter)
    if date_start_filter:
        query += ' AND a.timestamp >= ?'
        params.append(date_start_filter + ' 00:00:00')
    if date_end_filter:
        query += ' AND a.timestamp <= ?'
        params.append(date_end_filter + ' 23:59:59')

    cursor.execute(f'SELECT COUNT(*) as total FROM ({query})', params)
    total = cursor.fetchone()['total']

    query += ' ORDER BY a.timestamp DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, params)
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'alerts': alerts, 'total': total, 'page': page, 'per_page': per_page})

@app.route('/categories', methods=['GET'])
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories')
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/safety_ranking', methods=['GET'])
def safety_ranking():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM alerts')
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()

    zones = [
        {"name": "Chiguayante Norte", "lat_min": -36.91, "lat_max": -36.90, "lon_min": -73.04, "lon_max": -73.02, "alerts": 0},
        {"name": "Chiguayante Sur", "lat_min": -36.94, "lat_max": -36.92, "lon_min": -73.04, "lon_max": -73.02, "alerts": 0},
        {"name": "Concepción Centro", "lat_min": -36.83, "lat_max": -36.81, "lon_min": -73.06, "lon_max": -73.04, "alerts": 0}
    ]

    for alert in alerts:
        lat, lon = alert['latitude'], alert['longitude']
        for zone in zones:
            if (zone['lat_min'] <= lat <= zone['lat_max']) and (zone['lon_min'] <= lon <= zone['lon_max']):
                zone['alerts'] += 1

    for zone in zones:
        zone['safety_score'] = max(100 - (zone['alerts'] * 10), 0)

    zones.sort(key=lambda x: x['safety_score'], reverse=True)
    return jsonify(zones)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        flash('Acceso denegado. Solo para administradores.')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete_alert':
            alert_id = request.form.get('alert_id')
            if current_user.can_delete:
                cursor.execute('DELETE FROM alerts WHERE id = ?', (alert_id,))
        elif action == 'update_alert_category':
            alert_id = request.form.get('alert_id')
            category_id = request.form.get('category_id')
            cursor.execute('UPDATE alerts SET category_id = ? WHERE id = ?', (category_id, alert_id))
        elif action == 'delete_user':
            if current_user.username == 'admin':
                user_id = request.form.get('user_id')
                cursor.execute('DELETE FROM users WHERE id = ? AND id != ?', (user_id, current_user.id))
        elif action == 'toggle_delete_permission':
            if current_user.username == 'admin':
                user_id = request.form.get('user_id')
                can_delete = 1 if request.form.get('can_delete') == 'on' else 0
                cursor.execute('UPDATE users SET can_delete = ? WHERE id = ?', (can_delete, user_id))
        elif action == 'add_category':
            category_name = request.form.get('category_name')
            cursor.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
        elif action == 'delete_category':
            category_id = request.form.get('category_id')
            cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()

    cursor.execute('SELECT a.*, c.name as category FROM alerts a JOIN categories c ON a.category_id = c.id')
    alerts = [dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT * FROM users')
    users = [dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT * FROM categories')
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return render_template('admin.html', alerts=alerts, users=users, categories=categories)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)