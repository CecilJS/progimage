"""
HTTP endpoints.

POST /api/v1/images          upload an image (multipart field "file")
GET  /api/v1/images/<id>     download the image

Views stay thin: the serializer validates and saves; the view connects the
request to it and shapes the response. Small class-based views are used so
each endpoint can declare its own rate-limit scope.
"""

import logging

from django.conf import settings
from django.http import FileResponse, HttpResponseNotModified
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Image
from .serializers import ImageSerializer, ImageTooLarge, ImageUploadSerializer

logger = logging.getLogger(__name__)

# Multipart framing (boundaries, part headers) adds a little on top of the
# file itself, so allow some slack when judging Content-Length.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


class ImageUploadView(APIView):
    throttle_scope = "uploads"

    def post(self, request):

        # Reject on the declared size *before* touching request.data.
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
        if declared > settings.PROGIMAGE_MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES:
            raise ImageTooLarge(
                f"Request is {declared} bytes; the limit is "
                f"{settings.PROGIMAGE_MAX_UPLOAD_BYTES} bytes."
            )
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save()

        data = ImageSerializer(image, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED, headers={"Location": data["url"]})


class ImageDetailView(APIView):
    throttle_scope = "reads"

    def get(self, request, image_id):
        # DRF turns a missing row into a JSON 404 automatically.
        image = get_object_or_404(Image, pk=image_id)

        # An id always points at the same bytes, so the content hash is a
        # perfect ETag and the response can be cached forever.
        etag = f'"{image.sha256}"'
        cache_headers = {
            "ETag": etag,
            "Cache-Control": "public, max-age=31536000, immutable",
        }

        # The client (or a CDN) already has this exact image: answer with an
        # empty 304 instead of re-sending the bytes.
        if etag_matches(request.headers.get("If-None-Match", ""), etag):
            response = HttpResponseNotModified()
        else:
            try:
                stream = image.file.open("rb")
            except FileNotFoundError:
                # The row exists but its bytes don't: an integrity problem worth
                # alerting on, but the client should get a clean 404, not a 500.
                # FUTURE: other storage backends (e.g. S3) raise their own errors;
                # map those too, and return 503 when storage is unreachable.
                logger.error("Stored file missing for image %s", image.id)
                raise NotFound("Image not found.") from None

            # FileResponse streams the file in chunks, so memory use stays
            # flat however large the image is.
            response = FileResponse(stream, content_type=image.content_type)

        for name, value in cache_headers.items():
            response[name] = value
        return response


def etag_matches(if_none_match: str, etag: str) -> bool:
    """True if any tag in an If-None-Match header matches (or it is "*")."""
    if if_none_match.strip() == "*":
        return True
    tags = {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
    return etag in tags


# FUTURE: GET /api/v1/images/<id>/metadata (dimensions, size, type without
# downloading the bytes) and DELETE /api/v1/images/<id>.
# FUTURE: a custom DRF exception handler so every error uses one format
# with a machine-readable code and request id.
