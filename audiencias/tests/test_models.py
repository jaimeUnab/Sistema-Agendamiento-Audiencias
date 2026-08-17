"""
Pruebas de MODELO de la aplicación Audiencias.

Contiene pruebas básicas del modelo Audiencia: creación directa vía
el ORM, sin pasar por AudienciaForm ni por ninguna vista HTTP. No
son pruebas de integración (no usan el cliente de pruebas) ni
prueban lógica de negocio (eso vive en test_services_unit.py): solo
verifican que el modelo almacena correctamente lo que se le pasa.

Movidas aquí desde el antiguo audiencias/tests.py (un único
archivo, reorganizado en el paquete audiencias/tests/ para separar
pruebas de modelo, unitarias de servicios/formularios, y de
integración).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime

# Permite crear usuarios de prueba sin acoplarse directamente
# a la clase Usuario (buena práctica recomendada por Django
# cuando el proyecto usa un modelo de usuario personalizado).
from django.contrib.auth import get_user_model

from django.test import TestCase

from bloques.models import BloqueHorario
from causas.models import Causa
from competencias.models import Competencia
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

from audiencias.models import Audiencia, EstadoAudiencia

Usuario = get_user_model()


class AudienciaModelTests(TestCase):
    """
    Pruebas básicas del modelo Audiencia.

    setUp() crea, para cada prueba, todos los datos de apoyo
    (Competencia, TipoAudiencia, Sala, BloqueHorario, Causa,
    Usuario) que Audiencia necesita por sus relaciones
    obligatorias.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_audiencias",
            email="pruebas_audiencias@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
        )

        self.competencia = Competencia.objects.create(
            nombre="Competencia de Pruebas"
        )

        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo de Prueba",
            activo=True,
        )

        self.sala = Sala.objects.create(nombre="Sala de Pruebas Audiencias")

        self.bloque = BloqueHorario.objects.create(
            orden=9101,
            horaInicio="09:00",
            horaTermino="09:30",
        )

        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="1234-2026",
            ruc="2600123456-7",
            caratulado="Fiscal de Chile con Persona de Prueba",
        )

    def _crear_audiencia(self, **overrides):
        """
        Helper interno: crea una Audiencia válida con valores
        por defecto razonables, permitiendo sobreescribir
        cualquier campo desde cada prueba.
        """

        datos = {
            "causa": self.causa,
            "tipoAudiencia": self.tipo_audiencia,
            "sala": self.sala,
            "bloqueInicio": self.bloque,
            "cantidadBloques": 2,
            "fecha": datetime.date(2026, 9, 18),
            "horaInicio": datetime.time(9, 0),
            "horaTermino": datetime.time(10, 0),
            "usuarioCreacion": self.usuario,
        }
        datos.update(overrides)

        return Audiencia.objects.create(**datos)

    def test_creacion_de_audiencia_valida(self):
        """
        Se puede crear una Audiencia con todos sus datos
        obligatorios, y queda almacenada en la base de datos.
        """

        audiencia = self._crear_audiencia()

        self.assertTrue(Audiencia.objects.filter(pk=audiencia.pk).exists())
        self.assertEqual(audiencia.causa, self.causa)
        self.assertEqual(audiencia.tipoAudiencia, self.tipo_audiencia)
        self.assertEqual(audiencia.sala, self.sala)
        self.assertEqual(audiencia.bloqueInicio, self.bloque)
        self.assertEqual(audiencia.usuarioCreacion, self.usuario)

    def test_fecha_creacion_se_genera_automaticamente(self):
        """
        fechaCreacion se completa sola al crear la audiencia
        (auto_now_add), sin que se haya indicado explícitamente
        al crear el registro.
        """

        audiencia = self._crear_audiencia()

        self.assertIsNotNone(audiencia.fechaCreacion)

    def test_estado_inicial_es_programada(self):
        """
        Toda audiencia nueva nace con estado PROGRAMADA, sin
        necesidad de indicarlo explícitamente.
        """

        audiencia = self._crear_audiencia()

        self.assertEqual(audiencia.estado, EstadoAudiencia.PROGRAMADA)

    def test_cantidad_bloques_almacena_la_cantidad_indicada(self):
        """
        cantidadBloques almacena correctamente el número de
        bloques consecutivos ocupados por la audiencia (por
        ejemplo, bloqueInicio=bloque 9101 y cantidadBloques=3
        representa los bloques 9101, 9102 y 9103).
        """

        audiencia = self._crear_audiencia(cantidadBloques=3)

        self.assertEqual(audiencia.cantidadBloques, 3)

    def test_hora_inicio_y_hora_termino_se_almacenan_correctamente(self):
        """
        horaInicio y horaTermino quedan almacenadas tal como
        se registraron ("fotografía" del horario concreto de
        la audiencia), sin depender de BloqueHorario.
        """

        audiencia = self._crear_audiencia(
            horaInicio=datetime.time(9, 0),
            horaTermino=datetime.time(10, 0),
        )

        self.assertEqual(audiencia.horaInicio, datetime.time(9, 0))
        self.assertEqual(audiencia.horaTermino, datetime.time(10, 0))
