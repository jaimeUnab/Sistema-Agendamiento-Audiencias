"""
Prueba automatizada de la Prueba 2 del proyecto de título:
"Trazabilidad".

Evalúa que las operaciones reales del sistema sobre Audiencia
(crear, dejar sin efecto, guardar anotación) queden correctamente
registradas en RegistroTrazabilidad (audiencias/models.py), a
través de sus puntos de entrada reales (las URLs de
audiencias/urls.py, invocadas con self.client.post(reverse(...))),
tal como los usa un funcionario real -no se invoca ningún servicio
de audiencias/services.py directamente-.

REGLAS DE DISEÑO DE ESTA PRUEBA:

- No usa la base de datos real del proyecto: corre sobre la base
  de datos de pruebas que Django crea y destruye automáticamente
  (TestCase), igual que el resto de los archivos de este paquete.
- No depende de datos precargados: todos los datos (Competencia,
  TipoAudiencia, Sala, DiaAtencion, ReglaAgendamiento,
  BloqueHorario, Causa, Usuario) se crean dentro de este mismo
  archivo.
- No modifica audiencias/services.py, ningún modelo, ninguna vista
  ni ningún archivo de prueba existente: solo agrega este archivo
  nuevo.
- Las 30 operaciones se ejecutan mediante los puntos de entrada
  HTTP reales:
    * reverse("registrar_audiencia")         (crear audiencia)
    * reverse("guardar_anotacion_audiencia")  (guardar anotación)
    * reverse("dejar_sin_efecto_audiencia")   (dejar sin efecto)
  exactamente los nombres definidos en audiencias/urls.py.
- La fecha de cada audiencia se calcula en relación con
  timezone.localdate() (la misma fuente de "hoy" que usa
  audiencias/views.py:registrar_audiencia para
  fecha_referencia), buscando los próximos días hábiles
  (lunes a viernes, los únicos valores de DiaSemana), para que el
  resultado no dependa de en qué día del calendario se ejecute la
  prueba, sin necesitar confirmar advertencias de agendamiento
  (fuera del alcance de esta prueba: aquí se evalúa la
  trazabilidad, no las reglas de ValidadorAgendamiento).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime
import os

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from audiencias.forms import MotivoBaja
from audiencias.models import AccionTrazabilidad, Audiencia, EstadoAudiencia, RegistroTrazabilidad
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

CRITERIO_PORCENTAJE_MINIMO = 99  # estrictamente mayor (>), no >=
TOTAL_OPERACIONES = 30
CANTIDAD_AUDIENCIAS = 10

RUTA_EVIDENCIA = os.path.join(
    os.path.dirname(__file__),
    "evidencia_prueba_2_trazabilidad.txt",
)

# Ciclo de motivos reales de MotivoBaja (audiencias/forms.py),
# usado para variar el motivo entre las 10 bajas de la fase 3.
MOTIVOS_BAJA_CICLO = [
    MotivoBaja.SUSPENSION,
    MotivoBaja.REPROGRAMACION,
    MotivoBaja.ERROR_AGENDAMIENTO,
    MotivoBaja.SOLICITUD_TRIBUNAL,
    MotivoBaja.OTRO,
]

DIAS_LUNES_A_VIERNES = [
    DiaSemana.LUNES,
    DiaSemana.MARTES,
    DiaSemana.MIERCOLES,
    DiaSemana.JUEVES,
    DiaSemana.VIERNES,
]

# Anotación con la que nace cada una de las 10 audiencias (fase 1).
# Por defecto nace vacía; las audiencias 08, 09 y 10 nacen con una
# anotación ya cargada, para poder ejercitar en la fase 2 los tres
# casos reales de guardar_anotacion_audiencia: anotación nueva
# (audiencias 01-07), anotación que reemplaza una anterior
# (audiencias 08 y 09) y anotación vaciada (audiencia 10).
ANOTACIONES_INICIALES = {
    8: "Anotación inicial de la audiencia 08",
    9: "Anotación inicial de la audiencia 09",
    10: "Anotación a eliminar de la audiencia 10",
}

# Anotación que se guarda en la fase 2 para cada una de las 10
# audiencias (ver ANOTACIONES_INICIALES arriba para el punto de
# partida de cada una).
ANOTACIONES_NUEVAS = {
    1: "Anotación registrada para la audiencia 01",
    2: "Anotación registrada para la audiencia 02",
    3: "Anotación registrada para la audiencia 03",
    4: "Anotación registrada para la audiencia 04",
    5: "Anotación registrada para la audiencia 05",
    6: "Anotación registrada para la audiencia 06",
    7: "Anotación registrada para la audiencia 07",
    8: "Anotación reemplazada para la audiencia 08",
    9: "Anotación reemplazada para la audiencia 09",
    10: "",
}


def _siguientes_fechas_habiles(fecha_inicial, cantidad):
    """
    Devuelve "cantidad" fechas estrictamente posteriores a
    fecha_inicial, correspondientes a días hábiles de atención
    (lunes a viernes -los únicos valores que existen en
    DiaSemana, reglas_agendamiento/models.py-), en orden
    cronológico ascendente. No depende de qué día de la semana
    sea "fecha_inicial": simplemente avanza día a día y descarta
    sábados/domingos.
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

