"""
Módulo de formularios de la aplicación Bloques.

Contiene los formularios utilizados para la administración
del horario oficial de audiencias del tribunal.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Modelo de bloques horarios del sistema.
from .models import BloqueHorario


# =====================================================
# FORMULARIO
# =====================================================

class BloqueHorarioForm(forms.ModelForm):
    """
    Formulario para el registro y edición de bloques
    horarios.

    Incluye únicamente los campos propios del modelo
    BloqueHorario; las validaciones (orden único, campos
    obligatorios) son las definidas por el propio modelo,
    sin reglas adicionales.

    Al crear un bloque nuevo, todos los campos son editables.
    Al editar un bloque existente, "orden", "horaInicio" y
    "horaTermino" quedan de solo lectura: los bloques
    describen la jornada oficial del tribunal y esa
    configuración horaria no debe alterarse desde la edición;
    solo puede modificarse si el algoritmo de agendamiento
    puede proponerlo automáticamente.
    """

    class Meta:
        model = BloqueHorario

        # Campos del modelo que incluirá el formulario.
        fields = [
            "orden",
            "horaInicio",
            "horaTermino",
            "permiteAgendamientoAutomatico",
        ]

        # Se usa un widget de tipo "time" para que el
        # navegador muestre un selector de hora nativo, en
        # vez del campo de texto libre que Django usa por
        # defecto para un TimeField.
        widgets = {
            "horaInicio": forms.TimeInput(attrs={"type": "time"}),
            "horaTermino": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Al editar un bloque existente (self.instance.pk ya
        asignado), "orden", "horaInicio" y "horaTermino" se
        marcan como disabled.

        Se usa el atributo "disabled" del campo (no solo el
        atributo HTML "readonly") porque es la práctica
        recomendada por Django para este caso: además de
        deshabilitar visualmente el campo en el formulario
        renderizado, Django ignora cualquier valor recibido
        para ese campo en el POST y usa siempre el valor
        inicial (el que ya tiene la instancia), sin importar
        que alguien manipule el HTML o el request. "readonly"
        es solo una pista visual y no ofrece esa protección.
        """

        super().__init__(*args, **kwargs)

        if self.instance.pk:
            self.fields["orden"].disabled = True
            self.fields["horaInicio"].disabled = True
            self.fields["horaTermino"].disabled = True
