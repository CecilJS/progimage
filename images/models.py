import uuid

from django.db import models


def image_upload_path(instance: "Image", filename: str) -> str:
    # The stored filename is derived from our own id and the *detected*
    # format, never from the client's filename.
    return f"images/{instance.id}.{instance.extension}"


class Image(models.Model):
    # A random UUID is unguessable, so nobody can walk through every image
    # by incrementing an id.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=image_upload_path)
    content_type = models.CharField(max_length=50)
    extension = models.CharField(max_length=10)
    size_bytes = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)