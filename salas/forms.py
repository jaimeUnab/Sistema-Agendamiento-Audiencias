"""
Módulo de formularios de la aplicación Salas.

Contiene los formularios utilizados para la administración
de salas del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Modelo de salas del sistema.
from .models import Sala


# =====================================================
# FORMULARIO
# =====================================================

class SalaForm(forms.ModelForm):
    """
    Formulario para el registro de nuevas salas.

    Incluye únicamente los campos propios del modelo Sala
    necesarios para su alta; las validaciones (nombre único,
    campos obligatorios) son las definidas por el propio
    modelo, sin reglas adicionales.
    """

    class Meta:
        model = Sala

        # Campos del modelo que incluirá el formulario.
        fields = [
            "nombre",
            "activa",
        ]
