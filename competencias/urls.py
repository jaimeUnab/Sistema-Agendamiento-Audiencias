# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import lista_competencias

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de competencias registradas en el sistema.
    path("lista/", lista_competencias, name="lista_competencias"),

]
