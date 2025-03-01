import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime

conn = sqlite3.connect('alerts.db')
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS alerts')
cursor.execute('DROP TABLE IF EXISTS users')
cursor.execute('DROP TABLE IF EXISTS categories')

cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        is_admin INTEGER DEFAULT 0,
        can_delete INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
''')

cursor.execute('''
    CREATE TABLE alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_path TEXT,
        description TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        user_id INTEGER,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
''')

cursor.execute('INSERT OR IGNORE INTO users (username, password, email, is_admin, can_delete) VALUES (?, ?, ?, ?, ?)',
               ('admin', generate_password_hash('admin123'), 'admin@example.com', 1, 1))
cursor.execute('INSERT OR IGNORE INTO users (username, password, email, is_admin, can_delete) VALUES (?, ?, ?, ?, ?)',
               ('user1', generate_password_hash('user123'), 'user1@example.com', 0, 0))

cursor.executemany('INSERT INTO categories (name) VALUES (?)',
                   [('Infraestructura',), ('Medio Ambiente',), ('Seguridad',)])

cursor.executemany('''
    INSERT INTO alerts (photo_path, description, category_id, latitude, longitude, user_id, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', [
    ('uploads/bache.jpg', 'Bache en Av. Colón', 1, -36.8270, -73.0503, 1, '2025-02-27 10:00:00'),
    ('uploads/basura.jpg', 'Basura en Chiguayante', 2, -36.9256, -73.0284, 2, '2025-02-28 15:30:00'),
])

conn.commit()
conn.close()

print("Base de datos actualizada con usuarios, categorías y alertas.")