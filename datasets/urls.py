from django.urls import path

from . import views

app_name = "datasets"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("map/", views.map_viewer, name="map"),
    path("about/", views.about, name="about"),
    path("share-data/", views.share, name="share"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("contribute/", views.upload, name="upload"),
    path("contribute/my-uploads/", views.my_uploads, name="my_uploads"),
    path("review/", views.review_queue, name="review_queue"),
    path("datasets/<slug:slug>/", views.detail, name="detail"),
    path("datasets/<slug:slug>/download/", views.download, name="download"),
    path("datasets/<slug:slug>/geojson/", views.dataset_geojson, name="geojson"),
    path("datasets/<slug:slug>/edit/", views.edit, name="edit"),
    path("datasets/<slug:slug>/review/", views.review_action, name="review_action"),
]
