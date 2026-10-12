#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 manage.py migrate --noinput
exec python3 manage.py runserver 127.0.0.1:8080
