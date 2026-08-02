"""
Módulo de vistas de la aplicación Bloques.

Contiene las vistas de consulta del catálogo de bloques
horarios oficiales del tribunal.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de bloques horarios del sistema.
from .models import BloqueHorario


# =====================================================
# LISTADO DE BLOQUES HORARIOS
# =====================================================

@login_required
def lista_bloques(request):
    """
    Muestra el listado de bloques horarios oficiales
    registrados en el sistema.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todos los bloques horarios ordenados
    # por su campo "orden".
    # -------------------------------------------------

    bloques = BloqueHorario.objects.all().order_by("orden")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "bloques": bloques
    }

    return render(
        request,
        "bloques/lista.html",
        context
    )
