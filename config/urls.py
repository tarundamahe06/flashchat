from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # Users API
    path("api/users/", include("users.urls")),

    # Chat API
    path("api/chat/", include("chat.urls")),
]