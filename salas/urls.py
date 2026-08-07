# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_salas

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de salas registradas en el sistema.
    path("lista/", lista_salas, name="lista_salas"),

]
