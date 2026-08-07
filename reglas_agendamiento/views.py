"""
Módulo de vistas de la aplicación Reglas de Agendamiento.

Contiene las vistas de consulta del catálogo de reglas
de agendamiento del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de reglas de agendamiento del sistema.
from .models import ReglaAgendamiento


# =====================================================
# LISTADO DE REGLAS DE AGENDAMIENTO
# =====================================================

@login_required
def lista_reglas_agendamiento(request):
    """
    Muestra el listado de reglas de agendamiento
    registradas en el sistema.

    ReglaAgendamiento es un catálogo de solo lectura: esta
    vista únicamente consulta y muestra los datos, no
    permite crear, editar, eliminar ni cambiar su estado.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todas las reglas de agendamiento ordenadas
    # por competencia y día de la semana.
    # -------------------------------------------------

    reglas = ReglaAgendamiento.objects.all().order_by("competencia", "diaSemana")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "reglas": reglas
    }

    return render(
        request,
        "reglas_agendamiento/lista.html",
        context
    )
