from django.urls import path
from .views import UsuarioLoginView

urlpatterns = [
    path("", UsuarioLoginView.as_view(), name="login"),
]