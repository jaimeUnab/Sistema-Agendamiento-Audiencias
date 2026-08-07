# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import (
    lista_bloques,
    crear_bloque,
    editar_bloque,
    cambiar_agendamiento_automatico,
)

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de bloques horarios registrados en el sistema.
    path("lista/", lista_bloques, name="lista_bloques"),

    # Alta de un nuevo bloque horario.
    path("nuevo/", crear_bloque, name="crear_bloque"),

    # Edición de un bloque horario existente.
    # Ya no se usa desde la interfaz (el listado cambia el
    # indicador de agendamiento automático directamente sobre
    # el badge), pero se conserva la vista y la ruta.
    path("<int:pk>/editar/", editar_bloque, name="editar_bloque"),

    # Cambia si el bloque puede ser propuesto por el
    # agendamiento automático, directamente desde el listado.
    path(
        "<int:pk>/agendamiento-automatico/",
        cambiar_agendamiento_automatico,
        name="cambiar_agendamiento_automatico",
    ),

]
