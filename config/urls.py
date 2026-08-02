from django.contrib import admin
from django.urls import path, include
# Importa las funciones necesarias para definir las rutas del proyecto.

urlpatterns = [

    # Panel de administración de Django
    path("admin/", admin.site.urls),

    # Página principal del sistema (Dashboard)
    path("", include("dashboard.urls")),

    # Rutas de la aplicación Usuarios
    path("usuarios/", include("usuarios.urls")),

    # Rutas de la aplicación Bloques
    path("bloques/", include("bloques.urls")),

]