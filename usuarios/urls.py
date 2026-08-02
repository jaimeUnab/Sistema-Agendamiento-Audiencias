from django.urls import path
from .views import UsuarioLoginView, UsuarioLogoutView, lista_usuarios

urlpatterns = [
    path("login/", UsuarioLoginView.as_view(), name="login"),

    # Cierre de sesión del usuario.
    path("logout/", UsuarioLogoutView.as_view(), name="logout"),

    # Listado de usuarios registrados en el sistema.
    path("lista/", lista_usuarios, name="lista_usuarios"),
]
