# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from . import views

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # Registro de una nueva audiencia.
    path("nueva/", views.registrar_audiencia, name="registrar_audiencia"),

    # Solicitud de propuestas automáticas de fecha/bloques.
    path("proponer/", views.proponer_fechas_audiencia, name="proponer_fechas_audiencia"),

    # Consulta de disponibilidad de agenda (sala + fecha), de solo lectura.
    path(
        "disponibilidad/",
        views.ver_disponibilidad_audiencia,
        name="ver_disponibilidad_audiencia",
    ),

    # Agenda diaria: audiencias PROGRAMADAS de una fecha, de solo lectura.
    path("agenda/", views.agenda_diaria, name="agenda_diaria"),

    # Agenda semanal: audiencias PROGRAMADAS de una semana completa
    # (lunes a domingo), de solo lectura.
    path("agenda-semanal/", views.agenda_semanal, name="agenda_semanal"),

    # Agregar/modificar la anotación de una audiencia ya registrada.
    path(
        "anotacion/guardar/",
        views.guardar_anotacion_audiencia,
        name="guardar_anotacion_audiencia",
    ),

    # Dejar sin efecto (baja lógica) una audiencia PROGRAMADA.
    path(
        "dejar-sin-efecto/",
        views.dejar_sin_efecto_audiencia,
        name="dejar_sin_efecto_audiencia",
    ),

    # Consulta de trazabilidad de una audiencia, de solo lectura.
    path(
        "<int:pk>/trazabilidad/",
        views.ver_trazabilidad_audiencia,
        name="ver_trazabilidad_audiencia",
    ),

]