class Prueba2TrazabilidadTests(TestCase):
    """
    Ejecuta 30 operaciones reales (10 creaciones, 10 anotaciones,
    10 bajas lógicas, encadenadas sobre las mismas 10 audiencias)
    contra los puntos de entrada HTTP reales de audiencias/urls.py,
    y calcula el porcentaje de operaciones correctamente trazadas
    en RegistroTrazabilidad.
    """

    @classmethod
    def setUpTestData(cls):
        # Usuario real de prueba, con el que se inicia sesión
        # (force_login) antes de cada solicitud: es el usuario que
        # debe quedar registrado como responsable en cada
        # RegistroTrazabilidad.
        cls.usuario = Usuario.objects.create(
            nombre="Usuario de prueba - trazabilidad",
            email="prueba2.trazabilidad@example.com",
        )

        # Catálogos mínimos, compartidos por las 10 audiencias:
        # una sola Competencia/TipoAudiencia/Sala es suficiente,
        # porque esta prueba evalúa el mecanismo de trazabilidad,
        # no las reglas de agendamiento (esas ya las evalúa la
        # Métrica 1, test_metrica_propuesta_automatica.py).
        cls.competencia = Competencia.objects.create(
            nombre="Competencia trazabilidad", activa=True
        )
        cls.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo de audiencia trazabilidad", activo=True
        )
        cls.sala = Sala.objects.create(nombre="Sala trazabilidad", activa=True)

        # Día de atención lunes a viernes, para que las fechas
        # elegidas (ver _siguientes_fechas_habiles) nunca generen
        # la advertencia "día no habitual de atención".
        for dia in DIAS_LUNES_A_VIERNES:
            DiaAtencion.objects.create(
                competencia=cls.competencia, diaSemana=dia, activa=True
            )

        # Plazo legal amplio (1 a 365 días corridos), para que
        # ninguna de las 10 fechas usadas (todas dentro de las
        # próximas ~2 semanas hábiles) genere la advertencia de
        # plazo legal.
        ReglaAgendamiento.objects.create(
            competencia=cls.competencia,
            tipoAudiencia=cls.tipo_audiencia,
            plazoMinimo=1,
            plazoMaximo=365,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )

        # Un único bloque horario (08:00-08:30, orden=1): todas
        # las audiencias de esta prueba usan cantidadBloques=1 y
        # fechas distintas entre sí, así que no hay ningún
        # conflicto de sala/bloque que generar ni evitar.
        cls.bloque = BloqueHorario.objects.create(
            horaInicio=datetime.time(8, 0),
            horaTermino=datetime.time(8, 30),
            orden=1,
            permiteAgendamientoAutomatico=True,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    # =================================================
    # HELPERS DE VERIFICACIÓN (oráculos independientes)
    # =================================================

    def _texto_motivo_esperado(self, motivo, motivo_otro_texto):
        """
        Recalcula, de forma independiente al código evaluado, el
        texto que DejarSinEfectoAudienciaForm.motivo_texto()
        debería producir para "motivo" (y, si corresponde,
        "motivo_otro_texto"), usando únicamente las etiquetas
        reales de MotivoBaja.
        """
        etiqueta = MotivoBaja(motivo).label
        if motivo == MotivoBaja.OTRO:
            return f"{etiqueta}: {motivo_otro_texto}"
        return etiqueta

    def _verificar_creacion(
        self, respuesta, audiencia, registros_antes, fecha_esperada, anotacion_esperada
    ):
        if respuesta.status_code != 302:
            return False, (
                f"La vista registrar_audiencia no redirigió tras crear la "
                f"audiencia (status {respuesta.status_code})."
            )
        if audiencia is None:
            return False, "No se creó ninguna Audiencia para este caso."
        if audiencia.estado != EstadoAudiencia.PROGRAMADA:
            return False, "La audiencia creada no quedó en estado PROGRAMADA."
        if audiencia.fecha != fecha_esperada:
            return False, "La fecha de la audiencia creada no coincide con la solicitada."
        if (audiencia.anotacion or "") != (anotacion_esperada or ""):
            return False, "La anotación inicial no coincide con la enviada."

        registros = list(
            RegistroTrazabilidad.objects.filter(
                audiencia=audiencia, accion=AccionTrazabilidad.CREACION
            )
        )
        if len(registros) != 1:
            return False, (
                f"Se esperaba exactamente 1 RegistroTrazabilidad de CREACION "
                f"y se encontraron {len(registros)}."
            )
        registro = registros[0]

        if registro.usuario_id != self.usuario.pk:
            return False, "El usuario del registro no es el usuario de prueba."
        if registro.audiencia_id != audiencia.pk:
            return False, "El registro no está asociado a la audiencia correcta."
        if registro.fechaHora is None:
            return False, "El registro no tiene fechaHora."
        if registro.valoresAnteriores is not None:
            return False, "Un registro de CREACION no debería tener valoresAnteriores."

        nuevos = registro.valoresNuevos or {}
        if nuevos.get("cantidadBloques") != audiencia.cantidadBloques:
            return False, "valoresNuevos no refleja la cantidadBloques real."
        if nuevos.get("fecha") != audiencia.fecha.isoformat():
            return False, "valoresNuevos no refleja la fecha real."
        if (nuevos.get("anotacion") or "") != (audiencia.anotacion or ""):
            return False, "valoresNuevos no refleja la anotación real."

        if RegistroTrazabilidad.objects.count() != registros_antes + 1:
            return False, "Esta operación creó más de un RegistroTrazabilidad."

        return True, "OK"

    def _verificar_anotacion(
        self, respuesta, audiencia, registros_antes, anotacion_anterior_esperada, anotacion_nueva_esperada
    ):
        if respuesta.status_code != 302:
            return False, (
                f"La vista guardar_anotacion_audiencia no redirigió "
                f"(status {respuesta.status_code})."
            )
        if (audiencia.anotacion or "") != (anotacion_nueva_esperada or ""):
            return False, "La anotación guardada no coincide con la enviada."

        registros = list(
            RegistroTrazabilidad.objects.filter(
                audiencia=audiencia, accion=AccionTrazabilidad.MODIFICACION
            )
        )
        if len(registros) != 1:
            return False, (
                f"Se esperaba exactamente 1 RegistroTrazabilidad de "
                f"MODIFICACION para esta audiencia y se encontraron "
                f"{len(registros)}."
            )
        registro = registros[0]

        if registro.usuario_id != self.usuario.pk:
            return False, "El usuario del registro no es el usuario de prueba."
        if registro.audiencia_id != audiencia.pk:
            return False, "El registro no está asociado a la audiencia correcta."
        if registro.fechaHora is None:
            return False, "El registro no tiene fechaHora."

        anteriores = registro.valoresAnteriores or {}
        nuevos = registro.valoresNuevos or {}
        if (anteriores.get("anotacion") or "") != (anotacion_anterior_esperada or ""):
            return False, "valoresAnteriores no refleja la anotación previa real."
        if (nuevos.get("anotacion") or "") != (anotacion_nueva_esperada or ""):
            return False, "valoresNuevos no refleja la anotación nueva real."

        if RegistroTrazabilidad.objects.count() != registros_antes + 1:
            return False, "Esta operación creó más de un RegistroTrazabilidad."

        return True, "OK"

    def _verificar_baja(self, respuesta, audiencia, registros_antes, motivo_esperado):
        if respuesta.status_code != 302:
            return False, (
                f"La vista dejar_sin_efecto_audiencia no redirigió "
                f"(status {respuesta.status_code})."
            )
        if audiencia.estado != EstadoAudiencia.ELIMINADA:
            return False, "La audiencia no quedó en estado ELIMINADA."
        if audiencia.motivoBaja != motivo_esperado:
            return False, "El motivo de baja guardado no coincide con el esperado."

        registros = list(
            RegistroTrazabilidad.objects.filter(
                audiencia=audiencia, accion=AccionTrazabilidad.BAJA
            )
        )
        if len(registros) != 1:
            return False, (
                f"Se esperaba exactamente 1 RegistroTrazabilidad de BAJA "
                f"para esta audiencia y se encontraron {len(registros)}."
            )
        registro = registros[0]

        if registro.usuario_id != self.usuario.pk:
            return False, "El usuario del registro no es el usuario de prueba."
        if registro.audiencia_id != audiencia.pk:
            return False, "El registro no está asociado a la audiencia correcta."
        if registro.fechaHora is None:
            return False, "El registro no tiene fechaHora."

        anteriores = registro.valoresAnteriores or {}
        nuevos = registro.valoresNuevos or {}
        if anteriores.get("estado") != EstadoAudiencia.PROGRAMADA:
            return False, "valoresAnteriores no refleja el estado PROGRAMADA previo."
        if nuevos.get("estado") != EstadoAudiencia.ELIMINADA:
            return False, "valoresNuevos no refleja el estado ELIMINADA nuevo."
        if nuevos.get("motivoBaja") != motivo_esperado:
            return False, "valoresNuevos no refleja el motivo de baja real."

        if RegistroTrazabilidad.objects.count() != registros_antes + 1:
            return False, "Esta operación creó más de un RegistroTrazabilidad."

        return True, "OK"

    def _registrar_caso(self, resultados, numero, descripcion, ok, detalle):
        resultados.append(
            {"numero": numero, "descripcion": descripcion, "ok": ok, "detalle": detalle}
        )
        with self.subTest(caso=numero, descripcion=descripcion):
            self.assertTrue(ok, detalle)

    # =================================================
    # PRUEBA PRINCIPAL
    # =================================================

    def test_prueba_2_trazabilidad_30_operaciones(self):
        resultados = []
        audiencias = {}  # número (1..10) -> Audiencia creada

        fechas = _siguientes_fechas_habiles(timezone.localdate(), CANTIDAD_AUDIENCIAS)

        # ---------------------------------------------------
        # FASE 1 (casos 01-10): crear audiencia, vía
        # reverse("registrar_audiencia").
        # ---------------------------------------------------

        for indice in range(1, CANTIDAD_AUDIENCIAS + 1):
            causa = Causa.objects.create(
                competencia=self.competencia,
                rit=f"C-{indice:02d}-TRZ",
                ruc=f"RUC-{indice:02d}-TRZ",
                caratulado=f"Causa de prueba trazabilidad {indice:02d}",
            )
            fecha = fechas[indice - 1]
            anotacion_inicial = ANOTACIONES_INICIALES.get(indice, "")

            datos_post = {
                "competencia": self.competencia.pk,
                "rit": causa.rit,
                "tipoAudiencia": self.tipo_audiencia.pk,
                "sala": self.sala.pk,
                "cantidadBloques": 1,
                "fecha": fecha.isoformat(),
                "bloqueInicio": self.bloque.pk,
                "anotacion": anotacion_inicial,
            }

            registros_antes = RegistroTrazabilidad.objects.count()
            respuesta = self.client.post(reverse("registrar_audiencia"), datos_post)
            audiencia = Audiencia.objects.filter(causa=causa).first()

            if audiencia is not None:
                audiencias[indice] = audiencia

            ok, detalle = self._verificar_creacion(
                respuesta, audiencia, registros_antes, fecha, anotacion_inicial
            )
            self._registrar_caso(
                resultados,
                indice,
                f"Crear audiencia (audiencia {indice:02d})",
                ok,
                detalle,
            )

        # ---------------------------------------------------
        # FASE 2 (casos 11-20): guardar anotación, vía
        # reverse("guardar_anotacion_audiencia").
        # ---------------------------------------------------

        for indice in range(1, CANTIDAD_AUDIENCIAS + 1):
            caso_numero = CANTIDAD_AUDIENCIAS + indice
            audiencia = audiencias.get(indice)
            anotacion_anterior = ANOTACIONES_INICIALES.get(indice, "")
            anotacion_nueva = ANOTACIONES_NUEVAS[indice]

            if audiencia is None:
                self._registrar_caso(
                    resultados,
                    caso_numero,
                    f"Guardar anotación (audiencia {indice:02d})",
                    False,
                    "No existe la audiencia de este caso (falló su creación en la fase 1).",
                )
                continue

            registros_antes = RegistroTrazabilidad.objects.count()
            respuesta = self.client.post(
                reverse("guardar_anotacion_audiencia"),
                {"audiencia_id": audiencia.pk, "anotacion": anotacion_nueva},
            )
            audiencia.refresh_from_db()

            ok, detalle = self._verificar_anotacion(
                respuesta, audiencia, registros_antes, anotacion_anterior, anotacion_nueva
            )
            self._registrar_caso(
                resultados,
                caso_numero,
                f"Guardar anotación (audiencia {indice:02d})",
                ok,
                detalle,
            )

        # ---------------------------------------------------
        # FASE 3 (casos 21-30): dejar sin efecto, vía
        # reverse("dejar_sin_efecto_audiencia").
        # ---------------------------------------------------

        for indice in range(1, CANTIDAD_AUDIENCIAS + 1):
            caso_numero = 2 * CANTIDAD_AUDIENCIAS + indice
            audiencia = audiencias.get(indice)
            motivo = MOTIVOS_BAJA_CICLO[(indice - 1) % len(MOTIVOS_BAJA_CICLO)]
            motivo_otro_texto = (
                f"Explicación de prueba para la audiencia {indice:02d}"
                if motivo == MotivoBaja.OTRO
                else ""
            )

            if audiencia is None:
                self._registrar_caso(
                    resultados,
                    caso_numero,
                    f"Dejar sin efecto (audiencia {indice:02d})",
                    False,
                    "No existe la audiencia de este caso (falló su creación en la fase 1).",
                )
                continue

            datos_post = {"audiencia_id": audiencia.pk, "motivo_seleccionado": motivo}
            if motivo == MotivoBaja.OTRO:
                datos_post["motivo_otro"] = motivo_otro_texto

            registros_antes = RegistroTrazabilidad.objects.count()
            respuesta = self.client.post(
                reverse("dejar_sin_efecto_audiencia"), datos_post
            )
            audiencia.refresh_from_db()

            motivo_esperado = self._texto_motivo_esperado(motivo, motivo_otro_texto)

            ok, detalle = self._verificar_baja(
                respuesta, audiencia, registros_antes, motivo_esperado
            )
            self._registrar_caso(
                resultados,
                caso_numero,
                f"Dejar sin efecto (audiencia {indice:02d})",
                ok,
                detalle,
            )

        # ---------------------------------------------------
        # CÁLCULO DE LA MÉTRICA (sobre las 30 operaciones)
        # ---------------------------------------------------

        casos_correctos = sum(1 for r in resultados if r["ok"])
        casos_incorrectos = TOTAL_OPERACIONES - casos_correctos
        porcentaje = round((casos_correctos / TOTAL_OPERACIONES) * 100, 2)
        cumple = porcentaje > CRITERIO_PORCENTAJE_MINIMO

        # ---------------------------------------------------
        # CASOS ADICIONALES (fuera del conteo de las 30
        # operaciones y de la fórmula de la métrica: no miden
        # "trazabilidad correcta de una operación realizada",
        # sino comportamientos complementarios pedidos aparte).
        # ---------------------------------------------------

        casos_adicionales = []

        # (a) Varias operaciones consecutivas generan varios
        # registros: cada una de las 10 audiencias debe terminar
        # con exactamente 3 RegistroTrazabilidad, en el orden
        # CREACION -> MODIFICACION -> BAJA.
        for indice in range(1, CANTIDAD_AUDIENCIAS + 1):
            audiencia = audiencias.get(indice)
            if audiencia is None:
                casos_adicionales.append(
                    {
                        "nombre": f"Acumulación de registros (audiencia {indice:02d})",
                        "ok": False,
                        "detalle": "La audiencia no existe.",
                    }
                )
                continue

            registros = list(
                RegistroTrazabilidad.objects.filter(audiencia=audiencia).order_by(
                    "fechaHora"
                )
            )
            acciones = [r.accion for r in registros]
            esperado = [
                AccionTrazabilidad.CREACION,
                AccionTrazabilidad.MODIFICACION,
                AccionTrazabilidad.BAJA,
            ]
            ok_acumulacion = len(registros) == 3 and acciones == esperado
            casos_adicionales.append(
                {
                    "nombre": f"Acumulación de registros (audiencia {indice:02d})",
                    "ok": ok_acumulacion,
                    "detalle": (
                        "OK"
                        if ok_acumulacion
                        else f"Se esperaban 3 registros en orden {esperado} y se obtuvo {acciones}"
                    ),
                }
            )

        # (b) Operación fallida no deja un registro incorrecto:
        # reintentar "dejar sin efecto" sobre una audiencia que
        # ya quedó ELIMINADA en la fase 3.
        audiencia_reintento = audiencias.get(1)
        if audiencia_reintento is not None:
            estado_antes = audiencia_reintento.estado
            motivo_antes = audiencia_reintento.motivoBaja
            registros_antes_b = RegistroTrazabilidad.objects.filter(
                audiencia=audiencia_reintento
            ).count()

            self.client.post(
                reverse("dejar_sin_efecto_audiencia"),
                {
                    "audiencia_id": audiencia_reintento.pk,
                    "motivo_seleccionado": MotivoBaja.SUSPENSION,
                },
            )
            audiencia_reintento.refresh_from_db()
            registros_despues_b = RegistroTrazabilidad.objects.filter(
                audiencia=audiencia_reintento
            ).count()

            ok_b = (
                audiencia_reintento.estado == estado_antes
                and audiencia_reintento.motivoBaja == motivo_antes
                and registros_despues_b == registros_antes_b
            )
            casos_adicionales.append(
                {
                    "nombre": "Reintento de baja sobre audiencia ya eliminada",
                    "ok": ok_b,
                    "detalle": (
                        "OK"
                        if ok_b
                        else "El reintento modificó el estado/motivo de la audiencia "
                        "o creó un RegistroTrazabilidad adicional."
                    ),
                }
            )
        else:
            casos_adicionales.append(
                {
                    "nombre": "Reintento de baja sobre audiencia ya eliminada",
                    "ok": False,
                    "detalle": "No existe la audiencia 01 para este caso.",
                }
            )

        # (c) Operación fallida no deja un registro incorrecto:
        # crear audiencia con formulario inválido (sin "fecha").
        audiencias_antes_c = Audiencia.objects.count()
        registros_antes_c = RegistroTrazabilidad.objects.count()

        self.client.post(
            reverse("registrar_audiencia"),
            {
                "competencia": self.competencia.pk,
                "rit": "RIT-INVALIDO-SIN-FECHA",
                "tipoAudiencia": self.tipo_audiencia.pk,
                "sala": self.sala.pk,
                "cantidadBloques": 1,
                # "fecha" deliberadamente ausente: formulario inválido.
                "bloqueInicio": self.bloque.pk,
            },
        )

        ok_c = (
            Audiencia.objects.count() == audiencias_antes_c
            and RegistroTrazabilidad.objects.count() == registros_antes_c
        )
        casos_adicionales.append(
            {
                "nombre": "Creación con formulario inválido (sin fecha)",
                "ok": ok_c,
                "detalle": (
                    "OK"
                    if ok_c
                    else "Se creó una Audiencia y/o un RegistroTrazabilidad pese a "
                    "que el formulario era inválido."
                ),
            }
        )

        # ---------------------------------------------------
        # EVIDENCIA + VEREDICTO
        # ---------------------------------------------------

        self._escribir_evidencia(
            resultados, casos_correctos, casos_incorrectos, porcentaje, cumple, casos_adicionales
        )

        self.assertGreater(
            porcentaje,
            CRITERIO_PORCENTAJE_MINIMO,
            (
                f"Prueba 2 (Trazabilidad) NO CUMPLE: {porcentaje}% "
                f"(criterio: >{CRITERIO_PORCENTAJE_MINIMO}%). "
                f"Ver {RUTA_EVIDENCIA} para el detalle por caso."
            ),
        )

    # =================================================
    # EVIDENCIA
    # =================================================

    def _escribir_evidencia(
        self, resultados, casos_correctos, casos_incorrectos, porcentaje, cumple, casos_adicionales
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
        lineas.append("PRUEBA 2 – TRAZABILIDAD")
        lineas.append("=========================")
        lineas.append(f"Operaciones evaluadas: {TOTAL_OPERACIONES}")
        lineas.append(f"Operaciones con trazabilidad correcta: {casos_correctos}")
        lineas.append(f"Operaciones sin trazabilidad: {casos_incorrectos}")
        lineas.append(f"Porcentaje obtenido: {porcentaje} %")
        lineas.append(f"Criterio: >{CRITERIO_PORCENTAJE_MINIMO} %")
        lineas.append(f"Resultado: {'CUMPLE' if cumple else 'NO CUMPLE'}")

        lineas.append("")
        lineas.append("CASOS ADICIONALES (fuera del cálculo de la métrica)")
        lineas.append("-----------------------------------------------------")
        for extra in casos_adicionales:
            lineas.append(f"{extra['nombre']} → {'OK' if extra['ok'] else 'FALLA'}")
            if not extra["ok"]:
                lineas.append(f"    {extra['detalle']}")

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
