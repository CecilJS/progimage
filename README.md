# ProgImage

A small Django REST framework service that stores images and returns them by id.
It's API-only, and intended to be called by other applications.

## Run it

Requires Python 3.14 (3.12 or later works) and, optionally, Docker.

```bash
# Locally
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=true PROGIMAGE_API_KEYS=dev-key
python manage.py migrate
python manage.py runserver          # listens on 127.0.0.1:8000 only

# Or in Docker (published on localhost only, not the local network)
docker build -t progimage .
docker run -p 127.0.0.1:8000:8000 -e PROGIMAGE_API_KEYS=dev-key -e DJANGO_SECRET_KEY=change-me progimage

# Tests, linting and formatting
pip install -r requirements-dev.txt
python manage.py test       
ruff format .              
ruff check .                  
```

## API

Every request needs an `X-API-Key` header. If no keys are configured, all
requests are refused: the service fails closed.

```bash
# Upload -> 201 {"id": "...", "url": "...", "content_type": "image/png", "sha256": "...", ...}
curl -H "X-API-Key: dev-key" -F file=@cat.png http://localhost:8000/api/v1/images

# Retrieve
curl -H "X-API-Key: dev-key" -o out.png http://localhost:8000/api/v1/images/<id>

# Conditional retrieve -> 304 Not Modified if you already have it
curl -H "X-API-Key: dev-key" -H 'If-None-Match: "<sha256>"' http://localhost:8000/api/v1/images/<id>
```

Errors are JSON in DRF's standard shapes: `{"detail": "..."}`, or
`{"file": ["..."]}` for field validation errors.

| Status | Meaning |
|--------|---------|
| 304 | Not modified: your cached copy (by ETag) is current |
| 400 | No file, empty file, not an image, or corrupt/truncated |
| 401 | Missing or invalid API key |
| 404 | No image with that id, or its stored file is missing |
| 405 | Wrong HTTP method |
| 413 | Too many bytes, or too many pixels |
| 415 | A real image, but not JPEG, PNG, GIF or WebP |
| 429 | Rate limit hit (see `Retry-After`) |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROGIMAGE_API_KEYS` | *(none: all requests refused)* | Comma-separated client keys |
| `DJANGO_SECRET_KEY` | *(required unless `DJANGO_DEBUG=true`)* | Django's signing key |
| `DJANGO_DEBUG` | `false` | Local development only |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Hostnames to serve |
| `PROGIMAGE_MAX_UPLOAD_BYTES` | 10 MB | Largest accepted file |
| `PROGIMAGE_MAX_PIXELS` | 40,000,000 | Largest accepted width × height |
| `PROGIMAGE_UPLOAD_RATE` | `30/min` | Uploads per client |
| `PROGIMAGE_READ_RATE` | `600/min` | Reads per client |

## Code layout

```
progimage/settings.py   configuration (env-driven), DRF settings, limits
images/auth.py          API-key authentication
images/models.py        Image metadata; bytes live in storage, not the DB
images/serializers.py   upload validation, hashing, response shape
images/views.py         two thin views: upload, and retrieve with ETag/304
images/tests.py         API tests, including failure paths
Dockerfile              container image (non-root, gunicorn)
```

## Design decisions

I kept this deliberately small and focused on getting the core right:

- **Let the framework do the work.** DRF's `ImageField` opens every upload
  with Pillow and verifies it, so non-images and corrupt files are rejected
  before any of my code runs. DRF also provides authentication hooks,
  rate limiting, JSON errors and 404 handling.
- **Never trust the client.** The format is detected from the bytes; the
  filename and Content-Type header are ignored. The stored filename is built
  from our own id, so a client can't influence the storage path.
- **Fail closed.** API keys are compared in constant time; with no keys
  configured every request is refused, and outside debug mode the service
  won't start without a real secret key.
- **Protect resources, cheapest check first.** Oversized requests are
  rejected from the Content-Length header before the body is parsed. Then
  comes the exact file size, a format allow-list, and a pixel limit that
  stops decompression bombs.
- **Separate rate limits.** Uploads (verify, hash, write) cost far more than
  reads, so they get a much tighter per-client budget.
- **Cache aggressively.** An id always maps to the same bytes, so the SHA-256
  is a perfect ETag. Responses are cacheable for a year, and revalidation
  costs an empty 304. With a CDN in front, most reads never reach Django.
- **Constant memory.** Uploads over 2 MB spill to disk, hashing reads in
  64 KB chunks, and downloads stream.
- **Storage is swappable.** All file access goes through Django's storage
  API, so moving to S3 is a settings change (django-storages), not a rewrite.
- **Unguessable UUID ids**, so images can't be enumerated.

## Trade-offs

| Chose | Over | Because | Would revisit when |
|-------|------|---------|--------------------|
| API keys from an environment variable | JWTs from an identity provider | Callers are a few trusted services; no identity provider in scope | An identity provider exists, or keys need expiry and scopes |
| SQLite | Postgres | Zero setup; only small metadata rows are stored | Running in production or on more than one instance |
| Local disk, via Django's storage API | S3 from the start | Simplest to run; switching is a settings change | Deploying to more than one server |
| Storing originals byte-for-byte | Re-encoding uploads | Exact round trip and cheap uploads | Images are served publicly (EXIF can contain GPS location) |
| No update or list endpoints | Full CRUD | Immutable images make caching safe; listing needs ownership first | Multi-tenancy is added |
| No gzip compression | Compressing responses | Image formats are already compressed; text compression belongs at the CDN or proxy | Not planned |
| Synchronous WSGI with gunicorn | ASGI | DRF and this workload are synchronous and short-lived | Long-lived connections or slow upstream calls appear |
| Validating uploads during the request | Background processing | Immediate, precise errors, and simple | Upload volume or file sizes grow |
| Two `APIView` classes | A DRF `ModelViewSet` | Custom behaviour: byte streaming, ETags, early size checks | A plain JSON CRUD resource is added |

## Known limitations

- Rate-limit counters live in each gunicorn worker's memory, so limits are
  effectively per worker until a shared Redis cache is configured.
- Errors raised by Django itself, such as a malformed id in the URL, return
  HTML rather than JSON.
- Downloads don't check who uploaded an image: any valid key that knows an
  id can fetch it.
- Images above Pillow's own limit (about 179 million pixels) get a generic
  400 rather than 413.
- Only local-disk "file missing" errors map to 404; other storage backends'
  errors would surface as 500.
- Settings recognise `manage.py test` from the command line to allow a
  throwaway secret key; a dedicated test settings module would be cleaner.
- Migrations run on every container start.

## With more time

Places in the code that would change are marked with `FUTURE:` comments.
In rough priority order:

1. **Redis-backed rate limits**, so limits hold across workers and instances.
2. **Production infrastructure**: Postgres with connection pooling, S3
   storage, nginx with a body-size cap, migrations as a release step, and a
   docker-compose file.
3. **One error format** (RFC 9457) via a custom DRF exception handler, with
   request ids, including for Django's own 404 and 500 pages.
4. **Resilience**: 503 when storage is unreachable, and a health check endpoint.
5. **Better key management**: keys stored hashed in the database, with names,
   scopes and rotation, or JWTs from an identity provider.
6. **Ownership**: record who uploaded each image and check it on download,
   which also makes a safe list endpoint possible.
7. **Deduplication** using the stored hash, with reference counting before deletion.
8. **Features**: metadata endpoint, delete, EXIF stripping, resizing/thumbnails.
9. **Scale**: a CDN in front, and presigned direct-to-S3 uploads for large files.