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

    def __init__(self, *args, **kwargs):
        """
        Agrega la clase Bootstrap correspondiente a cada campo
        (form-control / form-select / form-check-input) según el
        tipo de widget, para que se vea consistente con el resto
        del sistema (ver templates/audiencias/formulario.html).

        widget.attrs.setdefault (no una asignación directa) no
        pisaría ningún atributo que un widget ya trajera declarado
        -este formulario no tiene ninguno, pero es el mismo
        criterio usado en BloqueHorarioForm/UsuarioForm/
        ReglaAgendamientoForm/DiaNoDisponibleForm, que sí traen
        widgets con attrs propios (type="time", type="date")-.
        Es exclusivamente presentación: no cambia validación,
        valores ni comportamiento del formulario.
        """

        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
