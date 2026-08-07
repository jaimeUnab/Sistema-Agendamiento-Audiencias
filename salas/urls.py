# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_salas, crear_sala, editar_sala, cambiar_estado_sala

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de salas registradas en el sistema.
    path("lista/", lista_salas, name="lista_salas"),

    # Alta de una nueva sala.
    path("nueva/", crear_sala, name="crear_sala"),

    # Edición de una sala existente.
    path("<int:pk>/editar/", editar_sala, name="editar_sala"),

    # Activación/desactivación lógica de una sala existente.
    path("<int:pk>/estado/", cambiar_estado_sala, name="cambiar_estado_sala"),

]
