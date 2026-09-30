"""Password-based demo access with short-lived JWTs and rotating refresh sessions."""
import hashlib
import hmac
import os
import secrets
import time
import jwt
from fastapi import HTTPException

DEMO_USERS = [
    {'username': 'admin', 'name': 'Aditi Sharma', 'role': 'admin', 'password': 'CityTrace@26127'},
    {'username': 'officer', 'name': 'Arjun Mehra', 'role': 'officer', 'password': 'CityTrace@26127'},
    {'username': 'viewer', 'name': 'Nisha Rao', 'role': 'viewer', 'password': 'CityTrace@26127'},
]


def password_hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, maxmem=64*1024*1024).hex()


class Auth:
    def __init__(self, db, demo: bool):
        self.db = db
        self.secret = os.getenv('ANPR_JWT_SECRET') or secrets.token_urlsafe(48)
        self.demo = demo
        with db.transaction():
            db.conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL, failures INTEGER DEFAULT 0, locked_until REAL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL, refresh_hash TEXT NOT NULL, expires REAL NOT NULL, unit TEXT NOT NULL);
            ''')
            if demo:
                for user in DEMO_USERS:
                    if not db.rows('SELECT username FROM users WHERE username=?', (user['username'],)):
                        salt = secrets.token_hex(16)
                        db.conn.execute('INSERT INTO users(username,name,role,salt,password_hash) VALUES (?,?,?,?,?)',
                                        (user['username'], user['name'], user['role'], salt, password_hash(user['password'], salt)))

    def public_user(self, username, unit):
        row = self.db.rows('SELECT username,name,role FROM users WHERE username=?', (username,))
        if not row:
            raise HTTPException(401, 'User not found')
        return {**row[0], 'unit': unit}

    def _tokens(self, username, sid, unit):
        now = int(time.time())
        access = jwt.encode({'sub': username, 'sid': sid, 'typ': 'access', 'iat': now, 'exp': now + 900}, self.secret, algorithm='HS256')
        refresh = jwt.encode({'sub': username, 'sid': sid, 'typ': 'refresh', 'nonce': secrets.token_hex(16), 'iat': now, 'exp': now + 28800}, self.secret, algorithm='HS256')
        self.db.conn.execute('UPDATE sessions SET refresh_hash=?, expires=? WHERE id=?',
                             (hashlib.sha256(refresh.encode()).hexdigest(), now + 28800, sid))
        return {'access_token': access, 'expires_in': 900, 'user': self.public_user(username, unit)}, refresh

    def login(self, username, password, unit):
        error = None
        tokens = None
        with self.db.transaction():
            rows = self.db.rows('SELECT * FROM users WHERE username=?', (username,))
            user = rows[0] if rows else None
            if user and user['locked_until'] > time.time():
                error = HTTPException(429, 'Account locked for five minutes after repeated failed attempts.')
            elif not user or not hmac.compare_digest(password_hash(password, user['salt']), user['password_hash']):
                if user:
                    failures = user['failures'] + 1
                    self.db.conn.execute('UPDATE users SET failures=?,locked_until=? WHERE username=?',
                        (failures, time.time()+300 if failures >= 5 else 0, username))
                error = HTTPException(401, 'Invalid User ID or password.')
            if error:
                self.db.audit('anonymous', 'auth.login_failed', {'user': username, 'unit': unit})
            else:
                self.db.conn.execute('UPDATE users SET failures=0,locked_until=0 WHERE username=?', (username,))
                sid = secrets.token_hex(24)
                self.db.conn.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (sid, username, '', 0, unit))
                self.db.audit(user['role'], 'auth.login', {'user': username, 'unit': unit})
                tokens = self._tokens(username, sid, unit)
        if error:
            raise error
        return tokens

    def decode(self, token, kind='access'):
        try:
            claims = jwt.decode(token, self.secret, algorithms=['HS256'], options={'require': ['sub', 'sid', 'typ', 'exp']})
            if claims['typ'] != kind:
                raise ValueError('Wrong token type')
            rows = self.db.rows('SELECT * FROM sessions WHERE id=? AND username=? AND expires>?', (claims['sid'], claims['sub'], time.time()))
            if not rows:
                raise ValueError('Session expired')
            return claims, rows[0]
        except (jwt.PyJWTError, ValueError, TypeError):
            raise HTTPException(401, 'Session expired. Please sign in again.')

    def authenticate(self, authorization: str):
        if not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Sign in required')
        claims, session = self.decode(authorization[7:])
        return self.public_user(claims['sub'], session['unit'])

    def refresh(self, token):
        with self.db.transaction():
            claims, session = self.decode(token, 'refresh')
            if not hmac.compare_digest(session['refresh_hash'], hashlib.sha256(token.encode()).hexdigest()):
                raise HTTPException(401, 'Refresh token already used')
            return self._tokens(claims['sub'], claims['sid'], session['unit'])

    def logout(self, token):
        try:
            claims, session = self.decode(token, 'refresh')
        except HTTPException:
            return
        with self.db.transaction():
            self.db.conn.execute('DELETE FROM sessions WHERE id=?', (session['id'],))
            self.db.audit('authenticated', 'auth.logout', {'user': claims['sub']})
