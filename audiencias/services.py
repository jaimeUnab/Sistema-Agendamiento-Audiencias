"""
Módulo de servicios (lógica de negocio) de la aplicación
Audiencias.

Contiene:

- ValidadorAgendamiento: valida una Audiencia antes de
  registrarla (errores bloqueantes + advertencias de negocio).
- GeneradorPropuestaFecha: genera hasta 3 propuestas
  automáticas de fecha/bloques para una audiencia, en una
  sala ya elegida por el funcionario.
- ServicioTrazabilidad: registra en RegistroTrazabilidad las
  operaciones (creación, modificación, baja) realizadas sobre
  una Audiencia. No modifica ni guarda la Audiencia: eso es
  responsabilidad del flujo de negocio que lo invoque.
- ServicioCreacionAudiencia: coordina el registro de una
  Audiencia nueva, orquestando ValidadorAgendamiento y
  ServicioTrazabilidad (no implementa lógica de validación ni
  de trazabilidad propia, solo las invoca en el orden
  correcto). No llama a GeneradorPropuestaFecha: el generador
  es una ayuda opcional de la interfaz, independiente del
  proceso de creación.

ValidadorAgendamiento y GeneradorPropuestaFecha comparten el
cálculo de días hábiles y la comparación de solapamiento de
bloques (funciones de módulo _contarDiasHabiles y
_rangosSeSolapan, más abajo), para no duplicar esa lógica.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime

from django.db import transaction

from bloques.models import BloqueHorario, ConfiguracionAgendamiento
from dias_no_disponibles.models import DiaNoDisponible, TipoDiaNoDisponible
from reglas_agendamiento.models import (
    DiaAtencion,
    DiaSemana,
    ReglaAgendamiento,
    TipoPlazo,
)

from .models import (
    AccionTrazabilidad,
    Audiencia,
    EstadoAudiencia,
    RegistroTrazabilidad,
)


# =====================================================
# FUNCIONES COMPARTIDAS
# =====================================================
# Usadas tanto por ValidadorAgendamiento como por
# GeneradorPropuestaFecha. Viven a nivel de módulo
# precisamente para que ninguna de las dos clases tenga que
# reimplementarlas.

# Traduce el día de la semana de Python (0=lunes) al valor
# correspondiente de DiaSemana. Sábado (5) y domingo (6) no
# tienen equivalente: el tribunal no atiende esos días como
# "día de atención" (ver DiaSemana). Nota: esto es distinto
# de la definición de "día hábil" para el plazo legal, que sí
# incluye el sábado (ver _contarDiasHabiles).
_DIAS_SEMANA_PYTHON = {
    0: DiaSemana.LUNES,
    1: DiaSemana.MARTES,
    2: DiaSemana.MIERCOLES,
    3: DiaSemana.JUEVES,
    4: DiaSemana.VIERNES,
}


def _diaSemanaDe(fecha):
    """
    Traduce una fecha de Python al valor de DiaSemana
    correspondiente, o None si cae en sábado o domingo (sin
    representación en DiaSemana).
    """
    return _DIAS_SEMANA_PYTHON.get(fecha.weekday())


def _contarDiasHabiles(fecha_inicio, fecha_fin):
    """
    Cuenta los días hábiles entre fecha_inicio (exclusiva) y
    fecha_fin (inclusiva), según la definición confirmada:

    - Lunes a sábado cuentan como hábiles.
    - Domingo no cuenta.
    - Las fechas con un DiaNoDisponible activo de tipo
      FERIADO no cuentan (otros tipos de DiaNoDisponible
      -cierre de tribunal, mantención, suspensión judicial,
      otro- no afectan este cálculo).
    - DiaAtencion no participa en este cálculo.

    Si fecha_fin es anterior a fecha_inicio, el resultado es
    negativo (mismo criterio que una resta de fechas
    corriente).
    """
    feriados = set(
        DiaNoDisponible.objects.filter(
            activo=True, tipo=TipoDiaNoDisponible.FERIADO
        ).values_list("fecha", flat=True)
    )

    paso = 1 if fecha_fin >= fecha_inicio else -1
    contador = 0
    fecha_actual = fecha_inicio

    while fecha_actual != fecha_fin:
        fecha_actual += datetime.timedelta(days=paso)
        # weekday(): 0=lunes ... 5=sábado ... 6=domingo.
        es_domingo = fecha_actual.weekday() == 6
        if not es_domingo and fecha_actual not in feriados:
            contador += paso

    return contador


def _rangosSeSolapan(inicio_a, fin_a, inicio_b, fin_b):
    """
    Indica si dos rangos cerrados [inicio_a, fin_a] y
    [inicio_b, fin_b] (enteros, típicamente valores de
    BloqueHorario.orden) se solapan en algún punto.
    """
    return inicio_a <= fin_b and inicio_b <= fin_a


# =====================================================
# VALIDADOR DE AGENDAMIENTO
# =====================================================

class ValidadorAgendamiento:
    """
    Valida una Audiencia antes de registrarla.

    REGLA PRINCIPAL DEL DISEÑO: el sistema siempre permite la
    programación manual. Las reglas de negocio (plazo legal,
    día de atención, día no disponible, conflicto de sala/
    bloque) nunca bloquean por sí solas: se reportan como
    "advertencias", para que el funcionario decida si
    continúa. Solo bloquean los "errores": datos obligatorios
    faltantes, datos técnicamente inválidos, o una sala
    inactiva (una sala desactivada por un administrador no es
    una advertencia: es una restricción de configuración, no
    está disponible para agendamiento bajo ninguna
    circunstancia).

    Opera sobre una instancia de Audiencia SIN GUARDAR
    (audiencia.pk puede ser None; en ningún punto de esta
    clase se llama a audiencia.save()). Acceder a una FK no
    asignada (por ejemplo audiencia.causa cuando nunca se
    asignó causa_id) devuelve None en Django sin lanzar
    excepción, lo que permite validar instancias con datos
    incompletos.

    fecha_referencia se recibe explícitamente (un
    datetime.date) en vez de inferirse de
    audiencia.fechaCreacion o de la fecha del día: quien
    instancia el validador es responsable de indicar cuál es
    la fecha desde la que se cuenta el plazo legal.
    """

    def __init__(self, audiencia, fecha_referencia):
        self.audiencia = audiencia
        self.fecha_referencia = fecha_referencia
        self.errores = []
        self.advertencias = []

    # =================================================
    # PUNTO DE ENTRADA
    # =================================================

    def validar(self):
        """
        Ejecuta todas las validaciones y devuelve:
            {"errores": [...], "advertencias": [...]}

        Cada método de advertencia valida por su cuenta que
        tiene los datos que necesita antes de consultar la
        base de datos; si a la audiencia le faltan datos para
        evaluar una advertencia en particular, esa advertencia
        simplemente no se agrega (el error correspondiente de
        "dato obligatorio faltante" ya lo reporta
        _validarDatosObligatorios()).
        """
        self.errores = []
        self.advertencias = []

        self._validarDatosObligatorios()
        self._validarSalaActiva()

        self.validarConflicto()
        self.validarPlazoLegal()
        self.validarDiaHabil()

        return {
            "errores": self.errores,
            "advertencias": self.advertencias,
        }

    # =================================================
    # ERRORES (bloqueantes)
    # =================================================

    def _validarDatosObligatorios(self):
        """
        Verifica los datos mínimos para que la audiencia sea
        técnicamente válida.
        """
        a = self.audiencia

        if not a.causa_id:
            self.errores.append("Falta indicar la causa.")

        if not a.tipoAudiencia_id:
            self.errores.append("Falta indicar el tipo de audiencia.")

        if not a.sala_id:
            self.errores.append("Falta indicar la sala.")

        if not a.fecha:
            self.errores.append("Falta indicar la fecha.")

        if not a.bloqueInicio_id:
            self.errores.append("Falta indicar el bloque de inicio.")

        if a.cantidadBloques is None or a.cantidadBloques < 1:
            self.errores.append(
                "La cantidad de bloques debe ser al menos 1."
            )

    def _validarSalaActiva(self):
        """
        Una sala con activa=False fue desactivada por un
        administrador para agendamiento: es un error
        bloqueante, no una advertencia. No se muestra como
        "¿está seguro?"; la sala directamente no está
        disponible.
        """
        a = self.audiencia

        if a.sala_id and not a.sala.activa:
            self.errores.append(
                "La sala seleccionada no está disponible para agendamiento."
            )

    # =================================================
    # ADVERTENCIAS (no bloqueantes)
    # =================================================

    def validarConflicto(self):
        """
        Advierte si ya existe una audiencia PROGRAMADA que
        ocupa bloques coincidentes en la misma sala y fecha.

        La ocupación se determina mediante bloqueInicio +
        cantidadBloques (comparando el campo "orden" de
        BloqueHorario), no mediante horaInicio/horaTermino.
        """
        a = self.audiencia

        if not (a.sala_id and a.bloqueInicio_id and a.fecha and a.cantidadBloques):
            return

        inicio_nuevo = a.bloqueInicio.orden
        fin_nuevo = inicio_nuevo + a.cantidadBloques - 1

        candidatas = Audiencia.objects.filter(
            sala_id=a.sala_id,
            fecha=a.fecha,
            estado=EstadoAudiencia.PROGRAMADA,
        ).exclude(pk=a.pk).select_related("bloqueInicio")

        for existente in candidatas:
            inicio_existente = existente.bloqueInicio.orden
            fin_existente = inicio_existente + existente.cantidadBloques - 1

            if _rangosSeSolapan(inicio_nuevo, fin_nuevo, inicio_existente, fin_existente):
                self.advertencias.append(
                    "Ya existe una audiencia programada en la sala y "
                    "horario seleccionados. ¿Está seguro de que desea "
                    "programarla?"
                )
                break

    def validarPlazoLegal(self):
        """
        Advierte si no existe una ReglaAgendamiento activa
        para la combinación Competencia + TipoAudiencia de la
        audiencia, o si la fecha queda fuera del plazo
        configurado.

        El plazo se cuenta desde self.fecha_referencia (no
        desde audiencia.fechaCreacion: ver docstring de la
        clase). Si unidadPlazo es CORRIDO, se cuentan todos
        los días del calendario. Si es HABIL, se cuentan los
        días de lunes a sábado, excluyendo únicamente las
        fechas con un DiaNoDisponible activo de tipo FERIADO
        (domingo nunca cuenta; DiaAtencion no participa en
        este cálculo).
        """
        a = self.audiencia

        if not (a.causa_id and a.tipoAudiencia_id and a.fecha):
            return

        competencia = a.causa.competencia

        regla = ReglaAgendamiento.objects.filter(
            competencia=competencia,
            tipoAudiencia_id=a.tipoAudiencia_id,
            activa=True,
        ).first()

        if regla is None:
            self.advertencias.append(
                "No existe un plazo legal configurado para la "
                "combinación seleccionada."
            )
            return

        if regla.unidadPlazo == TipoPlazo.CORRIDO:
            dias_transcurridos = (a.fecha - self.fecha_referencia).days
        else:
            dias_transcurridos = _contarDiasHabiles(self.fecha_referencia, a.fecha)

        if not (regla.plazoMinimo <= dias_transcurridos <= regla.plazoMaximo):
            self.advertencias.append(
                "La fecha seleccionada se encuentra fuera del plazo "
                "legal configurado."
            )

    def validarDiaHabil(self):
        """
        Advierte si el día de la semana de la audiencia no
        está configurado como día de atención habitual para
        la competencia (vía DiaAtencion), y por separado si la
        fecha está marcada como DiaNoDisponible a nivel global
        del tribunal.
        """
        a = self.audiencia

        if not (a.causa_id and a.fecha):
            return

        competencia = a.causa.competencia
        dia_semana = _diaSemanaDe(a.fecha)

        if dia_semana is None or not DiaAtencion.objects.filter(
            competencia=competencia,
            diaSemana=dia_semana,
            activa=True,
        ).exists():
            self.advertencias.append(
                "El día seleccionado no está configurado como día "
                "habitual de atención para esta competencia."
            )

        # fecha es unique=True en DiaNoDisponible (ver
        # dias_no_disponibles/models.py): nunca puede haber más
        # de un registro para la misma fecha, así que .first()
        # sobre este filtro devuelve como máximo uno, sin
        # necesidad de decidir entre varios.
        dia_no_disponible = DiaNoDisponible.objects.filter(
            fecha=a.fecha, activo=True
        ).first()

        if dia_no_disponible is not None:
            motivo = dia_no_disponible.motivo.strip()

            if motivo:
                self.advertencias.append(
                    "El día seleccionado se encuentra marcado como no "
                    f"disponible. Motivo: {motivo}."
                )
            else:
                # Registro existente pero sin motivo cargado: se
                # mantiene exactamente el mensaje original, sin
                # agregar "Motivo:" vacío.
                self.advertencias.append(
                    "El día seleccionado se encuentra marcado como no "
                    "disponible."
                )


# =====================================================
# GENERADOR DE PROPUESTA DE FECHA
# =====================================================

class GeneradorPropuestaFecha:
    """
    Genera hasta 3 propuestas automáticas de fecha/bloques
    para una audiencia, en una sala YA elegida por el
    funcionario (no busca ni cambia de sala: eso lo decide el
    funcionario antes de pedir propuestas).

    REGLA PRINCIPAL DEL DISEÑO: solo genera sugerencias. Nunca
    guarda una Audiencia ni bloquea la programación manual; el
    funcionario siempre puede elegir otra fecha por su cuenta,
    y en ese caso es ValidadorAgendamiento quien evalúa esa
    elección manual.

    Prioriza fechas dentro del plazo legal (cuando existe una
    ReglaAgendamiento aplicable) y completa con las fechas
    disponibles más cercanas a fecha_referencia aunque queden
    fuera de plazo, marcándolas con fueraDePlazo=True. Si no
    existe ReglaAgendamiento, ninguna fecha se marca fuera de
    plazo: se buscan simplemente las 3 más cercanas
    disponibles.

    Si la sala indicada no está activa, generar() lanza
    ValueError: es un error bloqueante, no genera ninguna
    propuesta (parcial ni total).
    """

    MAXIMO_PROPUESTAS = 3

    def __init__(self, causa, tipoAudiencia, sala, cantidadBloques, fecha_referencia):
        self.causa = causa
        self.tipoAudiencia = tipoAudiencia
        self.sala = sala
        self.cantidadBloques = cantidadBloques
        self.fecha_referencia = fecha_referencia

    # =================================================
    # PUNTO DE ENTRADA
    # =================================================

    def generar(self):
        """
        Devuelve una lista de hasta MAXIMO_PROPUESTAS dicts,
        cada uno con:
            {
                "fecha": date,
                "sala": Sala,
                "bloqueInicio": BloqueHorario,
                "cantidadBloques": int,
                "horaInicio": time,
                "horaTermino": time,
                "fueraDePlazo": bool,
                "advertencias": [str, ...],
            }

        Lanza ValueError si la sala indicada no está activa.
        """
        if not self.sala.activa:
            raise ValueError(
                "La sala seleccionada no está disponible para agendamiento."
            )

        competencia = self.causa.competencia

        dias_habilitados = set(
            DiaAtencion.objects.filter(
                competencia=competencia, activa=True
            ).values_list("diaSemana", flat=True)
        )

        fechas_no_disponibles = set(
            DiaNoDisponible.objects.filter(activo=True).values_list(
                "fecha", flat=True
            )
        )

        regla = ReglaAgendamiento.objects.filter(
            competencia=competencia,
            tipoAudiencia=self.tipoAudiencia,
            activa=True,
        ).first()

        horizonte = ConfiguracionAgendamiento.objects.get().horizonteBusquedaDias
        limite = self.fecha_referencia + datetime.timedelta(days=horizonte)

        dentro_de_plazo = []
        fuera_de_plazo = []

        fecha_actual = self.fecha_referencia

        # Recorrido cronológico único: se detiene apenas se
        # juntan 3 propuestas dentro de plazo, porque al ser
        # cronológico esas 3 ya son las más cercanas posibles.
        while fecha_actual < limite and len(dentro_de_plazo) < self.MAXIMO_PROPUESTAS:
            fecha_actual += datetime.timedelta(days=1)

            dia_semana = _diaSemanaDe(fecha_actual)
            if dia_semana is None or dia_semana not in dias_habilitados:
                continue

            if fecha_actual in fechas_no_disponibles:
                continue

            secuencia = self._buscarBloquesLibres(fecha_actual)
            if secuencia is None:
                continue

            propuesta = self._construirPropuesta(fecha_actual, secuencia)

            if regla is None:
                dentro_de_plazo.append(propuesta)
                continue

            if regla.unidadPlazo == TipoPlazo.CORRIDO:
                dias_transcurridos = (fecha_actual - self.fecha_referencia).days
            else:
                dias_transcurridos = _contarDiasHabiles(
                    self.fecha_referencia, fecha_actual
                )

            if regla.plazoMinimo <= dias_transcurridos <= regla.plazoMaximo:
                dentro_de_plazo.append(propuesta)
            else:
                propuesta["fueraDePlazo"] = True
                propuesta["advertencias"].append(
                    "Fecha propuesta fuera del plazo legal."
                )
                fuera_de_plazo.append(propuesta)

        propuestas = dentro_de_plazo[: self.MAXIMO_PROPUESTAS]

        if len(propuestas) < self.MAXIMO_PROPUESTAS:
            faltan = self.MAXIMO_PROPUESTAS - len(propuestas)
            propuestas.extend(fuera_de_plazo[:faltan])

        return propuestas

    # =================================================
    # AUXILIARES
    # =================================================

    def _buscarBloquesLibres(self, fecha):
        """
        Busca, en self.sala y en "fecha", la primera secuencia
        de self.cantidadBloques bloques consecutivos (por
        "orden"), habilitados para agendamiento automático
        (permiteAgendamientoAutomatico=True) y libres de
        conflicto con audiencias PROGRAMADA existentes.

        Devuelve la lista de BloqueHorario de esa secuencia
        (ordenada), o None si no hay ninguna secuencia libre
        ese día.
        """
        bloques = list(
            BloqueHorario.objects.filter(
                permiteAgendamientoAutomatico=True
            ).order_by("orden")
        )

        ocupados = self._rangosOcupados(fecha)

        n = self.cantidadBloques
        for i in range(len(bloques) - n + 1):
            secuencia = bloques[i:i + n]
            ordenes = [b.orden for b in secuencia]

            # Deben ser consecutivos (sin huecos entre ellos).
            if ordenes != list(range(ordenes[0], ordenes[0] + n)):
                continue

            inicio, fin = ordenes[0], ordenes[-1]

            if any(
                _rangosSeSolapan(inicio, fin, oc_inicio, oc_fin)
                for oc_inicio, oc_fin in ocupados
            ):
                continue

            return secuencia

        return None

    def _rangosOcupados(self, fecha):
        """
        Devuelve los rangos [inicio, fin] (en "orden" de
        BloqueHorario) ocupados por audiencias PROGRAMADA en
        self.sala, en "fecha".
        """
        ocupadas = Audiencia.objects.filter(
            sala=self.sala,
            fecha=fecha,
            estado=EstadoAudiencia.PROGRAMADA,
        ).select_related("bloqueInicio")

        return [
            (a.bloqueInicio.orden, a.bloqueInicio.orden + a.cantidadBloques - 1)
            for a in ocupadas
        ]

    def _construirPropuesta(self, fecha, secuencia):
        """
        Arma el dict de una propuesta a partir de la fecha y
        la secuencia de bloques consecutivos encontrada.
        fueraDePlazo/advertencias parten en su valor "dentro
        de plazo"; generar() los ajusta si corresponde.
        """
        return {
            "fecha": fecha,
            "sala": self.sala,
            "bloqueInicio": secuencia[0],
            "cantidadBloques": self.cantidadBloques,
            "horaInicio": secuencia[0].horaInicio,
            "horaTermino": secuencia[-1].horaTermino,
            "fueraDePlazo": False,
            "advertencias": [],
        }


# =====================================================
# SERVICIO DE TRAZABILIDAD
# =====================================================

class ServicioTrazabilidad:
    """
    Registra las operaciones (creación, modificación, baja)
    realizadas sobre una Audiencia, asociándolas al usuario
    responsable.

    REGLA PRINCIPAL DEL DISEÑO: este servicio SOLO crea
    registros RegistroTrazabilidad. En ningún método modifica
    ni guarda la Audiencia recibida (nunca llama a
    audiencia.save() ni asigna atributos sobre ella); la baja
    lógica y cualquier otro cambio de la audiencia son
    responsabilidad del flujo de negocio que lo invoque.

    Para MODIFICACION y BAJA, "valoresAnteriores" no lo
    calcula este servicio: cuando se lo invoca, "audiencia" ya
    llega con el estado NUEVO (fue modificada y guardada por
    el llamador antes de invocar el servicio), así que el
    estado anterior ya no existe en esa instancia. El flujo
    correcto, a cargo de quien use este servicio, es:

        anterior = ServicioTrazabilidad.fotografiar(audiencia)
        # ... se modifica audiencia y se guarda (audiencia.save()) ...
        ServicioTrazabilidad.registrarModificacion(
            audiencia, usuario, valoresAnteriores=anterior
        )

    No agrega ni modifica ningún modelo: usa el JSONField ya
    existente de RegistroTrazabilidad (valoresAnteriores/
    valoresNuevos).
    """

    @staticmethod
    def fotografiar(audiencia):
        """
        Devuelve un diccionario JSON-serializable con el
        estado actual de "audiencia".

        Las relaciones FK se guardan como su ID (campos
        "*_id" de Django, sin consulta adicional a la base de
        datos), no como una etiqueta descriptiva.

        Las fechas/horas (fecha, horaInicio, horaTermino,
        fechaCreacion) se convierten explícitamente con
        isoformat(): los JSONField de RegistroTrazabilidad no
        usan DjangoJSONEncoder, por lo que guardar un objeto
        date/time/datetime sin convertir haría fallar el
        guardado.
        """
        return {
            "id": audiencia.id,
            "causaId": audiencia.causa_id,
            "tipoAudienciaId": audiencia.tipoAudiencia_id,
            "salaId": audiencia.sala_id,
            "bloqueInicioId": audiencia.bloqueInicio_id,
            "cantidadBloques": audiencia.cantidadBloques,
            "fecha": (
                audiencia.fecha.isoformat() if audiencia.fecha else None
            ),
            "horaInicio": (
                audiencia.horaInicio.isoformat()
                if audiencia.horaInicio
                else None
            ),
            "horaTermino": (
                audiencia.horaTermino.isoformat()
                if audiencia.horaTermino
                else None
            ),
            "estado": audiencia.estado,
            "motivoBaja": audiencia.motivoBaja,
            "fechaCreacion": (
                audiencia.fechaCreacion.isoformat()
                if audiencia.fechaCreacion
                else None
            ),
            "usuarioCreacionId": audiencia.usuarioCreacion_id,
        }

    @staticmethod
    def registrarCreacion(audiencia, usuario):
        """
        Registra la creación de "audiencia" (ya guardada, con
        pk asignado). valoresAnteriores queda en None: no
        existían valores previos.
        """
        return RegistroTrazabilidad.objects.create(
            audiencia=audiencia,
            usuario=usuario,
            accion=AccionTrazabilidad.CREACION,
            valoresAnteriores=None,
            valoresNuevos=ServicioTrazabilidad.fotografiar(audiencia),
        )

    @staticmethod
    def registrarModificacion(audiencia, usuario, valoresAnteriores):
        """
        Registra una modificación ya aplicada y guardada sobre
        "audiencia". valoresAnteriores debe ser la fotografía
        que el llamador tomó ANTES de aplicar los cambios (ver
        docstring de la clase).
        """
        return RegistroTrazabilidad.objects.create(
            audiencia=audiencia,
            usuario=usuario,
            accion=AccionTrazabilidad.MODIFICACION,
            valoresAnteriores=valoresAnteriores,
            valoresNuevos=ServicioTrazabilidad.fotografiar(audiencia),
        )

    @staticmethod
    def registrarBaja(audiencia, usuario, valoresAnteriores):
        """
        Registra una baja lógica ya aplicada y guardada sobre
        "audiencia" (se espera estado=ELIMINADA y motivoBaja
        poblado, pero este servicio no lo exige ni lo aplica:
        solo fotografía lo que encuentra). valoresAnteriores
        debe ser la fotografía que el llamador tomó ANTES de
        la baja.
        """
        return RegistroTrazabilidad.objects.create(
            audiencia=audiencia,
            usuario=usuario,
            accion=AccionTrazabilidad.BAJA,
            valoresAnteriores=valoresAnteriores,
            valoresNuevos=ServicioTrazabilidad.fotografiar(audiencia),
        )


# =====================================================
# SERVICIO DE CREACIÓN DE AUDIENCIA
# =====================================================

class ServicioCreacionAudiencia:
    """
    Coordina el registro de una Audiencia nueva.

    RESPONSABILIDADES SEPARADAS (no se mezclan aquí):
    - GeneradorPropuestaFecha propone fechas/bloques (no se
      invoca desde este servicio: es una ayuda opcional de la
      interfaz, previa e independiente de la creación).
    - ValidadorAgendamiento valida (este servicio lo invoca,
      pero no reimplementa ninguna de sus reglas).
    - ServicioTrazabilidad registra la trazabilidad (este
      servicio lo invoca, pero no reimplementa la fotografía
      ni la creación de RegistroTrazabilidad).
    - ServicioCreacionAudiencia solo coordina el orden de esos
      pasos y decide cuándo guardar.

    FLUJO DE DOS INVOCACIONES (confirmación de advertencias):
    1) Primera llamada, con confirmarAdvertencias=False (por
       defecto). Si ValidadorAgendamiento devuelve
       advertencias y ningún error, NO se guarda nada; el
       resultado queda con requiereConfirmacion=True para que
       la View se lo muestre al funcionario.
    2) Si el funcionario confirma, la View vuelve a invocar
       este servicio con los mismos datos y
       confirmarAdvertencias=True. ValidadorAgendamiento se
       ejecuta DE NUEVO en esa segunda llamada (nunca se
       reutilizan las advertencias de la primera): si algo
       cambió entre medio (por ejemplo, otra audiencia ocupó
       ese bloque), el resultado puede ser distinto.

    Si bloqueInicio + cantidadBloques se sale del rango de
    BloqueHorario configurado, es un error bloqueante propio
    de este servicio (no se agrega a ValidadorAgendamiento):
    sin ese cálculo no se puede construir la Audiencia.
    """

    MENSAJE_BLOQUE_FUERA_DE_RANGO = (
        "No existe un bloque válido para calcular la hora de término."
    )

    def __init__(
        self,
        causa,
        tipoAudiencia,
        sala,
        cantidadBloques,
        fecha,
        bloqueInicio,
        usuario,
        fecha_referencia,
        confirmarAdvertencias=False,
    ):
        self.causa = causa
        self.tipoAudiencia = tipoAudiencia
        self.sala = sala
        self.cantidadBloques = cantidadBloques
        self.fecha = fecha
        self.bloqueInicio = bloqueInicio
        self.usuario = usuario
        self.fecha_referencia = fecha_referencia
        self.confirmarAdvertencias = confirmarAdvertencias

    # =================================================
    # PUNTO DE ENTRADA
    # =================================================

    def crear(self):
        """
        Devuelve:
            {
                "guardada": bool,
                "requiereConfirmacion": bool,
                "audiencia": Audiencia | None,
                "errores": [...],
                "advertencias": [...],
                "registroTrazabilidad": RegistroTrazabilidad | None,
            }
        """
        # ---------------------------------------------
        # Paso 1: calcular horaTermino a partir del bloque
        # final (bloqueInicio.orden + cantidadBloques - 1).
        # Si bloqueInicio/cantidadBloques faltan o son
        # inválidos, no se hace este chequeo aquí: queda en
        # manos de ValidadorAgendamiento (_validarDatosObligatorios),
        # que ya reporta "falta indicar el bloque de inicio" /
        # "la cantidad de bloques debe ser al menos 1".
        # ---------------------------------------------

        bloque_final = None

        if self.bloqueInicio is not None and self.cantidadBloques and self.cantidadBloques >= 1:
            orden_final = self.bloqueInicio.orden + self.cantidadBloques - 1
            bloque_final = BloqueHorario.objects.filter(orden=orden_final).first()

            if bloque_final is None:
                return self._resultadoBloqueado(
                    errores=[self.MENSAJE_BLOQUE_FUERA_DE_RANGO]
                )

        # ---------------------------------------------
        # Paso 2: construir la Audiencia SIN GUARDAR, con las
        # horas ya calculadas (quedarán congeladas: una vez
        # asignadas aquí, nada las vuelve a recalcular).
        # ---------------------------------------------

        audiencia = Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipoAudiencia,
            sala=self.sala,
            bloqueInicio=self.bloqueInicio,
            cantidadBloques=self.cantidadBloques,
            fecha=self.fecha,
            horaInicio=self.bloqueInicio.horaInicio if self.bloqueInicio else None,
            horaTermino=bloque_final.horaTermino if bloque_final else None,
            usuarioCreacion=self.usuario,
        )

        # ---------------------------------------------
        # Paso 3: validar. Se ejecuta SIEMPRE, en cada llamada
        # a crear() -incluida la segunda, con
        # confirmarAdvertencias=True-, sin cachear ni asumir
        # que las advertencias de una llamada anterior siguen
        # vigentes.
        # ---------------------------------------------

        resultado_validacion = ValidadorAgendamiento(
            audiencia, self.fecha_referencia
        ).validar()

        errores = resultado_validacion["errores"]
        advertencias = resultado_validacion["advertencias"]

        if errores:
            return self._resultadoBloqueado(errores=errores, advertencias=advertencias)

        if advertencias and not self.confirmarAdvertencias:
            return {
                "guardada": False,
                "requiereConfirmacion": True,
                "audiencia": None,
                "errores": [],
                "advertencias": advertencias,
                "registroTrazabilidad": None,
            }

        # ---------------------------------------------
        # Paso 4: guardar y registrar trazabilidad como una
        # única operación transaccional. Si registrarCreacion
        # falla, transaction.atomic() revierte también el
        # audiencia.save() de esta misma transacción.
        # ---------------------------------------------

        with transaction.atomic():
            audiencia.save()
            registro = ServicioTrazabilidad.registrarCreacion(audiencia, self.usuario)

        return {
            "guardada": True,
            "requiereConfirmacion": False,
            "audiencia": audiencia,
            "errores": [],
            "advertencias": advertencias,
            "registroTrazabilidad": registro,
        }

    # =================================================
    # AUXILIARES
    # =================================================

    def _resultadoBloqueado(self, errores, advertencias=None):
        """
        Arma el resultado para el caso "no se guarda por
        errores": ni Audiencia ni RegistroTrazabilidad se
        crean.
        """
        return {
            "guardada": False,
            "requiereConfirmacion": False,
            "audiencia": None,
            "errores": errores,
            "advertencias": advertencias or [],
            "registroTrazabilidad": None,
        }
