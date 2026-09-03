"""
Prueba automatizada de la Prueba 4 del proyecto de título:
"Agenda diaria y semanal".

Evalúa que audiencias/views.py:agenda_diaria y
audiencias/views.py:agenda_semanal muestren exactamente las
audiencias que corresponden -ni de más ni de menos, con sus datos
correctos y (en la semanal) agrupadas en el día correcto-, a
través de sus puntos de entrada HTTP reales
(reverse("agenda_diaria")/reverse("agenda_semanal"), invocados con
self.client.get(...)).

ORÁCULO INDEPENDIENTE (requisito central de esta prueba): para
cada escenario, "qué audiencias deberían aparecer" NO se calcula
volviendo a ejecutar Audiencia.objects.filter(...) con la misma
forma de consulta que usan las vistas. En su lugar, cada vez que
este archivo crea una Audiencia (ver _crear_audiencia), guarda sus
datos reales en una lista de Python propia (self.registros_creados,
de instancias de RegistroEsperado -un namedtuple simple, no un
QuerySet-). Los "esperados" de cada escenario se obtienen filtrando
ESA lista de Python con condiciones booleanas explícitas
(_esperados_dia/_esperados_semana), sin tocar el ORM. Solo el lado
"mostrado" consulta la vista real, vía response.context. Si alguna
de las dos vistas tuviera un error en su propio filtro, el oráculo
no lo heredaría, porque nunca ejecuta esa misma consulta.

REGLAS DE DISEÑO GENERALES (mismas que los archivos de prueba
anteriores de este paquete):

- No usa la base de datos real del proyecto: corre sobre la base
  de datos de pruebas que Django crea y destruye automáticamente
  (TestCase).
- No depende de datos precargados: todos los datos se crean dentro
  de este mismo archivo.
- No modifica audiencias/views.py, ningún modelo, ninguna
  plantilla ni ningún archivo de prueba existente: solo agrega
  este archivo nuevo.
- A diferencia de las Pruebas 2 y 3, agenda_diaria/agenda_semanal
  aceptan "fecha" explícita por GET (no dependen internamente de
  timezone.localdate() salvo cuando el parámetro está ausente), así
  que esta prueba usa fechas de calendario FIJAS (no relativas al
  día de ejecución), para que el resultado sea exactamente
  reproducible en cualquier momento.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime
import os
from collections import namedtuple

from django.test import TestCase
from django.urls import reverse

from audiencias.models import Audiencia, EstadoAudiencia
from bloques.models import BloqueHorario
from causas.models import Causa
from competencias.models import Competencia
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia
from usuarios.models import Usuario


# =====================================================
# CONSTANTES DE LA PRUEBA
# =====================================================

CRITERIO_PORCENTAJE_MINIMO = 98  # estrictamente mayor (>), no >=
TOTAL_ESCENARIOS = 14

RUTA_EVIDENCIA = os.path.join(
    os.path.dirname(__file__),
    "evidencia_prueba_4_agenda.txt",
)

# Snapshot plano (no un modelo, no un QuerySet) de una Audiencia
# creada por esta prueba: es la única fuente de verdad del
# oráculo independiente (ver docstring del módulo).
RegistroEsperado = namedtuple(
    "RegistroEsperado",
    [
        "pk", "fecha", "sala_id", "estado", "rit",
        "horaInicio", "horaTermino", "cantidadBloques", "bloqueOrden",
    ],
)


class Prueba4AgendaTests(TestCase):
    """
    Ejecuta 14 escenarios (8 sobre agenda_diaria, 6 sobre
    agenda_semanal) contra los puntos de entrada HTTP reales, y
    calcula el porcentaje de registros mostrados correctamente
    respecto de los registros que, según un oráculo independiente,
    deberían mostrarse.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create(
            nombre="Usuario de prueba - agenda",
            email="prueba4.agenda@example.com",
        )

        cls.sala_a = Sala.objects.create(nombre="Sala agenda A", activa=True)
        cls.sala_b = Sala.objects.create(nombre="Sala agenda B", activa=True)

        cls.competencia = Competencia.objects.create(
            nombre="Competencia agenda", activa=True
        )
        cls.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo de audiencia agenda", activo=True
        )

        # 3 bloques horarios con horas distintas y "orden" distinto:
        # necesarios para verificar que agenda_diaria/agenda_semanal
        # ordenan realmente por bloqueInicio__orden (no por la hora
        # como texto, ni por el orden de creación).
        cls.bloque_1 = BloqueHorario.objects.create(
            horaInicio=datetime.time(8, 0), horaTermino=datetime.time(8, 30),
            orden=1, permiteAgendamientoAutomatico=True,
        )
        cls.bloque_2 = BloqueHorario.objects.create(
            horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            orden=2, permiteAgendamientoAutomatico=True,
        )
        cls.bloque_3 = BloqueHorario.objects.create(
            horaInicio=datetime.time(10, 0), horaTermino=datetime.time(10, 30),
            orden=3, permiteAgendamientoAutomatico=True,
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.registros_creados = []  # lista de RegistroEsperado (oráculo)
        self._contador_rit = 0

    # =================================================
    # CONSTRUCCIÓN DE DATOS (alimenta el oráculo)
    # =================================================

    def _crear_audiencia(self, sala, fecha, bloque, estado=EstadoAudiencia.PROGRAMADA, motivo_baja=""):
        """
        Crea una Audiencia real (vía ORM, con su propia Causa) y, en
        el mismo paso, registra sus datos en self.registros_creados
        -la lista de Python que alimenta el oráculo independiente-.
        """
        self._contador_rit += 1
        causa = Causa.objects.create(
            competencia=self.competencia,
            rit=f"C-AGENDA-{self._contador_rit:03d}",
            ruc=f"RUC-AGENDA-{self._contador_rit:03d}",
            caratulado=f"Causa de prueba agenda {self._contador_rit:03d}",
        )
        audiencia = Audiencia.objects.create(
            causa=causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=sala,
            bloqueInicio=bloque,
            cantidadBloques=1,
            fecha=fecha,
            horaInicio=bloque.horaInicio,
            horaTermino=bloque.horaTermino,
            estado=estado,
            motivoBaja=motivo_baja,
            usuarioCreacion=self.usuario,
        )
        self.registros_creados.append(
            RegistroEsperado(
                pk=audiencia.pk,
                fecha=fecha,
                sala_id=sala.pk,
                estado=estado,
                rit=causa.rit,
                horaInicio=bloque.horaInicio,
                horaTermino=bloque.horaTermino,
                cantidadBloques=1,
                bloqueOrden=bloque.orden,
            )
        )
        return audiencia

    # =================================================
    # ORÁCULO INDEPENDIENTE
    # =================================================
    # Filtra self.registros_creados (una lista de Python, no un
    # QuerySet) con condiciones booleanas explícitas, replicando el
    # SIGNIFICADO real de cada filtro sin ejecutar la misma consulta
    # ORM que las vistas evaluadas.

    def _esperados_dia(self, fecha, sala_id, estado_filtro=""):
        resultado = [
            r for r in self.registros_creados
            if r.fecha == fecha
            and r.sala_id == sala_id
            and (estado_filtro == "" or r.estado == estado_filtro)
        ]
        return sorted(resultado, key=lambda r: r.bloqueOrden)

    def _esperados_semana(self, fecha_desde, fecha_hasta, sala_id, estado_filtro=""):
        return [
            r for r in self.registros_creados
            if fecha_desde <= r.fecha <= fecha_hasta
            and r.sala_id == sala_id
            and (estado_filtro == "" or r.estado == estado_filtro)
        ]

    # =================================================
    # COMPARACIÓN ESPERADO vs. MOSTRADO
    # =================================================

    def _registro_correcto(self, audiencia_real, esperado):
        """
        Compara una Audiencia real devuelta por la vista contra el
        RegistroEsperado correspondiente, campo por campo (solo los
        campos que las plantillas realmente muestran, ver docstring
        del módulo).
        """
        return (
            audiencia_real.fecha == esperado.fecha
            and audiencia_real.sala_id == esperado.sala_id
            and audiencia_real.estado == esperado.estado
            and audiencia_real.causa.rit == esperado.rit
            and audiencia_real.horaInicio == esperado.horaInicio
            and audiencia_real.horaTermino == esperado.horaTermino
            and audiencia_real.cantidadBloques == esperado.cantidadBloques
        )

    def _evaluar_diaria(self, esperados, mostrados):
        """
        Devuelve (registros_correctos, registros_incorrectos, ok, detalle)
        para un escenario de agenda_diaria. "mostrados" es
        response.context["audiencias"] tal cual (lista de Audiencia
        reales, en el orden real que devolvió la vista).
        """
        detalles_falla = []

        pks_esperados = [r.pk for r in esperados]
        pks_mostrados = [a.pk for a in mostrados]
        pks_esperados_set = set(pks_esperados)

        faltantes = [pk for pk in pks_esperados if pk not in pks_mostrados]
        sobrantes = [pk for pk in pks_mostrados if pk not in pks_esperados_set]

        if faltantes:
            detalles_falla.append(f"Faltan {len(faltantes)} registro(s) esperado(s) (pk={faltantes}).")
        if sobrantes:
            detalles_falla.append(f"Aparecen {len(sobrantes)} registro(s) no esperado(s) (pk={sobrantes}).")
        if not faltantes and not sobrantes and pks_mostrados != pks_esperados:
            detalles_falla.append(
                f"El orden mostrado {pks_mostrados} no coincide con el esperado {pks_esperados}."
            )

        mostrados_por_pk = {a.pk: a for a in mostrados}
        registros_correctos = 0
        for r in esperados:
            audiencia_real = mostrados_por_pk.get(r.pk)
            if audiencia_real is not None and self._registro_correcto(audiencia_real, r):
                registros_correctos += 1
            elif audiencia_real is not None:
                detalles_falla.append(f"El registro pk={r.pk} aparece con datos distintos a los esperados.")

        registros_incorrectos = len(esperados) - registros_correctos
        ok = (not detalles_falla) and (registros_correctos == len(esperados))
        detalle = "OK" if ok else " | ".join(detalles_falla)
        return registros_correctos, registros_incorrectos, ok, detalle

    def _evaluar_semanal(self, esperados, dias_semana_context):
        """
        Devuelve (registros_correctos, registros_incorrectos, ok, detalle)
        para un escenario de agenda_semanal. "dias_semana_context" es
        response.context["dias_semana"] tal cual (lista de 7 dicts
        reales, cada uno con "fecha" y "audiencias").
        """
        detalles_falla = []

        if len(dias_semana_context) != 7:
            detalles_falla.append(
                f"Se esperaban 7 días en dias_semana y hay {len(dias_semana_context)}."
            )

        registros_correctos = 0

        for dia in dias_semana_context:
            fecha_dia = dia["fecha"]
            esperados_del_dia = sorted(
                [r for r in esperados if r.fecha == fecha_dia],
                key=lambda r: r.bloqueOrden,
            )
            mostrados_del_dia = list(dia["audiencias"])

            pks_esperados = [r.pk for r in esperados_del_dia]
            pks_mostrados = [a.pk for a in mostrados_del_dia]

            if pks_mostrados != pks_esperados:
                detalles_falla.append(
                    f"Día {fecha_dia}: se esperaban {pks_esperados} y se mostraron {pks_mostrados}."
                )

            mostrados_por_pk = {a.pk: a for a in mostrados_del_dia}
            for r in esperados_del_dia:
                audiencia_real = mostrados_por_pk.get(r.pk)
                if audiencia_real is not None and self._registro_correcto(audiencia_real, r):
                    registros_correctos += 1
                elif audiencia_real is not None:
                    detalles_falla.append(
                        f"Día {fecha_dia}: el registro pk={r.pk} aparece con datos distintos a los esperados."
                    )

        registros_incorrectos = len(esperados) - registros_correctos
        ok = (not detalles_falla) and (registros_correctos == len(esperados))
        detalle = "OK" if ok else " | ".join(detalles_falla)
        return registros_correctos, registros_incorrectos, ok, detalle

    def _registrar_caso(self, resultados, numero, descripcion, registros_correctos, registros_incorrectos, ok, detalle):
        resultados.append(
            {
                "numero": numero,
                "descripcion": descripcion,
                "registros_correctos": registros_correctos,
                "registros_incorrectos": registros_incorrectos,
                "ok": ok,
                "detalle": detalle,
            }
        )
        with self.subTest(caso=numero, descripcion=descripcion):
            self.assertTrue(ok, detalle)

    # =================================================
    # PRUEBA PRINCIPAL
    # =================================================

    def test_prueba_4_agenda_14_escenarios(self):
        resultados = []

        # =============================================
        # AGENDA DIARIA (casos 01-08)
        # =============================================

        # ---- Caso 01: múltiples audiencias mismo día, distintas
        # horas (verifica cantidad y el orden real por bloque). Se
        # crean deliberadamente en orden "desordenado" (bloque 3,
        # luego 1, luego 2) para no depender del orden de creación.
        fecha_d01 = datetime.date(2026, 9, 7)
        self._crear_audiencia(self.sala_a, fecha_d01, self.bloque_3)
        self._crear_audiencia(self.sala_a, fecha_d01, self.bloque_1)
        self._crear_audiencia(self.sala_a, fecha_d01, self.bloque_2)

        respuesta = self.client.get(
            reverse("agenda_diaria"), {"sala": self.sala_a.pk, "fecha": fecha_d01.isoformat()}
        )
        esperados = self._esperados_dia(fecha_d01, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        self._registrar_caso(resultados, 1, "Agenda diaria - múltiples audiencias, mismo día, orden por bloque", correctos, incorrectos, ok, detalle)

        # ---- Caso 02: audiencias en días diferentes, no se mezclan
        # (fecha_d02_b se eligió deliberadamente fuera de la semana
        # 2026-09-07..2026-09-13 usada por los casos 09-11, para que
        # este caso no deje una audiencia "de sobra" que contamine el
        # oráculo de esos otros escenarios: cada escenario debe poder
        # evaluarse con datos que no se pisen entre sí).
        fecha_d02_a = datetime.date(2026, 9, 8)
        fecha_d02_b = datetime.date(2026, 9, 16)
        self._crear_audiencia(self.sala_a, fecha_d02_a, self.bloque_1)
        self._crear_audiencia(self.sala_a, fecha_d02_b, self.bloque_1)

        respuesta = self.client.get(
            reverse("agenda_diaria"), {"sala": self.sala_a.pk, "fecha": fecha_d02_a.isoformat()}
        )
        esperados = self._esperados_dia(fecha_d02_a, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        self._registrar_caso(resultados, 2, "Agenda diaria - audiencias en días diferentes", correctos, incorrectos, ok, detalle)

        # ---- Caso 03: audiencias en distintas salas, filtro por sala
        fecha_d03 = datetime.date(2026, 9, 10)
        self._crear_audiencia(self.sala_a, fecha_d03, self.bloque_1)
        self._crear_audiencia(self.sala_b, fecha_d03, self.bloque_1)

        respuesta = self.client.get(
            reverse("agenda_diaria"), {"sala": self.sala_a.pk, "fecha": fecha_d03.isoformat()}
        )
        esperados = self._esperados_dia(fecha_d03, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        self._registrar_caso(resultados, 3, "Agenda diaria - audiencias en distintas salas", correctos, incorrectos, ok, detalle)

        # ---- Caso 04: fecha sin audiencias
        fecha_d04 = datetime.date(2026, 9, 11)
        respuesta = self.client.get(
            reverse("agenda_diaria"), {"sala": self.sala_a.pk, "fecha": fecha_d04.isoformat()}
        )
        esperados = self._esperados_dia(fecha_d04, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        ok = ok and respuesta.context["hay_audiencias"] is False
        self._registrar_caso(resultados, 4, "Agenda diaria - fecha sin audiencias", correctos, incorrectos, ok, detalle)

        # ---- Casos 05-07: filtro de estado (Todas / PROGRAMADA / ELIMINADA)
        fecha_d05 = datetime.date(2026, 9, 12)
        aud_prog = self._crear_audiencia(self.sala_a, fecha_d05, self.bloque_1)
        aud_elim = self._crear_audiencia(
            self.sala_a, fecha_d05, self.bloque_2,
            estado=EstadoAudiencia.ELIMINADA, motivo_baja="Suspensión de la audiencia",
        )

        respuesta = self.client.get(
            reverse("agenda_diaria"), {"sala": self.sala_a.pk, "fecha": fecha_d05.isoformat()}
        )
        esperados = self._esperados_dia(fecha_d05, self.sala_a.pk, estado_filtro="")
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        self._registrar_caso(resultados, 5, "Agenda diaria - filtro de estado Todas (PROGRAMADA + ELIMINADA)", correctos, incorrectos, ok, detalle)

        respuesta = self.client.get(
            reverse("agenda_diaria"),
            {"sala": self.sala_a.pk, "fecha": fecha_d05.isoformat(), "estado": EstadoAudiencia.PROGRAMADA},
        )
        esperados = self._esperados_dia(fecha_d05, self.sala_a.pk, estado_filtro=EstadoAudiencia.PROGRAMADA)
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        self._registrar_caso(resultados, 6, "Agenda diaria - filtro de estado PROGRAMADA", correctos, incorrectos, ok, detalle)

        respuesta = self.client.get(
            reverse("agenda_diaria"),
            {"sala": self.sala_a.pk, "fecha": fecha_d05.isoformat(), "estado": EstadoAudiencia.ELIMINADA},
        )
        esperados = self._esperados_dia(fecha_d05, self.sala_a.pk, estado_filtro=EstadoAudiencia.ELIMINADA)
        correctos, incorrectos, ok, detalle = self._evaluar_diaria(
            esperados, list(respuesta.context["audiencias"])
        )
        self._registrar_caso(resultados, 7, "Agenda diaria - filtro de estado ELIMINADA", correctos, incorrectos, ok, detalle)

        # ---- Caso 08: sin sala seleccionada (no debe consultar nada)
        respuesta = self.client.get(reverse("agenda_diaria"), {"fecha": "2026-09-07"})
        ok = (
            respuesta.context["sala_seleccionada"] is None
            and list(respuesta.context["audiencias"]) == []
        )
        detalle = "OK" if ok else "sala_seleccionada o audiencias no correspondieron al comportamiento esperado sin sala."
        self._registrar_caso(resultados, 8, "Agenda diaria - sin sala seleccionada", 0, 0, ok, detalle)

        # =============================================
        # AGENDA SEMANAL (casos 09-14)
        # =============================================

        # ---- Caso 09: semana con días ocupados y días vacíos mezclados
        lunes_s01 = datetime.date(2026, 9, 7)
        domingo_s01 = datetime.date(2026, 9, 13)
        aud_lunes = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 7), self.bloque_1)
        aud_mie_1 = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 9), self.bloque_2)
        aud_mie_2 = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 9), self.bloque_1)
        aud_viernes = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 11), self.bloque_1)

        respuesta = self.client.get(
            reverse("agenda_semanal"), {"sala": self.sala_a.pk, "fecha": lunes_s01.isoformat()}
        )
        esperados = self._esperados_semana(lunes_s01, domingo_s01, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_semanal(
            esperados, respuesta.context["dias_semana"]
        )
        self._registrar_caso(resultados, 9, "Agenda semanal - días ocupados y vacíos mezclados", correctos, incorrectos, ok, detalle)

        # ---- Caso 10: límite entre semanas (domingo vs. lunes siguiente)
        aud_domingo = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 13), self.bloque_1)
        aud_lunes_siguiente = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 14), self.bloque_1)

        respuesta = self.client.get(
            reverse("agenda_semanal"), {"sala": self.sala_a.pk, "fecha": lunes_s01.isoformat()}
        )
        esperados = self._esperados_semana(lunes_s01, domingo_s01, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_semanal(
            esperados, respuesta.context["dias_semana"]
        )
        self._registrar_caso(resultados, 10, "Agenda semanal - límite entre semanas", correctos, incorrectos, ok, detalle)

        # ---- Caso 11: fecha de referencia en medio de la semana
        # (jueves, día sin audiencias propias): debe dar exactamente
        # el mismo resultado que consultar con el lunes de esa semana
        # (misma semana ya poblada en los casos 09/10).
        jueves_misma_semana = datetime.date(2026, 9, 10)
        respuesta = self.client.get(
            reverse("agenda_semanal"), {"sala": self.sala_a.pk, "fecha": jueves_misma_semana.isoformat()}
        )
        esperados = self._esperados_semana(lunes_s01, domingo_s01, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_semanal(
            esperados, respuesta.context["dias_semana"]
        )
        self._registrar_caso(resultados, 11, "Agenda semanal - fecha de referencia en medio de la semana", correctos, incorrectos, ok, detalle)

        # ---- Caso 12: distinta sala, misma semana (otra semana,
        # para no interferir con los casos 09-11)
        lunes_s04 = datetime.date(2026, 9, 21)
        domingo_s04 = datetime.date(2026, 9, 27)
        aud_sala_a_s04 = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 23), self.bloque_1)
        aud_sala_b_s04 = self._crear_audiencia(self.sala_b, datetime.date(2026, 9, 23), self.bloque_1)

        respuesta = self.client.get(
            reverse("agenda_semanal"), {"sala": self.sala_a.pk, "fecha": lunes_s04.isoformat()}
        )
        esperados = self._esperados_semana(lunes_s04, domingo_s04, self.sala_a.pk)
        correctos, incorrectos, ok, detalle = self._evaluar_semanal(
            esperados, respuesta.context["dias_semana"]
        )
        self._registrar_caso(resultados, 12, "Agenda semanal - distinta sala, misma semana", correctos, incorrectos, ok, detalle)

        # ---- Caso 13: filtro de estado en semanal
        lunes_s05 = datetime.date(2026, 9, 28)
        domingo_s05 = datetime.date(2026, 10, 4)
        aud_prog_s05 = self._crear_audiencia(self.sala_a, datetime.date(2026, 9, 28), self.bloque_1)
        aud_elim_s05 = self._crear_audiencia(
            self.sala_a, datetime.date(2026, 9, 30), self.bloque_1,
            estado=EstadoAudiencia.ELIMINADA, motivo_baja="Reprogramación",
        )

        respuesta = self.client.get(
            reverse("agenda_semanal"),
            {"sala": self.sala_a.pk, "fecha": lunes_s05.isoformat(), "estado": EstadoAudiencia.PROGRAMADA},
        )
        esperados = self._esperados_semana(lunes_s05, domingo_s05, self.sala_a.pk, estado_filtro=EstadoAudiencia.PROGRAMADA)
        correctos, incorrectos, ok, detalle = self._evaluar_semanal(
            esperados, respuesta.context["dias_semana"]
        )
        self._registrar_caso(resultados, 13, "Agenda semanal - filtro de estado PROGRAMADA", correctos, incorrectos, ok, detalle)

        # ---- Caso 14: semana totalmente sin audiencias
        lunes_s06 = datetime.date(2026, 10, 5)
        respuesta = self.client.get(
            reverse("agenda_semanal"), {"sala": self.sala_a.pk, "fecha": lunes_s06.isoformat()}
        )
        esperados = self._esperados_semana(
            lunes_s06, datetime.date(2026, 10, 11), self.sala_a.pk
        )
        correctos, incorrectos, ok, detalle = self._evaluar_semanal(
            esperados, respuesta.context["dias_semana"]
        )
        ok = ok and respuesta.context["hay_audiencias"] is False
        self._registrar_caso(resultados, 14, "Agenda semanal - semana totalmente sin audiencias", correctos, incorrectos, ok, detalle)

        # ---------------------------------------------------
        # CÁLCULO DE LA MÉTRICA
        # ---------------------------------------------------

        registros_esperados_total = sum(
            r["registros_correctos"] + r["registros_incorrectos"] for r in resultados
        )
        registros_correctos_total = sum(r["registros_correctos"] for r in resultados)
        registros_incorrectos_total = sum(r["registros_incorrectos"] for r in resultados)

        if registros_esperados_total > 0:
            porcentaje = round((registros_correctos_total / registros_esperados_total) * 100, 2)
        else:
            porcentaje = 100.0
        cumple = porcentaje > CRITERIO_PORCENTAJE_MINIMO

        self._escribir_evidencia(
            resultados,
            registros_esperados_total,
            registros_correctos_total,
            registros_incorrectos_total,
            porcentaje,
            cumple,
        )

        self.assertGreater(
            porcentaje,
            CRITERIO_PORCENTAJE_MINIMO,
            (
                f"Prueba 4 (Agenda diaria y semanal) NO CUMPLE: {porcentaje}% "
                f"(criterio: >{CRITERIO_PORCENTAJE_MINIMO}%). "
                f"Ver {RUTA_EVIDENCIA} para el detalle por caso."
            ),
        )

    # =================================================
    # EVIDENCIA
    # =================================================

    def _escribir_evidencia(
        self, resultados, registros_esperados, registros_correctos, registros_incorrectos, porcentaje, cumple
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
        lineas.append("PRUEBA 4 – AGENDA DIARIA Y SEMANAL")
        lineas.append("====================================")
        lineas.append(f"Escenarios evaluados: {TOTAL_ESCENARIOS}")
        lineas.append(f"Registros esperados: {registros_esperados}")
        lineas.append(f"Registros mostrados correctamente: {registros_correctos}")
        lineas.append(f"Registros incorrectos: {registros_incorrectos}")
        lineas.append(f"Porcentaje obtenido: {porcentaje} %")
        lineas.append(f"Criterio: >{CRITERIO_PORCENTAJE_MINIMO} %")
        lineas.append(f"Resultado: {'CUMPLE' if cumple else 'NO CUMPLE'}")

        contenido = "\n".join(lineas) + "\n"

        with open(RUTA_EVIDENCIA, "w", encoding="utf-8") as archivo:
            archivo.write(contenido)

        # La consola de Windows suele usar cp1252, que no puede
        # representar "–"/"→"; si falla, se imprime un equivalente
        # en ASCII solo para no interrumpir la ejecución (el archivo
        # de evidencia siempre conserva el formato exacto en UTF-8).
        try:
            print("\n" + contenido)
        except UnicodeEncodeError:
            print("\n" + contenido.replace("–", "-").replace("→", "->"))
