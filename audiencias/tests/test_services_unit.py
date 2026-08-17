"""
Pruebas UNITARIAS de la lógica de agendamiento
(audiencias/services.py).

Cada prueba de este archivo llama DIRECTAMENTE a las clases y
funciones de audiencias/services.py (ValidadorAgendamiento,
GeneradorPropuestaFecha, y las funciones internas que ambas
comparten: _diaSemanaDe, _contarDiasHabiles, _rangosSeSolapan,
_dentroDePlazo), sin pasar por ninguna vista HTTP ni por el cliente
de pruebas de Django (django.test.Client): cada prueba aísla y
verifica UNA sola regla de negocio. Las pruebas que sí recorren el
flujo HTTP completo (login, formulario, vistas) están en
test_integration.py, no aquí -esa es la diferencia entre ambos
archivos.

ValidadorAgendamiento opera sobre una instancia de Audiencia SIN
GUARDAR (nunca se llama a audiencia.save() en este archivo salvo
cuando se necesita una audiencia YA EXISTENTE para probar
conflictos), tal como está documentado en su propia clase.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from bloques.models import BloqueHorario, ConfiguracionAgendamiento
from causas.models import Causa
from competencias.models import Competencia
from dias_no_disponibles.models import DiaNoDisponible, TipoDiaNoDisponible
from reglas_agendamiento.models import (
    DiaAtencion,
    DiaSemana,
    ReglaAgendamiento,
    TipoPlazo,
)
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

from audiencias.models import Audiencia, EstadoAudiencia
from audiencias.services import (
    GeneradorPropuestaFecha,
    ValidadorAgendamiento,
    _contarDiasHabiles,
    _dentroDePlazo,
    _diaSemanaDe,
    _rangosSeSolapan,
)

Usuario = get_user_model()


# =====================================================
# FUNCIONES INTERNAS COMPARTIDAS
# =====================================================
# Se prueban directamente, aunque su nombre empiece con "_" (son
# el núcleo del cálculo de fechas que usan tanto
# ValidadorAgendamiento como GeneradorPropuestaFecha, y una falla
# ahí afectaría a ambos).

class FuncionesInternasTests(TestCase):
    """
    Pruebas unitarias de las funciones de módulo compartidas de
    audiencias/services.py.
    """

    def test_diaSemanaDe_reconoce_un_dia_habil(self):
        # 2027-03-15 es lunes.
        self.assertEqual(
            _diaSemanaDe(datetime.date(2027, 3, 15)), DiaSemana.LUNES
        )

    def test_diaSemanaDe_devuelve_none_para_sabado_y_domingo(self):
        # 2027-03-20 es sábado, 2027-03-21 es domingo.
        self.assertIsNone(_diaSemanaDe(datetime.date(2027, 3, 20)))
        self.assertIsNone(_diaSemanaDe(datetime.date(2027, 3, 21)))

    def test_rangosSeSolapan_detecta_solape(self):
        self.assertTrue(_rangosSeSolapan(1, 3, 2, 4))

    def test_rangosSeSolapan_detecta_ausencia_de_solape(self):
        self.assertFalse(_rangosSeSolapan(1, 2, 3, 4))

    def test_contarDiasHabiles_cuenta_sabado_como_habil_y_excluye_domingo(self):
        # Del lunes 2027-03-15 al lunes 2027-03-22 (7 días
        # corridos): el sábado 20 cuenta como hábil, el domingo 21
        # no. Deben ser 6 días hábiles.
        dias = _contarDiasHabiles(
            datetime.date(2027, 3, 15), datetime.date(2027, 3, 22)
        )
        self.assertEqual(dias, 6)

    def test_contarDiasHabiles_excluye_feriado_activo(self):
        DiaNoDisponible.objects.create(
            fecha=datetime.date(2027, 3, 18),
            motivo="Feriado de prueba",
            tipo=TipoDiaNoDisponible.FERIADO,
            activo=True,
        )
        # Del lunes 15 al viernes 19 de marzo hay 4 días corridos;
        # con el feriado del jueves 18 excluido, quedan 3 hábiles.
        dias = _contarDiasHabiles(
            datetime.date(2027, 3, 15), datetime.date(2027, 3, 19)
        )
        self.assertEqual(dias, 3)

    def test_contarDiasHabiles_no_excluye_dia_no_disponible_que_no_es_feriado(self):
        # Un DiaNoDisponible de tipo distinto a FERIADO (por
        # ejemplo, MANTENCION) no afecta este cálculo, según la
        # propia documentación de la función.
        DiaNoDisponible.objects.create(
            fecha=datetime.date(2027, 3, 18),
            motivo="Mantención de prueba",
            tipo=TipoDiaNoDisponible.MANTENCION,
            activo=True,
        )
        dias = _contarDiasHabiles(
            datetime.date(2027, 3, 15), datetime.date(2027, 3, 19)
        )
        self.assertEqual(dias, 4)

    def test_dentroDePlazo_solo_minimo_configurado_aplica_solo_ese_limite(self):
        regla = ReglaAgendamiento(plazoMinimo=5, plazoMaximo=None)
        self.assertFalse(_dentroDePlazo(4, regla))
        self.assertTrue(_dentroDePlazo(5, regla))
        self.assertTrue(_dentroDePlazo(9999, regla))

    def test_dentroDePlazo_solo_maximo_configurado_aplica_solo_ese_limite(self):
        regla = ReglaAgendamiento(plazoMinimo=None, plazoMaximo=30)
        self.assertTrue(_dentroDePlazo(0, regla))
        self.assertTrue(_dentroDePlazo(30, regla))
        self.assertFalse(_dentroDePlazo(31, regla))

    def test_dentroDePlazo_ambos_configurados_aplica_ambos_limites(self):
        regla = ReglaAgendamiento(plazoMinimo=5, plazoMaximo=20)
        self.assertFalse(_dentroDePlazo(4, regla))
        self.assertTrue(_dentroDePlazo(12, regla))
        self.assertFalse(_dentroDePlazo(21, regla))

    def test_dentroDePlazo_ninguno_configurado_no_restringe(self):
        regla = ReglaAgendamiento(plazoMinimo=None, plazoMaximo=None)
        self.assertTrue(_dentroDePlazo(0, regla))
        self.assertTrue(_dentroDePlazo(99999, regla))


# =====================================================
# VALIDAR CONFLICTO (disponibilidad de sala/bloque)
# =====================================================

class ValidarConflictoTests(TestCase):
    """
    Pruebas de ValidadorAgendamiento.validarConflicto(): una
    audiencia no puede programarse en un bloque ya ocupado en la
    misma sala y fecha.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_conflicto",
            email="conflicto@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Conflicto",
        )
        self.competencia = Competencia.objects.create(nombre="Competencia Conflicto Tests")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Conflicto Tests", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Conflicto Tests", activa=True)
        self.otra_sala = Sala.objects.create(nombre="Otra Sala Conflicto Tests", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="5001-2027",
            ruc="2700050010-1",
            caratulado="Causa Conflicto Tests",
        )
        self.bloque_1 = BloqueHorario.objects.create(
            orden=9801, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )
        self.bloque_2 = BloqueHorario.objects.create(
            orden=9802, horaInicio=datetime.time(9, 30), horaTermino=datetime.time(10, 0)
        )
        self.fecha = datetime.date(2027, 3, 15)

        # Audiencia YA EXISTENTE, programada, que ocupa self.bloque_1
        # en self.sala y self.fecha.
        self.audiencia_existente = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque_1,
            cantidadBloques=1,
            fecha=self.fecha,
            horaInicio=self.bloque_1.horaInicio,
            horaTermino=self.bloque_1.horaTermino,
            usuarioCreacion=self.usuario,
        )

    def test_detecta_conflicto_cuando_los_bloques_se_solapan(self):
        nueva = Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque_1,
            cantidadBloques=1,
            fecha=self.fecha,
        )
        validador = ValidadorAgendamiento(nueva, fecha_referencia=self.fecha)
        validador.validarConflicto()

        self.assertTrue(
            any("Ya existe una audiencia programada" in a for a in validador.advertencias)
        )

    def test_no_detecta_conflicto_en_bloques_distintos(self):
        nueva = Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque_2,
            cantidadBloques=1,
            fecha=self.fecha,
        )
        validador = ValidadorAgendamiento(nueva, fecha_referencia=self.fecha)
        validador.validarConflicto()

        self.assertEqual(validador.advertencias, [])

    def test_no_detecta_conflicto_en_una_sala_distinta(self):
        nueva = Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.otra_sala,
            bloqueInicio=self.bloque_1,
            cantidadBloques=1,
            fecha=self.fecha,
        )
        validador = ValidadorAgendamiento(nueva, fecha_referencia=self.fecha)
        validador.validarConflicto()

        self.assertEqual(validador.advertencias, [])

    def test_no_detecta_conflicto_en_una_fecha_distinta(self):
        nueva = Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque_1,
            cantidadBloques=1,
            fecha=self.fecha + datetime.timedelta(days=1),
        )
        validador = ValidadorAgendamiento(nueva, fecha_referencia=self.fecha)
        validador.validarConflicto()

        self.assertEqual(validador.advertencias, [])


