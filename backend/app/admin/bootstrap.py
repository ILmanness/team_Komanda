"""Create or promote one explicitly named local administrator.

Usage: python -m app.admin.bootstrap --login NAME --email EMAIL --display-name NAME
The password is prompted on a terminal or read from standard input and is never logged.
"""
import argparse
import getpass
import os
import sys
import asyncio

from sqlalchemy import text

from app.auth.security import hash_password
from app.db import engine


async def main() -> None:
    parser = argparse.ArgumentParser(description='Create a named admin account')
    parser.add_argument('--login', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--display-name', required=True)
    parser.add_argument('--if-missing', action='store_true',
                        help='Leave an existing matching account and its password unchanged')
    args = parser.parse_args()
    login = args.login.lower()
    email = args.email.lower()
    async with engine.begin() as connection:
        existing = (await connection.execute(text('''
            SELECT id, login, email, role, password_hash IS NOT NULL AS has_password FROM users
            WHERE lower(login)=:login OR lower(email)=:email FOR UPDATE
        '''), {'login': login, 'email': email})).mappings().all()
        if len(existing) > 1 or (existing and (existing[0]['login'] != login or existing[0]['email'] != email)):
            raise SystemExit('The login or email belongs to another account')
        if existing and args.if_missing:
            if existing[0]['role'] != 'admin' or not existing[0]['has_password']:
                raise SystemExit('The matching account is not a usable admin; repair it manually')
            print(f'Administrator already exists: {login}')
            return
        password = (os.environ.get('ADMIN_BOOTSTRAP_PASSWORD') if args.if_missing else None) or (
            getpass.getpass('Administrator password: ')
            if sys.stdin.isatty() else sys.stdin.readline().rstrip('\r\n')
        )
        if not password:
            raise SystemExit('Set ADMIN_BOOTSTRAP_PASSWORD or provide a password on standard input')
        if existing:
            await connection.execute(text('''
                UPDATE users SET role='admin', display_name=:display_name,
                  password_hash=:password_hash, updated_at=now() WHERE id=:id
            '''), {'id': existing[0]['id'], 'display_name': args.display_name,
                   'password_hash': hash_password(password)})
        else:
            await connection.execute(text('''
                INSERT INTO users(login, email, display_name, password_hash, role)
                VALUES (:login, :email, :display_name, :password_hash, 'admin')
            '''), {'login': login, 'email': email, 'display_name': args.display_name,
                   'password_hash': hash_password(password)})
    print(f'Administrator ready: {login}')


if __name__ == '__main__':
    asyncio.run(main())
