"""
Módulo de vistas de la aplicación Salas.

Contiene las vistas de consulta del catálogo de salas
del tribunal.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de salas del sistema.
from .models import Sala


# =====================================================
# LISTADO DE SALAS
# =====================================================

@login_required
def lista_salas(request):
    """
    Muestra el listado de salas registradas
    en el sistema.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todas las salas ordenadas por nombre.
    # -------------------------------------------------

    salas = Sala.objects.all().order_by("nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "salas": salas
    }

    return render(
        request,
        "salas/lista.html",
        context
    )
