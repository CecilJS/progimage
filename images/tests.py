"""
API tests. Run with:  python manage.py test

They exercise the endpoints through HTTP, using real images generated with
Pillow, and cover the failure paths as well as the happy path - failure
paths are where services usually break.
"""

import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image as PILImage
from rest_framework.test import APITestCase

from .models import Image

TEMP_MEDIA = tempfile.mkdtemp()


def make_image(fmt="PNG", size=(40, 30)) -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", size, (200, 30, 30)).save(buf, format=fmt)
    return buf.getvalue()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class APITestBase(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def upload(self, data: bytes, name="photo.png", content_type="image/png"):
        file = SimpleUploadedFile(name, data, content_type=content_type)
        return self.client.post("/api/v1/images", {"file": file}, format="multipart")

    def upload_and_get_id(self, data: bytes) -> str:
        resp = self.upload(data)
        self.assertEqual(resp.status_code, 201)
        return resp.json()["id"]


class UploadTests(APITestBase):
    def test_upload_returns_id_and_metadata(self):
        resp = self.upload(make_image("PNG", (40, 30)))

        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["content_type"], "image/png")
        self.assertEqual((body["width"], body["height"]), (40, 30))
        self.assertTrue(Image.objects.filter(pk=body["id"]).exists())

    def test_all_supported_formats(self):
        for fmt, mime in [("PNG", "image/png"), ("JPEG", "image/jpeg"),
                          ("GIF", "image/gif"), ("WEBP", "image/webp")]:
            with self.subTest(fmt=fmt):
                resp = self.upload(make_image(fmt))
                self.assertEqual(resp.status_code, 201)
                self.assertEqual(resp.json()["content_type"], mime)

    def test_type_is_detected_from_bytes_not_trusted_from_client(self):
        # A PNG pretending to be a JPEG is stored as what it really is.
        resp = self.upload(make_image("PNG"), name="lies.jpg", content_type="image/jpeg")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["content_type"], "image/png")

    def test_client_filename_cannot_affect_storage_path(self):
        resp = self.upload(make_image(), name="../../etc/passwd.png")
        image = Image.objects.get(pk=resp.json()["id"])
        self.assertEqual(image.file.name, f"images/{image.id}.png")

    def test_wrong_method_rejected(self):
        self.assertEqual(self.client.get("/api/v1/images").status_code, 405)


class ValidationTests(APITestBase):
    def test_missing_file_field(self):
        resp = self.client.post("/api/v1/images", {"other": "x"}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file", resp.json())

    def test_non_image_rejected(self):
        resp = self.upload(b"#!/bin/sh\necho hello\n", name="evil.png")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file", resp.json())
        self.assertEqual(Image.objects.count(), 0)

    def test_svg_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        resp = self.upload(svg, name="x.svg", content_type="image/svg+xml")
        self.assertEqual(resp.status_code, 400)

    def test_real_image_in_unsupported_format_rejected(self):
        buf = io.BytesIO()
        PILImage.new("RGB", (10, 10)).save(buf, format="BMP")
        resp = self.upload(buf.getvalue(), name="x.bmp", content_type="image/bmp")
        self.assertEqual(resp.status_code, 415)

    def test_truncated_image_rejected(self):
        data = make_image("PNG", (200, 200))
        resp = self.upload(data[: len(data) // 2])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Image.objects.count(), 0)