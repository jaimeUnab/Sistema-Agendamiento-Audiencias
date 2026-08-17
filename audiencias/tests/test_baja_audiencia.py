"""
Pruebas UNITARIAS de la baja lógica de audiencias
(ServicioBajaAudiencia, en audiencias/services.py).

Cada prueba de este archivo llama DIRECTAMENTE a
ServicioBajaAudiencia, sin pasar por ninguna vista HTTP ni por el
cliente de pruebas de Django: aísla la regla de negocio de la baja
lógica. La prueba del flujo HTTP completo (modal, formulario de
motivo, vista, agenda) está en test_integration.py, no aquí -esa es
la diferencia entre ambos archivos, mismo criterio que
test_services_unit.py.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from bloques.models import BloqueHorario
from causas.models import Causa
from competencias.models import Competencia
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

from audiencias.models import (
    AccionTrazabilidad,
    Audiencia,
    EstadoAudiencia,
    RegistroTrazabilidad,
)
from audiencias.services import ServicioBajaAudiencia

Usuario = get_user_model()


class ServicioBajaAudienciaTests(TestCase):
    """
    Pruebas unitarias de ServicioBajaAudiencia.ejecutar().
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_baja_audiencia",
            email="baja_audiencia@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Baja Audiencia",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Baja Audiencia", activa=True
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Baja Audiencia", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Baja Audiencia", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="7001-2027",
            ruc="2700070010-1",
            caratulado="Causa Baja Audiencia",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9701,
            horaInicio=datetime.time(9, 0),
            horaTermino=datetime.time(9, 30),
        )
        self.audiencia = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=datetime.date(2027, 5, 1),
            horaInicio=self.bloque.horaInicio,
            horaTermino=self.bloque.horaTermino,
            usuarioCreacion=self.usuario,
        )

    # =================================================
    # CAMBIO DE ESTADO
    # =================================================

    def test_baja_cambia_programada_a_eliminada(self):
        resultado = ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Suspensión de la audiencia",
        ).ejecutar()

        self.assertTrue(resultado["exito"])
        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.ELIMINADA)

    # =================================================
    # MOTIVO ALMACENADO
    # =================================================

    def test_baja_guarda_motivoBaja_correctamente(self):
        ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Otro: Se cayó el sistema del tribunal.",
        ).ejecutar()

        self.audiencia.refresh_from_db()
        self.assertEqual(
            self.audiencia.motivoBaja,
            "Otro: Se cayó el sistema del tribunal.",
        )

    # =================================================
    # NO SE PERMITE REPETIR LA BAJA
    # =================================================

    def test_baja_sobre_audiencia_ya_eliminada_no_se_permite(self):
        primera = ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Reprogramación",
        ).ejecutar()
        self.assertTrue(primera["exito"])

        segunda = ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Error de agendamiento",
        ).ejecutar()

        self.assertFalse(segunda["exito"])
        self.assertEqual(
            segunda["error"], ServicioBajaAudiencia.MENSAJE_YA_ELIMINADA
        )
        self.assertIsNone(segunda["registroTrazabilidad"])

        # El motivo de la primera baja no fue sobreescrito por el
        # segundo intento (que no debía aplicarse).
        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.motivoBaja, "Reprogramación")

        # Solo existe UN RegistroTrazabilidad de acción BAJA, el de
        # la primera llamada.
        self.assertEqual(
            RegistroTrazabilidad.objects.filter(
                audiencia=self.audiencia, accion=AccionTrazabilidad.BAJA
            ).count(),
            1,
        )

    # =================================================
    # NO SE ELIMINA FÍSICAMENTE
    # =================================================

    def test_baja_no_elimina_fisicamente_el_registro(self):
        ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Solicitud del tribunal",
        ).ejecutar()

        self.assertTrue(
            Audiencia.objects.filter(pk=self.audiencia.pk).exists()
        )
        self.assertEqual(Audiencia.objects.count(), 1)

    # =================================================
    # TRAZABILIDAD: USUARIO, FECHA/HORA, ACCIÓN
    # =================================================

    def test_baja_registra_trazabilidad_con_usuario_fecha_y_accion_baja(self):
        resultado = ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Suspensión de la audiencia",
        ).ejecutar()

        registro = resultado["registroTrazabilidad"]
        self.assertIsNotNone(registro)
        self.assertEqual(registro.audiencia, self.audiencia)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.accion, AccionTrazabilidad.BAJA)
        self.assertIsNotNone(registro.fechaHora)

        # Snapshot anterior/posterior usado por la trazabilidad.
        self.assertEqual(
            registro.valoresAnteriores["estado"], EstadoAudiencia.PROGRAMADA
        )
        self.assertEqual(
            registro.valoresNuevos["estado"], EstadoAudiencia.ELIMINADA
        )
        self.assertEqual(
            registro.valoresNuevos["motivoBaja"], "Suspensión de la audiencia"
        )

    def test_baja_de_una_audiencia_no_afecta_a_otras_programadas(self):
        otra_audiencia = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=BloqueHorario.objects.create(
                orden=9702,
                horaInicio=datetime.time(9, 30),
                horaTermino=datetime.time(10, 0),
            ),
            cantidadBloques=1,
            fecha=datetime.date(2027, 5, 1),
            horaInicio=datetime.time(9, 30),
            horaTermino=datetime.time(10, 0),
            usuarioCreacion=self.usuario,
        )

        ServicioBajaAudiencia(
            audiencia=self.audiencia,
            usuario=self.usuario,
            motivo="Reprogramación",
        ).ejecutar()

        otra_audiencia.refresh_from_db()
        self.assertEqual(otra_audiencia.estado, EstadoAudiencia.PROGRAMADA)