# =====================================================
# VALIDAR SALA ACTIVA (disponibilidad de sala)
# =====================================================

class ValidarSalaActivaTests(TestCase):
    """
    Pruebas de ValidadorAgendamiento._validarSalaActiva(): una
    sala inactiva es un ERROR bloqueante, no una advertencia.
    """

    def setUp(self):
        self.competencia = Competencia.objects.create(nombre="Competencia Sala Activa Tests")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Sala Activa Tests", activo=True
        )
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="5002-2027",
            ruc="2700050020-2",
            caratulado="Causa Sala Activa Tests",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9803, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )

    def _audiencia(self, sala):
        return Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=sala,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=datetime.date(2027, 3, 15),
        )

    def test_sala_inactiva_es_un_error_bloqueante(self):
        sala_inactiva = Sala.objects.create(nombre="Sala Inactiva Validador", activa=False)
        validador = ValidadorAgendamiento(
            self._audiencia(sala_inactiva), fecha_referencia=datetime.date(2027, 3, 1)
        )
        validador._validarSalaActiva()

        self.assertTrue(
            any("no está disponible para agendamiento" in e for e in validador.errores)
        )
        # No debe reportarse como advertencia: es un error bloqueante.
        self.assertEqual(validador.advertencias, [])

    def test_sala_activa_no_genera_error(self):
        sala_activa = Sala.objects.create(nombre="Sala Activa Validador", activa=True)
        validador = ValidadorAgendamiento(
            self._audiencia(sala_activa), fecha_referencia=datetime.date(2027, 3, 1)
        )
        validador._validarSalaActiva()

        self.assertEqual(validador.errores, [])


