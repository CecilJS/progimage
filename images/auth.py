"""
API-key authentication for calling services.

ProgImage is used by other applications, not browsers, so a static key per
client in the `X-API-Key` header is a pragmatic start. It plugs into DRF's
authentication chain, so moving to JWT or mTLS later means swapping this
class, not touching the views.

FUTURE: store keys hashed in the database, with names, scopes and rotation,
instead of reading them from an environment variable.
"""

import hashlib
import hmac
from dataclasses import dataclass

from django.conf import settings
from rest_framework import authentication, exceptions


@dataclass(frozen=True)
class APIClient:
    """Stands in for request.user. `pk` is a short fingerprint of the key:
    safe to log, and used by DRF to key each client's rate limits."""

    pk: str
    is_authenticated: bool = True


class APIKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        provided = request.headers.get("X-API-Key")
        if not provided:
            return None  # no credentials: IsAuthenticated then returns 401

        for key in settings.PROGIMAGE_API_KEYS:
            # Constant-time comparison, so response timing can't leak how
            # much of a guessed key was correct.
            if hmac.compare_digest(provided.encode(), key.encode()):
                fingerprint = hashlib.sha256(key.encode()).hexdigest()[:12]
                return APIClient(pk=fingerprint), None
        raise exceptions.AuthenticationFailed("Invalid API key.")

    def authenticate_header(self, request):
        # Makes DRF answer 401 (not 403) and tells the caller what's expected.
        return "X-API-Key"
