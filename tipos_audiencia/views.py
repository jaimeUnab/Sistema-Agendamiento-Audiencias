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
    # Obtiene todos los tipos de audiencia ordenados por
    # nombre. Antes también se ordenaba por "competencia",
    # pero TipoAudiencia ya no tiene ese campo: es un
    # catálogo transversal desde que se repurposó (ver
    # tipos_audiencia/models.py), y ese order_by quedó
    # desactualizado, provocando un FieldError al usar esta
    # vista. Coincide con Meta.ordering = ["nombre"] del
    # propio modelo; se deja explícito aquí, mismo criterio
    # que el resto de los listados del proyecto (por ejemplo
    # lista_salas).
    # -------------------------------------------------

    tipos_audiencia = TipoAudiencia.objects.all().order_by("nombre")

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
