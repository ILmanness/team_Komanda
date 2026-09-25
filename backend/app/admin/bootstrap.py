"""Create or promote one explicitly named local administrator.

Usage: python -m app.admin.bootstrap --login NAME --email EMAIL --display-name NAME
The password is prompted on a terminal or read from standard input and is never logged.
"""
import argparse
import getpass
import sys

from sqlalchemy import text

from app.auth.security import hash_password
from app.db import engine


def main() -> None:
    parser = argparse.ArgumentParser(description='Create a named admin account')
    parser.add_argument('--login', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--display-name', required=True)
    args = parser.parse_args()
    password = getpass.getpass('Administrator password: ') if sys.stdin.isatty() else sys.stdin.readline().rstrip('\r\n')
    if not password:
        parser.error('Provide a password on standard input')
    login = args.login.lower()
    email = args.email.lower()
    with engine.begin() as connection:
        existing = connection.execute(text('''
            SELECT id, login, email FROM users
            WHERE lower(login)=:login OR lower(email)=:email FOR UPDATE
        '''), {'login': login, 'email': email}).mappings().all()
        if len(existing) > 1 or (existing and (existing[0]['login'] != login or existing[0]['email'] != email)):
            parser.error('The login or email belongs to another account')
        if existing:
            connection.execute(text('''
                UPDATE users SET role='admin', display_name=:display_name,
                  password_hash=:password_hash, updated_at=now() WHERE id=:id
            '''), {'id': existing[0]['id'], 'display_name': args.display_name,
                   'password_hash': hash_password(password)})
        else:
            connection.execute(text('''
                INSERT INTO users(login, email, display_name, password_hash, role)
                VALUES (:login, :email, :display_name, :password_hash, 'admin')
            '''), {'login': login, 'email': email, 'display_name': args.display_name,
                   'password_hash': hash_password(password)})
    print(f'Administrator ready: {login}')


if __name__ == '__main__':
    main()
