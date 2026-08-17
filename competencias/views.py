"""
Módulo de vistas de la aplicación Competencias.

Contiene las vistas de consulta del catálogo de
competencias (materias) del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso a usuarios con rol
# Administrador: Competencias es un módulo de Configuración
# (ver usuarios/decorators.py).
from usuarios.decorators import solo_administrador

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de competencias del sistema.
from .models import Competencia


# =====================================================
# LISTADO DE COMPETENCIAS
# =====================================================

@login_required
@solo_administrador
def lista_competencias(request):
    """
    Muestra el listado de competencias registradas
    en el sistema.

    Competencia es un catálogo de solo lectura: esta
    vista únicamente consulta y muestra los datos, no
    permite crear, editar, eliminar ni cambiar su estado.

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista:
    Competencias es un módulo de Configuración.
    """

    # -------------------------------------------------
    # Obtiene todas las competencias ordenadas
    # por nombre.
    # -------------------------------------------------

    competencias = Competencia.objects.all().order_by("nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "competencias": competencias
    }

    return render(
        request,
        "competencias/lista.html",
        context
    )