# =====================================================
# VALIDAR DATOS OBLIGATORIOS
# =====================================================

class ValidarDatosObligatoriosTests(TestCase):
    """
    Pruebas de ValidadorAgendamiento._validarDatosObligatorios():
    los datos técnicos mínimos que una Audiencia necesita.
    """

    def test_audiencia_completamente_vacia_reporta_todos_los_errores(self):
        validador = ValidadorAgendamiento(
            Audiencia(), fecha_referencia=datetime.date(2027, 3, 1)
        )
        validador._validarDatosObligatorios()

        self.assertIn("Falta indicar la causa.", validador.errores)
        self.assertIn("Falta indicar el tipo de audiencia.", validador.errores)
        self.assertIn("Falta indicar la sala.", validador.errores)
        self.assertIn("Falta indicar la fecha.", validador.errores)
        self.assertIn("Falta indicar el bloque de inicio.", validador.errores)
        self.assertIn(
            "La cantidad de bloques debe ser al menos 1.", validador.errores
        )

    def test_cantidad_bloques_cero_es_invalida(self):
        validador = ValidadorAgendamiento(
            Audiencia(cantidadBloques=0), fecha_referencia=datetime.date(2027, 3, 1)
        )
        validador._validarDatosObligatorios()

        self.assertIn(
            "La cantidad de bloques debe ser al menos 1.", validador.errores
        )


# =====================================================
# VALIDAR PLAZO LEGAL
# =====================================================

