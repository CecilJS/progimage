FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROGIMAGE_MEDIA_ROOT=/app/media

WORKDIR /app

# Install dependencies first so this layer is cached between code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user, so a compromised process isn't root.
RUN useradd --create-home app && mkdir -p /app/media && chown -R app:app /app
USER app

EXPOSE 8000

# Migrations run at start-up to keep this a single command.
# FUTURE: run migrations as a separate release step, not in every container;
# use Postgres instead of SQLite; mount /app/media on a volume (or use S3)
# so images outlive the container; put nginx or a load balancer in front.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn progimage.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 30"]