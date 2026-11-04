"""
HTTP endpoints.

POST /api/v1/images          upload an image (multipart field "file")
GET  /api/v1/images/<id>     download the image

Views stay thin: the serializer validates and saves; the view connects the
request to it and shapes the response. Small class-based views are used so
each endpoint can later declare its own rate-limit scope.
"""

from django.http import FileResponse
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Image
from .serializers import ImageSerializer, ImageUploadSerializer


class ImageUploadView(APIView):
    def post(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save()

        data = ImageSerializer(image, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED, headers={"Location": data["url"]})


class ImageDetailView(APIView):
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