class ValidarPlazoLegalTests(TestCase):
    """
    Pruebas de ValidadorAgendamiento.validarPlazoLegal(), incluida
    la interpretación de plazoMinimo/plazoMaximo opcionales.
    """

    def setUp(self):
        self.competencia = Competencia.objects.create(nombre="Competencia Plazo Tests")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Plazo Tests", activo=True
        )
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="5003-2027",
            ruc="2700050030-3",
            caratulado="Causa Plazo Tests",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9804, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )
        self.fecha_referencia = datetime.date(2027, 3, 1)

    def _audiencia(self, fecha):
        return Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=fecha,
        )

    def test_advierte_si_no_existe_regla_configurada(self):
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_referencia + datetime.timedelta(days=10)),
            fecha_referencia=self.fecha_referencia,
        )
        validador.validarPlazoLegal()

        self.assertTrue(
            any(
                "No existe un plazo legal configurado" in a
                for a in validador.advertencias
            )
        )

    def test_fecha_dentro_del_rango_configurado_no_genera_advertencia(self):
        ReglaAgendamiento.objects.create(
            competencia=self.competencia,
            tipoAudiencia=self.tipo_audiencia,
            plazoMinimo=5,
            plazoMaximo=20,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_referencia + datetime.timedelta(days=10)),
            fecha_referencia=self.fecha_referencia,
        )
        validador.validarPlazoLegal()

        self.assertEqual(validador.advertencias, [])

    def test_fecha_fuera_del_plazo_maximo_genera_advertencia(self):
        ReglaAgendamiento.objects.create(
            competencia=self.competencia,
            tipoAudiencia=self.tipo_audiencia,
            plazoMinimo=5,
            plazoMaximo=20,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_referencia + datetime.timedelta(days=30)),
            fecha_referencia=self.fecha_referencia,
        )
        validador.validarPlazoLegal()

        self.assertTrue(
            any(
                "fuera del plazo legal configurado" in a
                for a in validador.advertencias
            )
        )

    def test_solo_plazo_minimo_configurado_no_limita_por_arriba(self):
        ReglaAgendamiento.objects.create(
            competencia=self.competencia,
            tipoAudiencia=self.tipo_audiencia,
            plazoMinimo=5,
            plazoMaximo=None,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_referencia + datetime.timedelta(days=300)),
            fecha_referencia=self.fecha_referencia,
        )
        validador.validarPlazoLegal()

        self.assertEqual(validador.advertencias, [])

    def test_solo_plazo_maximo_configurado_no_exige_piso_minimo(self):
        ReglaAgendamiento.objects.create(
            competencia=self.competencia,
            tipoAudiencia=self.tipo_audiencia,
            plazoMinimo=None,
            plazoMaximo=30,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_referencia + datetime.timedelta(days=1)),
            fecha_referencia=self.fecha_referencia,
        )
        validador.validarPlazoLegal()

        self.assertEqual(validador.advertencias, [])


# =====================================================
# VALIDAR DÍA HÁBIL (días habilitados / no disponibles)
# =====================================================

class ValidarDiaHabilTests(TestCase):
    """
    Pruebas de ValidadorAgendamiento.validarDiaHabil(): día de
    atención por competencia y días marcados como no disponibles.
    """

    def setUp(self):
        self.competencia = Competencia.objects.create(nombre="Competencia Dia Habil Tests")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Dia Habil Tests", activo=True
        )
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="5004-2027",
            ruc="2700050040-4",
            caratulado="Causa Dia Habil Tests",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9805, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )
        # 2027-03-15 es lunes.
        self.fecha_lunes = datetime.date(2027, 3, 15)

    def _audiencia(self, fecha):
        return Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=fecha,
        )

    def test_dia_no_configurado_como_atencion_genera_advertencia(self):
        # No se crea ningún DiaAtencion para "competencia": el
        # lunes no está habilitado para esta competencia.
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_lunes), fecha_referencia=self.fecha_lunes
        )
        validador.validarDiaHabil()

        self.assertTrue(
            any(
                "no está configurado como día habitual de atención" in a
                for a in validador.advertencias
            )
        )

    def test_dia_configurado_como_atencion_no_genera_esa_advertencia(self):
        DiaAtencion.objects.create(
            competencia=self.competencia, diaSemana=DiaSemana.LUNES, activa=True
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_lunes), fecha_referencia=self.fecha_lunes
        )
        validador.validarDiaHabil()

        self.assertFalse(
            any(
                "no está configurado como día habitual de atención" in a
                for a in validador.advertencias
            )
        )

    def test_dia_marcado_no_disponible_genera_advertencia_con_motivo(self):
        DiaAtencion.objects.create(
            competencia=self.competencia, diaSemana=DiaSemana.LUNES, activa=True
        )
        DiaNoDisponible.objects.create(
            fecha=self.fecha_lunes,
            motivo="Feriado nacional de prueba",
            tipo=TipoDiaNoDisponible.FERIADO,
            activo=True,
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_lunes), fecha_referencia=self.fecha_lunes
        )
        validador.validarDiaHabil()

        self.assertTrue(
            any(
                "marcado como no disponible" in a and "Feriado nacional de prueba" in a
                for a in validador.advertencias
            )
        )

    def test_dia_no_disponible_inactivo_no_genera_advertencia(self):
        DiaAtencion.objects.create(
            competencia=self.competencia, diaSemana=DiaSemana.LUNES, activa=True
        )
        DiaNoDisponible.objects.create(
            fecha=self.fecha_lunes,
            motivo="Feriado desactivado",
            tipo=TipoDiaNoDisponible.FERIADO,
            activo=False,
        )
        validador = ValidadorAgendamiento(
            self._audiencia(self.fecha_lunes), fecha_referencia=self.fecha_lunes
        )
        validador.validarDiaHabil()

        self.assertFalse(
            any("marcado como no disponible" in a for a in validador.advertencias)
        )


