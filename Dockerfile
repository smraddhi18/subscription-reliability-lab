FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    RELIABILITY_DB=/data/reliability.db

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py ./manage.py
COPY config ./config
COPY reliability_lab ./reliability_lab
COPY static ./static
RUN mkdir -p /data && useradd --system --uid 10001 appuser && chown -R appuser:appuser /data
USER appuser
EXPOSE 8080
VOLUME ["/data"]
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8080 --noreload"]
