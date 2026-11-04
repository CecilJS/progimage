"""
Serializers: input validation for uploads, output shape for responses.

We never trust what the client says a file is. DRF's
ImageField ignores the filename and Content-Type header and opens the
bytes with Pillow, rejecting anything that isn't a real, intact image.
We add the checks that are specific to this service on top.
"""
from django.conf import settings
from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .models import Image

# Allow-list of raster formats. Pillow can read others (BMP, TIFF...) but we
# only accept what we intend to support. SVG never passes ImageField (Pillow
# can't read it), which is what we want: this is a security risk as SVG can carry <script>.
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "GIF": ("image/gif", "gif"),
    "WEBP": ("image/webp", "webp"),
}

# Custom exceptions let us return precise status codes instead of a generic
# 400, so callers know whether to shrink the file or convert it.
class ImageTooLarge(APIException):
    status_code = 413
    default_detail = "Image too large."
    default_code = "image_too_large"


class UnsupportedImageFormat(APIException):
    status_code = 415
    default_detail = "Image format not supported."
    default_code = "unsupported_image_format"


class ImageUploadSerializer(serializers.Serializer):
    # ImageField does the heavy lifting: it opens the file with Pillow and
    # runs verify(), so non-images, empty files and corrupt/truncated images
    # are rejected with 400 before our own code runs. It also attaches the
    # opened image as `file.image`, which we use below.
    file = serializers.ImageField()

    def validate_file(self, upload):
        if upload.size > settings.PROGIMAGE_MAX_UPLOAD_BYTES:
            raise ImageTooLarge(
                f"File is {upload.size} bytes; the limit is "
                f"{settings.PROGIMAGE_MAX_UPLOAD_BYTES} bytes."
            )

         # The view already rejects on Content-Length before the body is read;
         # this is the exact check on the file itself.

        if upload.image.format not in ALLOWED_FORMATS:
            raise UnsupportedImageFormat(
                f"Format {upload.image.format} is not accepted. "
                f"Allowed: {', '.join(ALLOWED_FORMATS)}."
            )

        # Guards against "decompression bombs"
        width, height = upload.image.size
        if width * height > settings.PROGIMAGE_MAX_PIXELS:
            raise ImageTooLarge(f"Image is {width}x{height}; that is too many pixels.")

        # FUTURE: strip EXIF metadata (it can contain GPS location) if images
        # are ever served publicly, and malware-scan untrusted uploads.
        return upload

    def create(self, validated_data):
        upload = validated_data["file"]
        content_type, extension = ALLOWED_FORMATS[upload.image.format]
        width, height = upload.image.size
        image = Image(
            content_type=content_type,
            extension=extension,
            size_bytes=upload.size,
            width=width,
            height=height,
        )
        # Writes the bytes through the configured storage backend, then the row.
        # FUTURE: catch storage errors and return 503, rather than a generic 500.
        image.file.save(upload.name, upload, save=True)
        return image


class ImageSerializer(serializers.ModelSerializer):
    """Public shape of an image. Decoupled from the model so internal
    fields (like the storage path) are never exposed."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ["id", "url", "content_type", "size_bytes", "width", "height", "created_at"]

    def get_url(self, image) -> str:
        return self.context["request"].build_absolute_uri(
            reverse("image-detail", args=[image.id])
        )