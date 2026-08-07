# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_dias_no_disponibles

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de días no disponibles registrados en el sistema.
    path("lista/", lista_dias_no_disponibles, name="lista_dias_no_disponibles"),

]
