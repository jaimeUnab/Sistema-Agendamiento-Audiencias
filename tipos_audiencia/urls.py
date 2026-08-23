# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import (
    lista_tipos_audiencia,
    crear_tipo_audiencia,
    editar_tipo_audiencia,
)

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de tipos de audiencia registrados en el sistema.
    path("lista/", lista_tipos_audiencia, name="lista_tipos_audiencia"),

    # Alta de un nuevo tipo de audiencia.
    path("nueva/", crear_tipo_audiencia, name="crear_tipo_audiencia"),

    # Edición de un tipo de audiencia existente.
    path("<int:pk>/editar/", editar_tipo_audiencia, name="editar_tipo_audiencia"),

]
