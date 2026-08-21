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

    # Rutas de la aplicación Competencias
    path("competencias/", include("competencias.urls")),

    # Rutas de la aplicación Tipos de Audiencia
    path("tipos-audiencia/", include("tipos_audiencia.urls")),

    # Rutas de la aplicación Salas
    path("salas/", include("salas.urls")),

    # Rutas de la aplicación Reglas de Agendamiento
    path("reglas-agendamiento/", include("reglas_agendamiento.urls")),

    # Rutas de la aplicación Días No Disponibles
    path("dias-no-disponibles/", include("dias_no_disponibles.urls")),

    # Rutas de la aplicación Causas
    path("causas/", include("causas.urls")),

    # Rutas de la aplicación Audiencias
    path("audiencias/", include("audiencias.urls")),

]