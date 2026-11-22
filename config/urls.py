from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Somaliland GeoData Portal – Administration"
admin.site.site_title = "GeoData Portal Admin"
admin.site.index_title = "Portal management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("datasets.urls")),
]

if settings.DEBUG:
    # Public media only (thumbnails/logos). Dataset files are never exposed here.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
