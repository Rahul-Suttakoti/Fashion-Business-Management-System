# create_admin.py
# Usage: python create_admin.py
# It reads DB creds from .env and creates an app user with hashed password + salt.

import os
import binascii, hashlib
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "fashion_business"),
    "port": int(os.getenv("DB_PORT", "3306"))
}

def make_salt():
    return binascii.hexlify(os.urandom(16)).decode()

def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def create_admin(username, password):
    salt = make_salt()
    phash = hash_password(password, salt)
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO app_users (username, role, password_hash, salt) VALUES (%s,%s,%s,%s)",
                    (username, 'admin', phash, salt))
        conn.commit()
        print("Admin user created.")
    except mysql.connector.Error as e:
        print("Error:", e)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    uname = input("Enter admin username (e.g. admin): ").strip()
    pw = input("Enter admin password (min 4 chars): ").strip()
    if len(uname)==0 or len(pw) < 4:
        print("Invalid input.")
    else:
        create_admin(uname, pw)
