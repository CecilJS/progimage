from django.urls import include, path

urlpatterns = [
    # Versioned from day one so a breaking change can live at /api/v2/
    # without breaking existing clients.
    path("api/v1/", include("images.urls")),
]

# FUTURE: a /healthz endpoint for load balancers, and custom handler404 /
# handler500 so even Django's own errors come back as JSON instead of HTML.