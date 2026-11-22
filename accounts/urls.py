from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.signup, name="signup"),
    path("profile/", views.profile, name="profile"),
    path("request-specialist/", views.request_specialist, name="request_specialist"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html", success_url="/accounts/profile/"
        ),
        name="password_change",
    ),
]
