"""
HTTP endpoints.

POST /api/v1/images
uploads an image (multipart field "file")

Views stay thin: the serializer validates and saves; the view connects the
request to it and shapes the response. I have used small class-based view so that
each endpoint can later declare its own rate-limit scope.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ImageSerializer, ImageUploadSerializer


class ImageUploadView(APIView):
    def post(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save()

        data = ImageSerializer(image, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)
