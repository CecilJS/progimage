from django.urls import path

from . import views

urlpatterns = [
    path("images", views.ImageUploadView.as_view(), name="image-upload"),
]