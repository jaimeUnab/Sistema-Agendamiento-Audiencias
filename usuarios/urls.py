# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import (
    UsuarioLoginView,
    UsuarioLogoutView,
    UsuarioCreateView,
    lista_usuarios,
)

# =====================================================
# URLS
# =====================================================

urlpatterns = [
    path("login/", UsuarioLoginView.as_view(), name="login"),

    # Cierre de sesión del usuario.
    path("logout/", UsuarioLogoutView.as_view(), name="logout"),

    # Listado de usuarios registrados en el sistema.
    path("lista/", lista_usuarios, name="lista_usuarios"),

    # Alta de un nuevo usuario (solo administradores o superusuarios).
    path("nuevo/", UsuarioCreateView.as_view(), name="nuevo_usuario"),
]
