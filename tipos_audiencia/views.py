"""
Módulo de vistas de la aplicación Tipos de Audiencia.

Contiene las vistas de consulta del catálogo de tipos de
audiencia (HU-13) del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de tipos de audiencia del sistema.
from .models import TipoAudiencia


# =====================================================
# LISTADO DE TIPOS DE AUDIENCIA
# =====================================================

@login_required
def lista_tipos_audiencia(request):
    """
    Muestra el listado de tipos de audiencia registrados
    en el sistema.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todos los tipos de audiencia ordenados
    # por competencia y nombre.
    # -------------------------------------------------

    tipos_audiencia = TipoAudiencia.objects.all().order_by("competencia", "nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "tipos_audiencia": tipos_audiencia
    }

    return render(
        request,
        "tipos_audiencia/lista.html",
        context
    )
