"""
HTTP endpoints.

POST /api/v1/images          upload an image (multipart field "file")
GET  /api/v1/images/<id>     download the image

Views stay thin: the serializer validates and saves; the view connects the
request to it and shapes the response. Small class-based views are used so
each endpoint can declare its own rate-limit scope.
"""

from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Image
from .serializers import ImageSerializer, ImageTooLarge, ImageUploadSerializer

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

        # FileResponse streams the file in chunks, so memory use stays
        # flat however large the image is.
        return FileResponse(image.file.open("rb"), content_type=image.content_type)


# FUTURE: GET /api/v1/images/<id>/metadata (dimensions, size, type without
# downloading the bytes) and DELETE /api/v1/images/<id>.
# FUTURE: a custom DRF exception handler so every error uses one format
# with a machine-readable code and request id.