# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from . import views

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Listado de causas registradas en el sistema (solo lectura).
    path("lista/", views.lista_causas, name="lista_causas"),

    # Importación de causas desde un archivo Excel (.xlsx).
    path("importar/", views.importar_causas, name="importar_causas"),

    # Confirmación de la decisión (actualizar/mantener) sobre las
    # causas detectadas como duplicadas durante una importación.
    path(
        "importar/confirmar/",
        views.confirmar_actualizacion_causas,
        name="confirmar_actualizacion_causas",
    ),

]
