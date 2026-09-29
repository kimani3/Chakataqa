from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "investors"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("deposit/", views.deposit, name="deposit"),
    path("deposit/callback/", views.deposit_callback, name="deposit_callback"),
    path("paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="investors/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password/",
        auth_views.PasswordChangeView.as_view(
            template_name="investors/password_change.html",
            success_url=reverse_lazy("investors:dashboard"),
        ),
        name="password_change",
    ),
]
