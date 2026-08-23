"""
Módulo de formularios de la aplicación Tipos de Audiencia.

Contiene el formulario utilizado para el alta y la edición de
tipos de audiencia del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Modelo de tipos de audiencia del sistema.
from .models import TipoAudiencia


# =====================================================
# FORMULARIO
# =====================================================

class TipoAudienciaForm(forms.ModelForm):
    """
    Formulario para el registro y la edición de tipos de audiencia.

    Incluye exactamente los tres campos que el modelo TipoAudiencia
    ya define (nombre, descripción y activo): no se agrega ningún
    campo nuevo (el plazo legal NO es un campo de este modelo, sino
    de ReglaAgendamiento -combinación Competencia + TipoAudiencia-,
    ver tipos_audiencia/models.py y reglas_agendamiento/models.py;
    se configura desde "Reglas de Agendamiento", no desde aquí). Las
    validaciones (nombre obligatorio y único, tal como ya lo exige
    el propio modelo) son las que el ModelForm deriva automáticamente
    de TipoAudiencia, sin reglas adicionales -mismo criterio que
    SalaForm (salas/forms.py), que tampoco agrega validaciones
    propias más allá de las del modelo-.
    """

    class Meta:
        model = TipoAudiencia

        # Campos del modelo que incluirá el formulario.
        fields = [
            "nombre",
            "descripcion",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        """
        Agrega la clase Bootstrap correspondiente a cada campo
        (form-control / form-select / form-check-input) según el
        tipo de widget, para que se vea consistente con el resto del
        sistema -mismo criterio que SalaForm/BloqueHorarioForm/
        UsuarioForm/ReglaAgendamientoForm (ver el docstring de
        SalaForm.__init__ en salas/forms.py)-. widget.attrs.setdefault
        (no una asignación directa) no pisaría ningún atributo que un
        widget ya trajera declarado. Es exclusivamente presentación:
        no cambia validación, valores ni comportamiento del
        formulario.
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