# =====================================================
# CASO COMPLETO VÁLIDO
# =====================================================

class ValidadorAgendamientoCasoValidoTests(TestCase):
    """
    Prueba de caso completo: una audiencia que cumple TODAS las
    reglas (sala activa, sin conflicto, dentro de plazo, día
    habilitado, sin día no disponible) no debe generar ni errores
    ni advertencias -"una fecha válida debe ser aceptada".
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_caso_valido",
            email="caso_valido@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Caso Valido",
        )
        self.competencia = Competencia.objects.create(nombre="Competencia Caso Valido Tests")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Caso Valido Tests", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Caso Valido Tests", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="5005-2027",
            ruc="2700050050-5",
            caratulado="Causa Caso Valido Tests",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9806, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )
        self.fecha_referencia = datetime.date(2027, 3, 1)
        # 2027-03-15 es lunes.
        self.fecha_audiencia = datetime.date(2027, 3, 15)

        DiaAtencion.objects.create(
            competencia=self.competencia, diaSemana=DiaSemana.LUNES, activa=True
        )
        ReglaAgendamiento.objects.create(
            competencia=self.competencia,
            tipoAudiencia=self.tipo_audiencia,
            plazoMinimo=1,
            plazoMaximo=60,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )

    def test_audiencia_valida_no_genera_errores_ni_advertencias(self):
        audiencia = Audiencia(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=self.fecha_audiencia,
        )
        resultado = ValidadorAgendamiento(
            audiencia, fecha_referencia=self.fecha_referencia
        ).validar()

        self.assertEqual(resultado["errores"], [])
        self.assertEqual(resultado["advertencias"], [])


# =====================================================
# GENERADOR DE PROPUESTA DE FECHA
# =====================================================

class GeneradorPropuestaFechaTests(TestCase):
    """
    Pruebas de GeneradorPropuestaFecha: propuesta/generación
    automática de fechas.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_propuestas",
            email="propuestas@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Propuestas",
        )
        self.competencia = Competencia.objects.create(nombre="Competencia Propuesta Tests")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Propuesta Tests", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Propuesta Tests", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="5006-2027",
            ruc="2700050060-6",
            caratulado="Causa Propuesta Tests",
        )

        ConfiguracionAgendamiento.objects.create(
            horaInicioJornada=datetime.time(8, 0),
            horaTerminoJornada=datetime.time(18, 0),
            duracionBloque=30,
            horizonteBusquedaDias=60,
        )

        # Habilita lunes a viernes para esta competencia, para no
        # depender de en qué día caiga cada fecha de referencia.
        for dia, _ in DiaSemana.choices:
            DiaAtencion.objects.create(
                competencia=self.competencia, diaSemana=dia, activa=True
            )

    def test_sala_inactiva_lanza_valueerror(self):
        sala_inactiva = Sala.objects.create(nombre="Sala Propuesta Inactiva", activa=False)
        generador = GeneradorPropuestaFecha(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=sala_inactiva,
            cantidadBloques=1,
            fecha_referencia=datetime.date(2027, 3, 1),
        )

        with self.assertRaises(ValueError):
            generador.generar()

    def test_genera_al_menos_una_propuesta_con_bloques_libres(self):
        BloqueHorario.objects.create(
            orden=9901, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            permiteAgendamientoAutomatico=True,
        )
        generador = GeneradorPropuestaFecha(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            cantidadBloques=1,
            # 2027-03-14 es domingo: la primera fecha candidata
            # (día siguiente) es el lunes 15.
            fecha_referencia=datetime.date(2027, 3, 14),
        )
        propuestas = generador.generar()

        self.assertGreaterEqual(len(propuestas), 1)
        self.assertEqual(propuestas[0]["cantidadBloques"], 1)
        self.assertEqual(propuestas[0]["horaInicio"], datetime.time(9, 0))

    def test_no_propone_un_bloque_de_inicio_si_hay_un_hueco_intermedio_ocupado(self):
        # 09:00 libre, 09:30 SE OCUPARÁ, 10:00 libre, 10:30 libre.
        # Al pedir 2 bloques consecutivos, el único rango de 2
        # bloques libres y consecutivos que queda es 10:00-11:00;
        # NUNCA debe proponerse 09:00 como inicio (09:00+09:30
        # se solaparía con el bloque ocupado).
        bloque_0900 = BloqueHorario.objects.create(
            orden=9911, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            permiteAgendamientoAutomatico=True,
        )
        bloque_0930 = BloqueHorario.objects.create(
            orden=9912, horaInicio=datetime.time(9, 30), horaTermino=datetime.time(10, 0),
            permiteAgendamientoAutomatico=True,
        )
        BloqueHorario.objects.create(
            orden=9913, horaInicio=datetime.time(10, 0), horaTermino=datetime.time(10, 30),
            permiteAgendamientoAutomatico=True,
        )
        BloqueHorario.objects.create(
            orden=9914, horaInicio=datetime.time(10, 30), horaTermino=datetime.time(11, 0),
            permiteAgendamientoAutomatico=True,
        )

        fecha_objetivo = datetime.date(2027, 3, 15)  # lunes

        Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=bloque_0930,
            cantidadBloques=1,
            fecha=fecha_objetivo,
            horaInicio=bloque_0930.horaInicio,
            horaTermino=bloque_0930.horaTermino,
            usuarioCreacion=self.usuario,
        )

        generador = GeneradorPropuestaFecha(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            cantidadBloques=2,
            fecha_referencia=datetime.date(2027, 3, 14),  # domingo
        )
        propuestas = generador.generar()

        propuestas_del_dia_objetivo = [
            p for p in propuestas if p["fecha"] == fecha_objetivo
        ]
        self.assertEqual(len(propuestas_del_dia_objetivo), 1)
        self.assertEqual(
            propuestas_del_dia_objetivo[0]["horaInicio"], datetime.time(10, 0)
        )
        self.assertNotEqual(
            propuestas_del_dia_objetivo[0]["bloqueInicio"], bloque_0900
        )

    def test_no_devuelve_mas_de_tres_propuestas(self):
        BloqueHorario.objects.create(
            orden=9921, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            permiteAgendamientoAutomatico=True,
        )
        generador = GeneradorPropuestaFecha(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            cantidadBloques=1,
            fecha_referencia=datetime.date(2027, 3, 14),  # domingo
        )
        propuestas = generador.generar()

        self.assertLessEqual(len(propuestas), 3)
        self.assertEqual(len(propuestas), 3)

    def test_propuesta_fuera_del_plazo_legal_se_marca_como_tal(self):
        BloqueHorario.objects.create(
            orden=9931, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            permiteAgendamientoAutomatico=True,
        )
        # plazoMaximo=0 (días corridos): ninguna fecha futura queda
        # nunca dentro de plazo, así que las 3 propuestas devueltas
        # deben venir marcadas fueraDePlazo=True.
        ReglaAgendamiento.objects.create(
            competencia=self.competencia,
            tipoAudiencia=self.tipo_audiencia,
            plazoMinimo=None,
            plazoMaximo=0,
            unidadPlazo=TipoPlazo.CORRIDO,
            activa=True,
        )
        generador = GeneradorPropuestaFecha(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            cantidadBloques=1,
            fecha_referencia=datetime.date(2027, 3, 14),  # domingo
        )
        propuestas = generador.generar()

        self.assertGreater(len(propuestas), 0)
        for propuesta in propuestas:
            self.assertTrue(propuesta["fueraDePlazo"])
            self.assertTrue(
                any("fuera del plazo legal" in a for a in propuesta["advertencias"])
            )
