"""
Prueba automatizada de la Prueba 3 del proyecto de título:
"Registros incompletos o inválidos".

Evalúa la capacidad real del sistema para RECHAZAR intentos de
registro de Audiencia con datos obligatorios faltantes o
inválidos, a través de su punto de entrada real
(reverse("registrar_audiencia"), invocado con
self.client.post(...)), tal como los usa un funcionario real -no
se invoca AudienciaForm ni ServicioCreacionAudiencia directamente-.

REGLA DE DISEÑO CENTRAL (confirmada con el usuario antes de
escribir este archivo): esta prueba NO mide "registros
incompletos guardados" (el sistema ya garantiza que eso nunca
ocurre, por diseño del modelo y del formulario). Mide, en cambio,
si cada intento inválido queda efectivamente BLOQUEADO antes de
poder guardarse. Por eso distingue explícitamente:

- Condiciones BLOQUEANTES (forman parte de los 15 casos
  principales, cuentan para el porcentaje de esta prueba):
  campo obligatorio faltante, opción fuera de las choices
  restringidas (incluye salas/competencias/tipos de audiencia
  inactivos, porque AudienciaForm ya los excluye de su queryset),
  formato de fecha inválido, causa inexistente
  (_resolver_causa), y bloqueInicio+cantidadBloques fuera del
  horario configurado (ServicioCreacionAudiencia).
- Condiciones de ADVERTENCIA no bloqueante (ValidadorAgendamiento.
  validarConflicto/validarPlazoLegal/validarDiaHabil): NO se
  cuentan como "rechazadas" en esta prueba, porque el sistema
  permite confirmarlas y guardar la audiencia igual. Se incluye
  un caso de control aparte (fuera del conteo de 15) que
  demuestra exactamente esa distinción con el propio sistema
  real: advertencia -> no se guarda sin confirmar -> se guarda
  al confirmar.

REGLAS DE DISEÑO GENERALES (mismas que test_metrica_propuesta_
automatica.py y test_prueba_2_trazabilidad.py):

- No usa la base de datos real del proyecto: corre sobre la base
  de datos de pruebas que Django crea y destruye automáticamente
  (TestCase).
- No depende de datos precargados: todos los datos se crean
  dentro de este mismo archivo.
- No modifica audiencias/forms.py, audiencias/views.py,
  audiencias/services.py, ningún modelo ni ningún archivo de
  prueba existente: solo agrega este archivo nuevo.
- Los 15 casos principales, el control válido y el control de
  advertencia se ejecutan mediante reverse("registrar_audiencia"),
  el mismo y único punto de entrada real de registro de
  audiencias.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime
import os

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from audiencias.models import AccionTrazabilidad, Audiencia, RegistroTrazabilidad
from bloques.models import BloqueHorario
from causas.models import Causa
from competencias.models import Competencia
from reglas_agendamiento.models import DiaAtencion, DiaSemana, ReglaAgendamiento, TipoPlazo
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia
from usuarios.models import Usuario


# =====================================================
# CONSTANTES DE LA PRUEBA
# =====================================================

CRITERIO_PORCENTAJE_MINIMO = 100  # exacto: ni un solo caso puede fallar
TOTAL_CASOS_INVALIDOS = 15

RUTA_EVIDENCIA = os.path.join(
    os.path.dirname(__file__),
    "evidencia_prueba_3_registros_invalidos.txt",
)

DIAS_LUNES_A_VIERNES = [
    DiaSemana.LUNES,
    DiaSemana.MARTES,
    DiaSemana.MIERCOLES,
    DiaSemana.JUEVES,
    DiaSemana.VIERNES,
]

# Cifra real del levantamiento del proceso anterior al sistema,
# usada únicamente como contexto en la evidencia (sección
# "Antes/Después"), tal como lo pidió el usuario: no se compara
# matemáticamente contra el porcentaje de esta prueba, porque
# miden fenómenos distintos (ver docstring del módulo).
AUDIENCIAS_INCOMPLETAS_PROCESO_ANTERIOR = 52
TOTAL_AUDIENCIAS_PROCESO_ANTERIOR = 174


def _siguientes_fechas_habiles(fecha_inicial, cantidad):
    """
    Devuelve "cantidad" fechas estrictamente posteriores a
    fecha_inicial, correspondientes a días hábiles de atención
    (lunes a viernes, los únicos valores que existen en
    DiaSemana), en orden cronológico ascendente. Mismo criterio
    que test_prueba_2_trazabilidad.py, definido aquí de forma
    independiente porque este archivo no debe depender de otro
    archivo de test para su propia fixture.
    """
    fechas = []
    fecha = fecha_inicial
    while len(fechas) < cantidad:
        fecha += datetime.timedelta(days=1)
        if fecha.weekday() < 5:  # 0=lunes ... 4=viernes
            fechas.append(fecha)
    return fechas


# =====================================================
# PRUEBA
# =====================================================

class Prueba3RegistrosInvalidosTests(TestCase):
    """
    Ejecuta 15 intentos de registro de audiencia deliberadamente
    inválidos (uno por cada condición bloqueante real e
    independiente identificada en AudienciaForm, _resolver_causa
    y ServicioCreacionAudiencia), más un caso de control válido y
    un caso de control de advertencia no bloqueante, contra el
    punto de entrada HTTP real registrar_audiencia.
    """

    @classmethod
    def setUpTestData(cls):
        # Usuario real de prueba, con el que se inicia sesión
        # (force_login) antes de cada solicitud.
        cls.usuario = Usuario.objects.create(
            nombre="Usuario de prueba - registros invalidos",
            email="prueba3.registrosinvalidos@example.com",
        )

        # ---------------------------------------------------
        # Catálogos para el registro BASE válido y para los 15
        # casos inválidos (todos, salvo donde se indica lo
        # contrario, comparten estos mismos catálogos activos).
        # ---------------------------------------------------

        cls.competencia_activa = Competencia.objects.create(
            nombre="Competencia registros invalidos", activa=True
        )
        cls.tipo_activo = TipoAudiencia.objects.create(
            nombre="Tipo de audiencia registros invalidos", activo=True
        )
        cls.sala_activa = Sala.objects.create(
            nombre="Sala registros invalidos", activa=True
        )

        # Catálogos INACTIVOS, exclusivamente para los casos 09,
        # 10 y 11 (sala/competencia/tipoAudiencia inactivos):
        # AudienciaForm restringe sus querysets a activa=True/
        # activo=True, así que un pk de estos catálogos siempre
        # queda fuera de las opciones válidas del formulario.
        cls.sala_inactiva = Sala.objects.create(
            nombre="Sala inactiva registros invalidos", activa=False
        )
        cls.competencia_inactiva = Competencia.objects.create(
            nombre="Competencia inactiva registros invalidos", activa=False
        )
        cls.tipo_inactivo = TipoAudiencia.objects.create(
            nombre="Tipo inactivo registros invalidos", activo=False
        )

        # Día de atención lunes a viernes y regla de plazo amplia
        # para la competencia/tipo activos: el registro BASE (y
        # los 15 casos inválidos, que parten de él) no debe
        # generar ninguna advertencia, para no confundir un
        # bloqueo real con una advertencia no bloqueante.
        for dia in DIAS_LUNES_A_VIERNES:
            DiaAtencion.objects.create(
                competencia=cls.competencia_activa, diaSemana=dia, activa=True
            )
        ReglaAgendamiento.objects.create(
            competencia=cls.competencia_activa,
            tipoAudiencia=cls.tipo_activo,
            plazoMinimo=1,
            plazoMaximo=365,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )

        # Solo 3 bloques horarios configurados (orden 1, 2 y 3):
        # a propósito pocos, para que el caso 15 (bloqueInicio +
        # cantidadBloques que excede el horario configurado)
        # pueda construirse eligiendo el último bloque real con
        # una cantidadBloques válida (1-10) que de todos modos
        # exceda el rango.
        cls.bloque_1 = BloqueHorario.objects.create(
            horaInicio=datetime.time(8, 0), horaTermino=datetime.time(8, 30),
            orden=1, permiteAgendamientoAutomatico=True,
        )
        cls.bloque_2 = BloqueHorario.objects.create(
            horaInicio=datetime.time(8, 30), horaTermino=datetime.time(9, 0),
            orden=2, permiteAgendamientoAutomatico=True,
        )
        cls.bloque_3 = BloqueHorario.objects.create(
            horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            orden=3, permiteAgendamientoAutomatico=True,
        )

        # pk que no corresponde a ningún BloqueHorario real
        # (usado por el caso 12), calculado en vez de un número
        # fijo, para no depender de qué pk concreto haya asignado
        # la base de datos.
        cls.pk_bloque_inexistente = (
            max(cls.bloque_1.pk, cls.bloque_2.pk, cls.bloque_3.pk) + 9999
        )

        # Causa real para el registro BASE y para los 15 casos
        # inválidos (ninguno de los 15 llega a guardarse, así que
        # no hay riesgo de "unique_causa_por_competencia_y_rit").
        cls.causa_base = Causa.objects.create(
            competencia=cls.competencia_activa,
            rit="C-BASE-TRZ3",
            ruc="RUC-BASE-TRZ3",
            caratulado="Causa de prueba registros invalidos (base)",
        )

        # ---------------------------------------------------
        # Catálogos EXCLUSIVOS para el caso de control de
        # advertencia no bloqueante: una competencia/tipo propios,
        # con una ReglaAgendamiento deliberadamente estrecha
        # (plazoMaximo=2), para poder elegir una fecha realmente
        # fuera de ese plazo sin afectar en nada a los 15 casos
        # bloqueantes (que usan la regla amplia de arriba).
        # ---------------------------------------------------

        cls.competencia_advertencia = Competencia.objects.create(
            nombre="Competencia control advertencia", activa=True
        )
        cls.tipo_advertencia = TipoAudiencia.objects.create(
            nombre="Tipo de audiencia control advertencia", activo=True
        )
        for dia in DIAS_LUNES_A_VIERNES:
            DiaAtencion.objects.create(
                competencia=cls.competencia_advertencia, diaSemana=dia, activa=True
            )
        ReglaAgendamiento.objects.create(
            competencia=cls.competencia_advertencia,
            tipoAudiencia=cls.tipo_advertencia,
            plazoMinimo=1,
            plazoMaximo=2,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )
        cls.causa_advertencia = Causa.objects.create(
            competencia=cls.competencia_advertencia,
            rit="C-ADVERTENCIA-TRZ3",
            ruc="RUC-ADVERTENCIA-TRZ3",
            caratulado="Causa de prueba control de advertencia",
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    # =================================================
    # HELPERS
    # =================================================

    def _datos_base(self, fecha):
        """
        Devuelve un diccionario NUEVO (una copia) con un registro
        de audiencia válido, listo para POST a
        reverse("registrar_audiencia"). Cada uno de los 15 casos
        parte de esta misma base y altera solamente el campo que
        le corresponde (ver docstring del módulo).
        """
        return {
            "competencia": self.competencia_activa.pk,
            "rit": self.causa_base.rit,
            "tipoAudiencia": self.tipo_activo.pk,
            "sala": self.sala_activa.pk,
            "cantidadBloques": "1",
            "fecha": fecha.isoformat(),
            "bloqueInicio": self.bloque_1.pk,
            "anotacion": "",
        }

    def _registrar_caso(self, resultados, numero, descripcion, ok, detalle):
        resultados.append(
            {"numero": numero, "descripcion": descripcion, "ok": ok, "detalle": detalle}
        )
        with self.subTest(caso=numero, descripcion=descripcion):
            self.assertTrue(ok, detalle)

    def _verificar_rechazo(
        self, respuesta, audiencias_antes, registros_antes, espera_errores_formulario
    ):
        """
        Oráculo común a los 15 casos inválidos: un intento
        correctamente rechazado nunca redirige (siempre vuelve a
        mostrar el formulario, status 200), nunca crea una
        Audiencia y nunca crea un RegistroTrazabilidad.
        """
        if respuesta.status_code != 200:
            return False, (
                f"Se esperaba status 200 (formulario re-mostrado con "
                f"errores) y se obtuvo {respuesta.status_code}."
            )
        if Audiencia.objects.count() != audiencias_antes:
            return False, "Se creó una Audiencia pese a que el intento debía ser rechazado."
        if RegistroTrazabilidad.objects.count() != registros_antes:
            return False, "Se creó un RegistroTrazabilidad pese a que el intento debía ser rechazado."

        if espera_errores_formulario:
            form_en_contexto = respuesta.context.get("form") if respuesta.context else None
            if form_en_contexto is None or not form_en_contexto.errors:
                return False, (
                    "Se esperaban errores de AudienciaForm (rechazo a nivel "
                    "de formulario) y no se encontró ninguno."
                )

        return True, "OK"

    def _verificar_creacion_exitosa(self, respuesta, causa, audiencias_antes, registros_antes):
        """
        Oráculo del caso de control válido (y del segundo paso del
        control de advertencia): la audiencia debe quedar
        realmente creada, con exactamente 1 RegistroTrazabilidad
        CREACION nuevo.
        """
        if respuesta.status_code != 302:
            return False, f"Se esperaba una redirección 302 y se obtuvo {respuesta.status_code}."

        audiencia = Audiencia.objects.filter(causa=causa).order_by("-fechaCreacion").first()
        if audiencia is None:
            return False, "No se encontró ninguna Audiencia creada para esta causa."
        if Audiencia.objects.count() != audiencias_antes + 1:
            return False, "No se creó exactamente 1 Audiencia nueva."

        registros = list(
            RegistroTrazabilidad.objects.filter(
                audiencia=audiencia, accion=AccionTrazabilidad.CREACION
            )
        )
        if len(registros) != 1:
            return False, f"Se esperaba 1 RegistroTrazabilidad de CREACION y hay {len(registros)}."
        if RegistroTrazabilidad.objects.count() != registros_antes + 1:
            return False, "Se crearon más registros de trazabilidad de los esperados."

        return True, "OK"

    # =================================================
    # PRUEBA PRINCIPAL
    # =================================================

    def test_prueba_3_registros_invalidos_15_casos(self):
        resultados = []

        fechas = _siguientes_fechas_habiles(timezone.localdate(), 10)
        fecha_base = fechas[0]
        fecha_fuera_de_plazo = fechas[9]  # muy por encima del plazoMaximo=2 del control de advertencia

        # ---------------------------------------------------
        # CASO 00 (control, fuera del conteo de 15): un registro
        # exactamente válido debe guardarse y generar su
        # trazabilidad. Si este caso fallara, el problema estaría
        # en los datos de esta prueba, no en el sistema.
        # ---------------------------------------------------

        casos_control = []

        audiencias_antes = Audiencia.objects.count()
        registros_antes = RegistroTrazabilidad.objects.count()
        respuesta_control = self.client.post(
            reverse("registrar_audiencia"), self._datos_base(fecha_base)
        )
        ok_control, detalle_control = self._verificar_creacion_exitosa(
            respuesta_control, self.causa_base, audiencias_antes, registros_antes
        )
        casos_control.append(
            {"nombre": "Caso 00 - Control: registro válido", "ok": ok_control, "detalle": detalle_control}
        )
        with self.subTest(caso="00-control-valido"):
            self.assertTrue(ok_control, detalle_control)

        # ---------------------------------------------------
        # LOS 15 CASOS PRINCIPALES (cuentan para el porcentaje)
        # ---------------------------------------------------

        casos = [
            {
                "numero": 1,
                "descripcion": "Fecha faltante",
                "mutar": lambda datos: datos.pop("fecha", None),
                "espera_errores_formulario": True,
            },
            {
                "numero": 2,
                "descripcion": "Competencia faltante",
                "mutar": lambda datos: datos.pop("competencia", None),
                "espera_errores_formulario": True,
            },
            {
                "numero": 3,
                "descripcion": "RIT vacío",
                "mutar": lambda datos: datos.__setitem__("rit", ""),
                "espera_errores_formulario": True,
            },
            {
                "numero": 4,
                "descripcion": "Tipo de audiencia faltante",
                "mutar": lambda datos: datos.pop("tipoAudiencia", None),
                "espera_errores_formulario": True,
            },
            {
                "numero": 5,
                "descripcion": "Sala faltante",
                "mutar": lambda datos: datos.pop("sala", None),
                "espera_errores_formulario": True,
            },
            {
                "numero": 6,
                "descripcion": "Bloque de inicio faltante",
                "mutar": lambda datos: datos.pop("bloqueInicio", None),
                "espera_errores_formulario": True,
            },
            {
                "numero": 7,
                "descripcion": "Cantidad de bloques faltante",
                "mutar": lambda datos: datos.pop("cantidadBloques", None),
                "espera_errores_formulario": True,
            },
            {
                "numero": 8,
                "descripcion": "Cantidad de bloques inválida (fuera de 1-10)",
                "mutar": lambda datos: datos.__setitem__("cantidadBloques", "0"),
                "espera_errores_formulario": True,
            },
            {
                "numero": 9,
                "descripcion": "Sala inactiva",
                "mutar": lambda datos: datos.__setitem__("sala", self.sala_inactiva.pk),
                "espera_errores_formulario": True,
            },
            {
                "numero": 10,
                "descripcion": "Competencia inactiva",
                "mutar": lambda datos: datos.__setitem__("competencia", self.competencia_inactiva.pk),
                "espera_errores_formulario": True,
            },
            {
                "numero": 11,
                "descripcion": "Tipo de audiencia inactivo",
                "mutar": lambda datos: datos.__setitem__("tipoAudiencia", self.tipo_inactivo.pk),
                "espera_errores_formulario": True,
            },
            {
                "numero": 12,
                "descripcion": "Bloque de inicio inexistente",
                "mutar": lambda datos: datos.__setitem__("bloqueInicio", self.pk_bloque_inexistente),
                "espera_errores_formulario": True,
            },
            {
                "numero": 13,
                "descripcion": "Fecha con formato inválido",
                "mutar": lambda datos: datos.__setitem__("fecha", "no-es-una-fecha"),
                "espera_errores_formulario": True,
            },
            {
                "numero": 14,
                "descripcion": "Causa inexistente",
                "mutar": lambda datos: datos.__setitem__("rit", "RIT-INEXISTENTE-9999"),
                "espera_errores_formulario": False,
            },
            {
                "numero": 15,
                "descripcion": "Bloque de inicio + cantidad de bloques fuera del horario configurado",
                "mutar": lambda datos: (
                    datos.__setitem__("bloqueInicio", self.bloque_3.pk),
                    datos.__setitem__("cantidadBloques", "5"),
                ),
                "espera_errores_formulario": False,
            },
        ]

        for caso in casos:
            datos = self._datos_base(fecha_base)
            caso["mutar"](datos)

            audiencias_antes = Audiencia.objects.count()
            registros_antes = RegistroTrazabilidad.objects.count()

            respuesta = self.client.post(reverse("registrar_audiencia"), datos)

            ok, detalle = self._verificar_rechazo(
                respuesta, audiencias_antes, registros_antes, caso["espera_errores_formulario"]
            )
            self._registrar_caso(resultados, caso["numero"], caso["descripcion"], ok, detalle)

        # ---------------------------------------------------
        # CÁLCULO DE LA MÉTRICA (sobre los 15 casos)
        # ---------------------------------------------------

        casos_correctos = sum(1 for r in resultados if r["ok"])
        casos_incorrectos = TOTAL_CASOS_INVALIDOS - casos_correctos
        porcentaje = round((casos_correctos / TOTAL_CASOS_INVALIDOS) * 100, 2)
        cumple = porcentaje == CRITERIO_PORCENTAJE_MINIMO

        # ---------------------------------------------------
        # CASO DE CONTROL: ADVERTENCIA NO BLOQUEANTE (fuera del
        # conteo de 15). Demuestra, con el sistema real, que una
        # advertencia (fecha fuera del plazo legal configurado)
        # NO bloquea el registro: primero no se guarda sin
        # confirmar, y luego SÍ se guarda al confirmar.
        # ---------------------------------------------------

        datos_advertencia = {
            "competencia": self.competencia_advertencia.pk,
            "rit": self.causa_advertencia.rit,
            "tipoAudiencia": self.tipo_advertencia.pk,
            "sala": self.sala_activa.pk,
            "cantidadBloques": "1",
            "fecha": fecha_fuera_de_plazo.isoformat(),
            "bloqueInicio": self.bloque_1.pk,
            "anotacion": "",
        }

        # Paso 1: sin confirmar_advertencias. Debe requerir
        # confirmación y NO guardar nada todavía.
        audiencias_antes_adv = Audiencia.objects.count()
        registros_antes_adv = RegistroTrazabilidad.objects.count()
        respuesta_advertencia = self.client.post(
            reverse("registrar_audiencia"), datos_advertencia
        )

        ok_paso1 = (
            respuesta_advertencia.status_code == 200
            and bool(respuesta_advertencia.context.get("requiere_confirmacion"))
            and bool(respuesta_advertencia.context.get("advertencias"))
            and Audiencia.objects.count() == audiencias_antes_adv
            and RegistroTrazabilidad.objects.count() == registros_antes_adv
        )
        casos_control.append(
            {
                "nombre": "Control de advertencia - paso 1 (advertencia, sin confirmar, no se guarda)",
                "ok": ok_paso1,
                "detalle": (
                    "OK"
                    if ok_paso1
                    else "La respuesta no coincide con el flujo real de advertencia sin confirmar."
                ),
            }
        )
        with self.subTest(caso="control-advertencia-paso-1"):
            self.assertTrue(ok_paso1, "Fallo en el paso 1 del control de advertencia.")

        # Paso 2: con confirmar_advertencias=1. Debe guardarse y
        # generar su trazabilidad de CREACION.
        datos_confirmacion = dict(datos_advertencia)
        datos_confirmacion["confirmar_advertencias"] = "1"

        audiencias_antes_conf = Audiencia.objects.count()
        registros_antes_conf = RegistroTrazabilidad.objects.count()
        respuesta_confirmacion = self.client.post(
            reverse("registrar_audiencia"), datos_confirmacion
        )

        ok_paso2, detalle_paso2 = self._verificar_creacion_exitosa(
            respuesta_confirmacion, self.causa_advertencia, audiencias_antes_conf, registros_antes_conf
        )
        casos_control.append(
            {
                "nombre": "Control de advertencia - paso 2 (confirmada, se guarda)",
                "ok": ok_paso2,
                "detalle": detalle_paso2,
            }
        )
        with self.subTest(caso="control-advertencia-paso-2"):
            self.assertTrue(ok_paso2, detalle_paso2)

        # ---------------------------------------------------
        # EVIDENCIA + VEREDICTO
        # ---------------------------------------------------

        self._escribir_evidencia(
            resultados, casos_correctos, casos_incorrectos, porcentaje, cumple, casos_control
        )

        self.assertEqual(
            porcentaje,
            CRITERIO_PORCENTAJE_MINIMO,
            (
                f"Prueba 3 (Registros incompletos/inválidos) NO CUMPLE: {porcentaje}% "
                f"(criterio: {CRITERIO_PORCENTAJE_MINIMO}% exacto). "
                f"Ver {RUTA_EVIDENCIA} para el detalle por caso."
            ),
        )

    # =================================================
    # EVIDENCIA
    # =================================================

    def _escribir_evidencia(
        self, resultados, casos_correctos, casos_incorrectos, porcentaje, cumple, casos_control
    ):
        lineas = []
        lineas.append(
            f"Ejecutado: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lineas.append("")

        for r in resultados:
            lineas.append(f"Caso {r['numero']:02d} – {r['descripcion']} → {'OK' if r['ok'] else 'FALLA'}")
            if not r["ok"]:
                lineas.append(f"    {r['detalle']}")

        lineas.append("")
        lineas.append("PRUEBA 3 – REGISTROS INCOMPLETOS / INVÁLIDOS")
        lineas.append("==============================================")
        lineas.append(f"Intentos inválidos evaluados: {TOTAL_CASOS_INVALIDOS}")
        lineas.append(f"Intentos correctamente rechazados: {casos_correctos}")
        lineas.append(f"Intentos aceptados incorrectamente: {casos_incorrectos}")
        lineas.append(f"Porcentaje de rechazo correcto: {porcentaje} %")
        lineas.append(f"Criterio: {CRITERIO_PORCENTAJE_MINIMO} %")
        lineas.append(f"Resultado: {'CUMPLE' if cumple else 'NO CUMPLE'}")

        lineas.append("")
        lineas.append("CASOS DE CONTROL (fuera del cálculo de la métrica)")
        lineas.append("-----------------------------------------------------")
        for extra in casos_control:
            lineas.append(f"{extra['nombre']} → {'OK' if extra['ok'] else 'FALLA'}")
            if not extra["ok"]:
                lineas.append(f"    {extra['detalle']}")

        lineas.append("")
        lineas.append("CONTEXTO DEL PROYECTO (Antes / Después)")
        lineas.append("-----------------------------------------------------")
        porcentaje_antes = round(
            (AUDIENCIAS_INCOMPLETAS_PROCESO_ANTERIOR / TOTAL_AUDIENCIAS_PROCESO_ANTERIOR) * 100, 2
        )
        lineas.append(
            f"Antes (proceso manual, levantamiento previo): "
            f"{AUDIENCIAS_INCOMPLETAS_PROCESO_ANTERIOR}/{TOTAL_AUDIENCIAS_PROCESO_ANTERIOR} "
            f"audiencias (~{porcentaje_antes} %) presentaban al menos un dato incompleto."
        )
        lineas.append(
            f"Después (sistema, esta prueba automatizada): {porcentaje} % de los intentos "
            f"inválidos evaluados ({casos_correctos}/{TOTAL_CASOS_INVALIDOS}) fueron rechazados "
            f"correctamente por el sistema antes de poder guardarse."
        )
        lineas.append(
            "Nota: estas dos cifras miden fenómenos distintos (proporción histórica de "
            "registros incompletos vs. capacidad del sistema actual de rechazar intentos "
            "inválidos); se presentan juntas solo como contexto del proyecto, no como una "
            "comparación matemática directa."
        )

        contenido = "\n".join(lineas) + "\n"

        with open(RUTA_EVIDENCIA, "w", encoding="utf-8") as archivo:
            archivo.write(contenido)

        # La consola de Windows suele usar cp1252, que no puede
        # representar "–"/"→"; si falla, se imprime un equivalente
        # en ASCII solo para no interrumpir la ejecución (el
        # archivo de evidencia siempre conserva el formato exacto
        # en UTF-8).
        try:
            print("\n" + contenido)
        except UnicodeEncodeError:
            print("\n" + contenido.replace("–", "-").replace("→", "->"))
