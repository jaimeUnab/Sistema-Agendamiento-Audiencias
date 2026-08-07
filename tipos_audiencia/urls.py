# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_tipos_audiencia

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de tipos de audiencia registrados en el sistema.
    path("lista/", lista_tipos_audiencia, name="lista_tipos_audiencia"),

]
