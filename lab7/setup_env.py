"""Создаёт локальный пароль Jenkins; не перезаписывает существующий .env."""
import os
from pathlib import Path
import secrets

path = Path(__file__).resolve().parent / '.env'
if path.exists():
    print('lab7/.env уже существует; пароль сохранён')
else:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write('JENKINS_ADMIN_USER=admin\nJENKINS_ADMIN_PASSWORD=' + secrets.token_urlsafe(24) + '\n')
    print('Создан lab7/.env (0600); пароль не выводится и не включается в Git')
