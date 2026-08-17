"""
Módulo de vistas de la aplicación Días No Disponibles.

Contiene las vistas de consulta del catálogo de días no
disponibles del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso a usuarios con rol
# Administrador: Días No Disponibles es un módulo de
# Configuración (ver usuarios/decorators.py).
from usuarios.decorators import solo_administrador

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de días no disponibles del sistema.
from .models import DiaNoDisponible


# =====================================================
# LISTADO DE DÍAS NO DISPONIBLES
# =====================================================

@login_required
@solo_administrador
def lista_dias_no_disponibles(request):
    """
    Muestra el listado de días no disponibles
    registrados en el sistema.

    DiaNoDisponible es, por ahora, un catálogo de solo
    lectura: esta vista únicamente consulta y muestra los
    datos, no permite crear, editar, eliminar ni cambiar
    su estado.

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todos los días no disponibles ordenados
    # por fecha.
    # -------------------------------------------------

    dias_no_disponibles = DiaNoDisponible.objects.all().order_by("fecha")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "dias_no_disponibles": dias_no_disponibles
    }

    return render(
        request,
        "dias_no_disponibles/lista.html",
        context
    )
