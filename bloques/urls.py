# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_bloques

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de bloques horarios registrados en el sistema.
    path("lista/", lista_bloques, name="lista_bloques"),

]
