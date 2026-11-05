from django.urls import path

from . import views

urlpatterns = [
    path("images", views.ImageUploadView.as_view(), name="image-upload"),
    # The <uuid:> converter rejects malformed ids before our view runs.
    path("images/<uuid:image_id>", views.ImageDetailView.as_view(), name="image-detail"),
]
