from django.urls import path
from . import views
# Importa las vistas de la aplicación Dashboard.


urlpatterns = [

    # Página principal del sistema
    path("", views.inicio, name="inicio"),

]