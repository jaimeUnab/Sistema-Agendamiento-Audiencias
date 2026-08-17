"""
Módulo de formularios de la aplicación Audiencias.

Contiene el formulario utilizado para recoger los datos de
entrada al registrar una nueva audiencia.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Únicamente para declarar MotivoBaja como TextChoices (un enum de
# Python, no un campo de modelo): no agrega ningún campo a
# Audiencia ni requiere migración.
from django.db import models

# Modelos de las relaciones que el formulario ofrece elegir.
from bloques.models import BloqueHorario
from competencias.models import Competencia
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

# Modelo de audiencia del sistema.
from .models import Audiencia


# =====================================================
# FORMULARIO
# =====================================================

class AudienciaForm(forms.ModelForm):
    """
    Formulario de entrada para registrar una nueva audiencia.

    La Causa ya NO se elige desde una lista desplegable. En su
    lugar, el funcionario selecciona una "competencia" y escribe
    un "rit": ambos son campos declarados aquí, pero NO son
    campos del modelo Audiencia (por eso van fuera de
    Meta.fields, igual que password1/password2 en UsuarioForm).
    Es la vista (audiencias/views.py) quien busca y resuelve el
    objeto Causa real a partir de estos dos valores -este
    formulario no hace esa búsqueda, solo entrega
    "competencia"/"rit" ya validados como datos de entrada.

    Incluye además los seis campos propios de Audiencia que sí
    selecciona el funcionario (tipoAudiencia, sala,
    cantidadBloques, fecha, bloqueInicio, anotacion). No incluye
    horaInicio, horaTermino, fechaCreacion, estado, motivoBaja
    ni usuarioCreacion: esos los determina el flujo de negocio.
    "anotacion" es opcional (blank=True en el modelo, por lo que
    ModelForm ya genera required=False sin necesidad de
    declararlo aparte) y se gestiona desde la interfaz mediante
    un botón/modal, no como un campo de texto visible permanente
    (ver templates/audiencias/formulario.html).

    IMPORTANTE: este formulario NO implementa form.save(), y no
    debe usarse para guardar una Audiencia directamente. Toda
    regla de negocio -búsqueda real de la causa, plazo legal,
    DiaAtencion, DiaNoDisponible, conflictos, disponibilidad,
    generación de propuestas, trazabilidad, confirmación de
    advertencias- vive exclusivamente en audiencias/views.py y
    audiencias/services.py; este formulario no la duplica.
    """

    # Competencia utilizada, junto con "rit", para localizar la
    # Causa. No es un campo de Audiencia: la vista la usa solo
    # para la búsqueda, y descarta este valor una vez resuelto
    # el objeto Causa real (que es lo que se entrega a
    # ServicioCreacionAudiencia/GeneradorPropuestaFecha).
    competencia = forms.ModelChoiceField(
        queryset=Competencia.objects.filter(activa=True),
        label="Competencia",
    )

    # RIT de la causa a buscar. Campo de texto libre, no un
    # Select: no existe un catálogo de "todos los RIT" entre
    # los cuales elegir, se escribe el que corresponde.
    rit = forms.CharField(
        max_length=20,
        label="RIT",
    )

    # Cantidad de bloques consecutivos que ocupará la audiencia.
    # Declarado explícitamente (en vez de dejar que ModelForm
    # genere el IntegerField por defecto para este campo) para
    # que sea un Select con únicamente las opciones 1 a 10, y
    # para que esa restricción se valide de verdad en el
    # servidor: ChoiceField/TypedChoiceField rechaza cualquier
    # valor que no esté en "choices" con un error de validación
    # ("Select a valid choice"), no es solo una pista visual del
    # navegador (a diferencia de simplemente poner min/max en un
    # NumberInput, que no impide un valor fuera de rango si
    # llega manipulado en la petición). coerce=int asegura que
    # cleaned_data["cantidadBloques"] siga siendo un int, igual
    # que antes, para que ServicioCreacionAudiencia y
    # GeneradorPropuestaFecha lo reciban sin ningún cambio.
    cantidadBloques = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(1, 11)],
        coerce=int,
        label="Cantidad de bloques",
    )

    class Meta:
        model = Audiencia

        # "causa" ya no es un campo de este formulario: se
        # reemplaza por la búsqueda vía competencia + rit
        # (declarados arriba, fuera de Meta.fields porque no
        # son campos de Audiencia). "cantidadBloques" sigue
        # listado aquí: sigue siendo el mismo campo del modelo
        # Audiencia, solo que su versión de formulario ahora es
        # la declarada arriba (Select 1-10) en vez de la que
        # ModelForm generaría automáticamente.
        fields = [
            "tipoAudiencia",
            "sala",
            "cantidadBloques",
            "fecha",
            "bloqueInicio",
            "anotacion",
        ]

        widgets = {
            # Selector de fecha nativo del navegador, mismo
            # criterio que BloqueHorarioForm usa type="time"
            # para sus campos de hora.
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }

    # Orden explícito: primero los datos para localizar la
    # causa (competencia, rit), después los datos propios de
    # la audiencia, en el mismo orden en que se muestran en
    # el template.
    field_order = [
        "competencia",
        "rit",
        "tipoAudiencia",
        "sala",
        "cantidadBloques",
        "fecha",
        "bloqueInicio",
    ]

    def __init__(self, *args, **kwargs):
        """
        Restringe los catálogos a lo que corresponde para una
        audiencia nueva:

        - competencia: solo activa=True.
        - sala: solo activa=True. Una sala inactiva no debe
          aparecer como opción (si de todos modos llegara su
          ID por una solicitud manipulada, Django la rechaza
          solo por no estar en este queryset; el backend
          -ValidadorAgendamiento- igual la vuelve a validar).
        - tipoAudiencia: solo activo=True, mismo criterio.
        - bloqueInicio: TODOS los BloqueHorario, ordenados por
          "orden", sin filtrar por
          permiteAgendamientoAutomatico. Ese campo solo acota
          qué bloques puede proponer automáticamente
          GeneradorPropuestaFecha; no debe restringir la
          programación manual, que siempre debe ser posible.
        """

        super().__init__(*args, **kwargs)

        self.fields["competencia"].queryset = Competencia.objects.filter(activa=True)
        self.fields["sala"].queryset = Sala.objects.filter(activa=True)
        self.fields["tipoAudiencia"].queryset = TipoAudiencia.objects.filter(
            activo=True
        )
        self.fields["bloqueInicio"].queryset = BloqueHorario.objects.all().order_by(
            "orden"
        )

    def clean_rit(self):
        """
        Quita espacios accidentales al inicio/fin del RIT
        ingresado. Es higiene básica de entrada, no una regla
        de negocio: " T-100-2026" y "T-100-2026" deben
        considerarse el mismo RIT al buscarlo.
        """

        return self.cleaned_data["rit"].strip()


# =====================================================
# BAJA LÓGICA: MOTIVO
# =====================================================

class MotivoBaja(models.TextChoices):
    """
    Categorías de motivo para dejar sin efecto (baja lógica) una
    Audiencia.

    NO es el choices= de ningún campo de modelo: Audiencia.
    motivoBaja sigue siendo un CharField de texto libre, sin
    cambios ni migración. Estas categorías existen únicamente
    para poblar el <select> del modal de "Dejar sin efecto" y
    para validar en DejarSinEfectoAudienciaForm; el texto final
    que se guarda en motivoBaja es la etiqueta elegida (y, si es
    OTRO, también la explicación ingresada por el funcionario).
    """

    SUSPENSION = "SUSPENSION", "Suspensión de la audiencia"
    REPROGRAMACION = "REPROGRAMACION", "Reprogramación"
    ERROR_AGENDAMIENTO = "ERROR_AGENDAMIENTO", "Error de agendamiento"
    SOLICITUD_TRIBUNAL = "SOLICITUD_TRIBUNAL", "Solicitud del tribunal"
    OTRO = "OTRO", "Otro"


class DejarSinEfectoAudienciaForm(forms.Form):
    """
    Valida el motivo por el cual se deja sin efecto una
    Audiencia.

    No es un ModelForm de Audiencia: solo valida el motivo,
    nunca decide el estado ni guarda nada -eso es
    responsabilidad exclusiva de ServicioBajaAudiencia-.
    "audiencia_id" no se declara como campo aquí: se lee
    directamente de request.POST en la vista, mismo criterio que
    guardar_anotacion_audiencia (audiencias/views.py) ya usa
    para el mismo dato.
    """

    motivo_seleccionado = forms.ChoiceField(
        choices=MotivoBaja.choices,
        label="Motivo de eliminación",
        error_messages={
            "required": "Debes seleccionar un motivo.",
            "invalid_choice": "El motivo seleccionado no es válido.",
        },
    )

    # Solo obligatorio cuando motivo_seleccionado == OTRO; esa
    # regla condicional se aplica en clean(), no aquí (un
    # required=True fijo rechazaría siempre las otras 4 opciones).
    motivo_otro = forms.CharField(
        required=False,
        max_length=200,
        label="Explicación adicional",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean(self):
        """
        Si se eligió OTRO, exige una explicación no vacía (con
        espacios accidentales ya recortados). Para el resto de
        las opciones, motivo_otro se ignora aunque venga con
        texto: no se combina con la etiqueta.
        """

        cleaned_data = super().clean()
        seleccionado = cleaned_data.get("motivo_seleccionado")
        otro = (cleaned_data.get("motivo_otro") or "").strip()

        if seleccionado == MotivoBaja.OTRO and not otro:
            self.add_error(
                "motivo_otro",
                "Debes ingresar una explicación cuando el motivo es 'Otro'.",
            )

        cleaned_data["motivo_otro"] = otro
        return cleaned_data

    def motivo_texto(self):
        """
        Arma el texto final a guardar en Audiencia.motivoBaja: la
        etiqueta legible del motivo elegido, y si es OTRO, agrega
        la explicación ingresada separada por ": ". Solo debe
        llamarse después de is_valid() == True (usa
        self.cleaned_data directamente, sin valores por defecto).
        """

        seleccionado = self.cleaned_data["motivo_seleccionado"]
        etiqueta = MotivoBaja(seleccionado).label

        if seleccionado == MotivoBaja.OTRO:
            return f"{etiqueta}: {self.cleaned_data['motivo_otro']}"

        return etiqueta
