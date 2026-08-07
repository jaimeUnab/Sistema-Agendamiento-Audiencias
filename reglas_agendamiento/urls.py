# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_reglas_agendamiento

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de reglas de agendamiento registradas en el sistema.
    path("lista/", lista_reglas_agendamiento, name="lista_reglas_agendamiento"),

]
