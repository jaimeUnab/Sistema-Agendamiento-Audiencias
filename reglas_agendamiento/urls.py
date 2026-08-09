# =====================================================
# IMPORTACIONES
# =====================================================

from django.urls import path
from .views import (
    # General
    configuracion_general,
    # Plazos legales
    lista_reglas_agendamiento,
    crear_regla_agendamiento,
    editar_regla_agendamiento,
    cambiar_estado_regla_agendamiento,
    # Asignación de días por competencia
    dias_atencion,
    guardar_dias_atencion,
    # Días bloqueados
    dias_bloqueados,
    crear_dia_no_disponible,
    editar_dia_no_disponible,
    cambiar_estado_dia_no_disponible,
)

# =====================================================
# URLS
# =====================================================

urlpatterns = [

    # ---------------------------------------------------
    # Pestaña: General
    # ---------------------------------------------------

    # Configuración general de agendamiento (jornada, duración de
    # bloque, horizonte de búsqueda) + listado de salas de solo lectura.
    path("general/", configuracion_general, name="configuracion_general"),

    # ---------------------------------------------------
    # Pestaña: Plazos Legales
    # ---------------------------------------------------

    # Listado de reglas de agendamiento (plazo legal) registradas en el sistema.
    path("lista/", lista_reglas_agendamiento, name="lista_reglas_agendamiento"),

    # Configurar una regla de plazo legal (alta, o edición si la
    # combinación competencia + tipo de audiencia ya existe).
    path("reglas/nueva/", crear_regla_agendamiento, name="crear_regla_agendamiento"),

    # Edición de una regla de plazo legal existente.
    path("reglas/<int:pk>/editar/", editar_regla_agendamiento, name="editar_regla_agendamiento"),

    # Activación/desactivación lógica de una regla de plazo legal existente.
    path("reglas/<int:pk>/estado/", cambiar_estado_regla_agendamiento, name="cambiar_estado_regla_agendamiento"),

    # ---------------------------------------------------
    # Pestaña: Asignación de días por competencia
    # ---------------------------------------------------

    # Matriz Competencia × Día de la semana de días de atención.
    path("dias-atencion/", dias_atencion, name="dias_atencion"),

    # Guarda de una sola vez todos los cambios hechos sobre la matriz.
    path("dias-atencion/guardar/", guardar_dias_atencion, name="guardar_dias_atencion"),

    # ---------------------------------------------------
    # Pestaña: Días Bloqueados
    # ---------------------------------------------------

    # Listado de días no disponibles registrados en el sistema.
    path("dias-bloqueados/", dias_bloqueados, name="dias_bloqueados"),

    # Registrar un día no disponible (alta, o edición si la fecha ya existe).
    path("dias-bloqueados/nuevo/", crear_dia_no_disponible, name="crear_dia_no_disponible"),

    # Edición de un día no disponible existente.
    path("dias-bloqueados/<int:pk>/editar/", editar_dia_no_disponible, name="editar_dia_no_disponible"),

    # Activación/desactivación lógica de un día no disponible existente.
    path("dias-bloqueados/<int:pk>/estado/", cambiar_estado_dia_no_disponible, name="cambiar_estado_dia_no_disponible"),

]
