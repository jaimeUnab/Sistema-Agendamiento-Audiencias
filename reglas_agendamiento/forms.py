"""
Módulo de formularios de la aplicación Reglas de Agendamiento.

Contiene los formularios utilizados para configurar tres de las
cuatro categorías del módulo "Reglas de Agendamiento":

- ConfiguracionAgendamientoForm: jornada general del tribunal
  (pestaña "General"). El modelo ConfiguracionAgendamiento vive
  en la app "bloques", pero su administración se concentra
  aquí porque, junto con las otras tres, forma parte del mismo
  módulo visual "Reglas de Agendamiento".
- ReglaAgendamientoForm: plazo legal por competencia + tipo de
  audiencia (pestaña "Plazos Legales").
- DiaNoDisponibleForm: fechas no disponibles (pestaña "Días
  Bloqueados"). El modelo DiaNoDisponible vive en la app
  "dias_no_disponibles"; se administra aquí por el mismo
  motivo que ConfiguracionAgendamiento.

La cuarta categoría, "Asignación de días por competencia"
(modelo DiaAtencion), ya NO usa un ModelForm: se administra
como una matriz Competencia × Día de la semana
(reglas_agendamiento/views.py: dias_atencion/
guardar_dias_atencion), que aplica los cambios directamente
sobre el modelo. El DiaAtencionForm y las vistas de alta/edición
tradicionales que lo usaban (configurar_dia_atencion,
editar_dia_atencion, cambiar_estado_dia_atencion) se eliminaron
por quedar completamente sin uso una vez implementada la matriz.

Ninguno de estos formularios modifica los modelos de sus apps
de origen: solo los usa, igual que AudienciaForm ya usa modelos
de Bloques, Competencias, Salas y TiposAudiencia sin tocar esas
apps.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Modelo de configuración general de agendamiento (vive en la
# app "bloques", ver docstring del módulo).
from bloques.models import ConfiguracionAgendamiento

# Modelo de competencias del sistema.
from competencias.models import Competencia

# Modelo de tipos de audiencia del sistema.
from tipos_audiencia.models import TipoAudiencia

# Modelo de días no disponibles (vive en la app
# "dias_no_disponibles", ver docstring del módulo).
from dias_no_disponibles.models import DiaNoDisponible

# Modelos de esta propia app.
from .models import ReglaAgendamiento


# =====================================================
# FORMULARIO: CONFIGURACIÓN GENERAL
# =====================================================

class ConfiguracionAgendamientoForm(forms.ModelForm):
    """
    Formulario para editar la configuración general de
    agendamiento (pestaña "General"): jornada de atención,
    duración de cada bloque y horizonte de búsqueda.

    No incluye "claveUnica": es un campo técnico no editable
    (editable=False en el modelo), que ModelForm ya excluye
    automáticamente aunque se listara en Meta.fields. No hace
    falta un save() personalizado para "siempre usar la misma
    instancia": eso lo decide la vista (configuracion_general,
    en views.py), pasando la instancia existente -o None, si
    todavía no existe ninguna- al construir este formulario.
    """

    # Duración de cada bloque horario, en minutos. Declarado
    # explícitamente (en vez de dejar que ModelForm genere el
    # IntegerField por defecto para este campo del modelo) para
    # que sea un Select con únicamente las opciones 15/30/45/60,
    # y para que esa restricción se valide de verdad en el
    # servidor: TypedChoiceField rechaza cualquier valor que no
    # esté en "choices" con un error de validación ("Escoja una
    # opción válida..."), no es solo una pista visual del
    # navegador. Mismo patrón ya usado en
    # audiencias/forms.py:AudienciaForm.cantidadBloques.
    # coerce=int asegura que cleaned_data["duracionBloque"] siga
    # siendo un int, igual que antes, para que el resto del
    # sistema (y el propio modelo, un PositiveIntegerField) lo
    # reciba sin ningún cambio; no fue necesario modificar el
    # modelo ni ninguna migración.
    duracionBloque = forms.TypedChoiceField(
        choices=[
            (15, "15 minutos"),
            (30, "30 minutos"),
            (45, "45 minutos"),
            (60, "60 minutos"),
        ],
        coerce=int,
        label="Duración del bloque (minutos)",
    )

    class Meta:
        model = ConfiguracionAgendamiento

        # Los cuatro campos configurables que ya existen en el
        # modelo. No se agrega ningún campo adicional.
        fields = [
            "horaInicioJornada",
            "horaTerminoJornada",
            "duracionBloque",
            "horizonteBusquedaDias",
        ]

        # Selectores de hora nativos del navegador, mismo
        # criterio que BloqueHorarioForm.
        widgets = {
            "horaInicioJornada": forms.TimeInput(attrs={"type": "time"}),
            "horaTerminoJornada": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Agrega la clase Bootstrap correspondiente a cada campo
        (form-control / form-select) según el tipo de widget -
        "duracionBloque" es un Select (TypedChoiceField declarado
        arriba), el resto son inputs de hora/número-. Exclusivamente
        presentación: no cambia validación ni comportamiento.
        setdefault no pisa "type": "time" ya declarado en
        Meta.widgets.
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


# =====================================================
# FORMULARIO: PLAZO LEGAL
# =====================================================

class ReglaAgendamientoForm(forms.ModelForm):
    """
    Formulario para configurar (crear o editar) una regla de
    plazo legal: combinación de competencia + tipo de
    audiencia, con su plazo mínimo, máximo y unidad (hábil o
    corrido).

    Se usa tanto para "+ Agregar regla" (alta, o edición del
    registro ya existente si la combinación competencia +
    tipoAudiencia ya existe -ver crear_regla_agendamiento en
    views.py, que decide cuál de los dos casos corresponde-)
    como para "Editar" una regla puntual desde el listado (ver
    editar_regla_agendamiento).

    No agrega campos adicionales a los que ya define el
    modelo. "unidadPlazo" usa exactamente el enum TipoPlazo ya
    definido en reglas_agendamiento/models.py: Django genera su
    ChoiceField automáticamente a partir de
    choices=TipoPlazo.choices del modelo.

    La restricción UniqueConstraint(competencia, tipoAudiencia)
    del modelo se valida automáticamente al llamar a is_valid(),
    excluyendo la propia instancia cuando se está editando.
    """

    class Meta:
        model = ReglaAgendamiento

        fields = [
            "competencia",
            "tipoAudiencia",
            "plazoMinimo",
            "plazoMaximo",
            "unidadPlazo",
            "activa",
        ]

    def __init__(self, *args, **kwargs):
        """
        Explicita que "competencia" y "tipoAudiencia" ofrecen
        TODAS las competencias/tipos de audiencia existentes
        (sin filtrar por "activa"/"activo"): aquí se administra
        un catálogo de reglas, no se está agendando una
        audiencia nueva, por lo que debe seguir siendo posible
        ver o editar una regla aunque la competencia o el tipo
        de audiencia asociados hayan sido desactivados después.
        """

        super().__init__(*args, **kwargs)

        self.fields["competencia"].queryset = Competencia.objects.all()
        self.fields["tipoAudiencia"].queryset = TipoAudiencia.objects.all()

        # Clase Bootstrap correspondiente a cada campo (form-control /
        # form-select / form-check-input) según el tipo de widget -
        # "competencia"/"tipoAudiencia"/"unidadPlazo" son Select,
        # "activa" es un checkbox, el resto son inputs numéricos-.
        # Exclusivamente presentación: no cambia validación ni
        # comportamiento.
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


# =====================================================
# FORMULARIO: DÍA NO DISPONIBLE
# =====================================================

class DiaNoDisponibleForm(forms.ModelForm):
    """
    Formulario para configurar (crear o editar) una fecha no
    disponible (pestaña "Días Bloqueados").

    Se usa tanto para "+ Agregar día bloqueado" (alta, o
    edición del registro ya existente si la fecha ya está
    registrada -ver crear_dia_no_disponible en views.py, que
    decide cuál de los dos casos corresponde-) como para
    "Editar" un día bloqueado puntual desde el listado (ver
    editar_dia_no_disponible).

    No agrega campos adicionales a los que ya define el
    modelo: fecha, motivo, tipo, activo. "tipo" usa exactamente
    el enum TipoDiaNoDisponible ya definido en
    dias_no_disponibles/models.py, sin declarar otro enum aquí.

    La unicidad de "fecha" (unique=True en el modelo) se valida
    automáticamente al llamar a is_valid(), excluyendo la
    propia instancia cuando se está editando.
    """

    class Meta:
        model = DiaNoDisponible

        fields = [
            "fecha",
            "tipo",
            "motivo",
            "activo",
        ]

        widgets = {
            # Selector de fecha nativo del navegador, mismo
            # criterio que AudienciaForm usa para "fecha".
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Agrega la clase Bootstrap correspondiente a cada campo
        (form-control / form-select / form-check-input) según el
        tipo de widget -"tipo" es un Select, "activo" es un
        checkbox, "fecha"/"motivo" son inputs de texto-.
        Exclusivamente presentación: no cambia validación ni
        comportamiento. setdefault no pisa "type": "date" ya
        declarado en Meta.widgets.
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
