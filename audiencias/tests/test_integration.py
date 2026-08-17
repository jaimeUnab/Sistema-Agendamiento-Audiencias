"""
Pruebas de INTEGRACIÓN de la aplicación Audiencias.

A diferencia de test_services_unit.py y test_forms_unit.py (que
llaman directamente a servicios/formularios en Python), estas
pruebas recorren el flujo HTTP completo usando el cliente de
pruebas de Django (self.client): login real contra la vista de
autenticación, envío de formularios tal como lo haría el
navegador, y verificación de que los datos efectivamente quedan
almacenados en la base de datos y de que las distintas partes del
sistema (formulario, disponibilidad, reglas de agendamiento,
propuestas, agenda, trazabilidad) trabajan correctamente en
conjunto.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bloques.models import BloqueHorario, ConfiguracionAgendamiento
from causas.models import Causa
from competencias.models import Competencia
from reglas_agendamiento.models import DiaAtencion, DiaSemana
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

from audiencias.models import (
    AccionTrazabilidad,
    Audiencia,
    EstadoAudiencia,
    RegistroTrazabilidad,
)

Usuario = get_user_model()


# =====================================================
# LOGIN (primer paso del flujo)
# =====================================================

class LoginIntegrationTests(TestCase):
    """
    Prueba de integración del inicio de sesión: recorre la vista
    real de login (UsuarioLoginView), no un atajo de prueba.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_login_integracion",
            email="login_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Login Integración",
        )

    def test_login_exitoso_autentica_al_usuario(self):
        # El formulario de login (templates/usuarios/login.html)
        # envía el campo "username" con el valor de USERNAME_FIELD
        # (email en este proyecto): así autentica AuthenticationForm
        # con cualquier modelo de usuario personalizado.
        respuesta = self.client.post(
            reverse("login"),
            {"username": self.usuario.email, "password": "ClaveSegura123"},
            follow=True,
        )

        self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
        self.assertEqual(respuesta.wsgi_request.user.pk, self.usuario.pk)

    def test_login_con_contrasena_incorrecta_no_autentica(self):
        respuesta = self.client.post(
            reverse("login"),
            {"username": self.usuario.email, "password": "ClaveIncorrecta"},
        )

        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_vista_protegida_redirige_al_login_si_no_hay_sesion(self):
        # registrar_audiencia tiene @login_required: un cliente
        # anónimo debe ser redirigido al login, no ver el formulario.
        respuesta = self.client.get(reverse("registrar_audiencia"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)


# =====================================================
# FLUJO COMPLETO: LOGIN -> FORMULARIO -> DISPONIBILIDAD ->
# REGLAS DE AGENDAMIENTO -> REGISTRO -> TRAZABILIDAD
# =====================================================

class FlujoCompletoRegistroAudienciaIntegrationTests(TestCase):
    """
    Recorre el flujo real que sigue un funcionario para programar
    una audiencia nueva: inicia sesión, abre el formulario, busca
    la causa, consulta disponibilidad, y registra la audiencia
    (incluido el caso con advertencias de negocio que exigen
    confirmación explícita). Verifica al final que la Audiencia
    quedó almacenada en la base de datos con los datos correctos,
    y que se registró su trazabilidad de creación.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_flujo_integracion",
            email="flujo_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Flujo Integración",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Flujo Integración", activa=True
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Flujo Integración", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Flujo Integración", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="6001-2027",
            ruc="2700060010-1",
            caratulado="Causa Flujo Integración",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9601,
            horaInicio=datetime.time(9, 0),
            horaTermino=datetime.time(9, 30),
        )
        # 2027-04-01 es jueves.
        DiaAtencion.objects.create(
            competencia=self.competencia, diaSemana=DiaSemana.JUEVES, activa=True
        )
        # Deliberadamente NO se crea ninguna ReglaAgendamiento: el
        # propio ValidadorAgendamiento debe advertir "no existe un
        # plazo legal configurado", y el flujo debe exigir
        # confirmación antes de guardar (ver más abajo).

        self.client.login(
            username=self.usuario.email, password="ClaveSegura123"
        )

    def test_flujo_completo_registra_la_audiencia_y_su_trazabilidad(self):
        # -----------------------------------------------
        # 1) El usuario ya inició sesión (setUp). Entra al
        #    formulario de nueva audiencia.
        # -----------------------------------------------
        respuesta_formulario = self.client.get(reverse("registrar_audiencia"))
        self.assertEqual(respuesta_formulario.status_code, 200)
        self.assertTemplateUsed(respuesta_formulario, "audiencias/formulario.html")

        # -----------------------------------------------
        # 2) Busca la causa por competencia + RIT.
        # -----------------------------------------------
        respuesta_causa = self.client.post(
            reverse("registrar_audiencia"),
            {
                "buscar_causa": "1",
                "competencia": self.competencia.pk,
                "rit": self.causa.rit,
            },
        )
        self.assertEqual(respuesta_causa.status_code, 200)
        self.assertEqual(respuesta_causa.context["causa_encontrada"], self.causa)

        # -----------------------------------------------
        # 3) Consulta la disponibilidad de agenda (sala + fecha):
        #    el bloque debe aparecer "Disponible" (sin audiencia
        #    todavía).
        # -----------------------------------------------
        datos_comunes = {
            "competencia": self.competencia.pk,
            "rit": self.causa.rit,
            "tipoAudiencia": self.tipo_audiencia.pk,
            "sala": self.sala.pk,
            "fecha": "2027-04-01",
            "cantidadBloques": 1,
            "bloqueInicio": self.bloque.pk,
        }

        respuesta_disponibilidad = self.client.post(
            reverse("ver_disponibilidad_audiencia"), datos_comunes
        )
        self.assertEqual(respuesta_disponibilidad.status_code, 200)
        disponibilidad = respuesta_disponibilidad.context["disponibilidad"]
        fila_del_bloque = next(
            item for item in disponibilidad if item["bloque"] == self.bloque
        )
        self.assertIsNone(fila_del_bloque["audiencia"])

        # -----------------------------------------------
        # 4) Primer intento de registro: como no existe una
        #    ReglaAgendamiento para esta combinación, se aplican
        #    las reglas de agendamiento y ValidadorAgendamiento
        #    devuelve una advertencia -no guarda nada todavía,
        #    exige confirmación explícita.
        # -----------------------------------------------
        respuesta_advertencia = self.client.post(
            reverse("registrar_audiencia"), datos_comunes
        )
        self.assertEqual(respuesta_advertencia.status_code, 200)
        self.assertTrue(respuesta_advertencia.context["requiere_confirmacion"])
        self.assertTrue(
            any(
                "No existe un plazo legal configurado" in a
                for a in respuesta_advertencia.context["advertencias"]
            )
        )
        self.assertEqual(Audiencia.objects.count(), 0)

        # -----------------------------------------------
        # 5) El usuario confirma pese a la advertencia: recién ahí
        #    se registra la audiencia.
        # -----------------------------------------------
        respuesta_confirmacion = self.client.post(
            reverse("registrar_audiencia"),
            {**datos_comunes, "confirmar_advertencias": "1"},
            follow=True,
        )
        self.assertRedirects(respuesta_confirmacion, reverse("registrar_audiencia"))

        # -----------------------------------------------
        # 6) La audiencia quedó almacenada correctamente en la
        #    base de datos, con los datos esperados.
        # -----------------------------------------------
        audiencia_creada = Audiencia.objects.get(causa=self.causa)
        self.assertEqual(audiencia_creada.sala, self.sala)
        self.assertEqual(audiencia_creada.tipoAudiencia, self.tipo_audiencia)
        self.assertEqual(audiencia_creada.bloqueInicio, self.bloque)
        self.assertEqual(audiencia_creada.cantidadBloques, 1)
        self.assertEqual(audiencia_creada.fecha, datetime.date(2027, 4, 1))
        self.assertEqual(audiencia_creada.horaInicio, datetime.time(9, 0))
        self.assertEqual(audiencia_creada.horaTermino, datetime.time(9, 30))
        self.assertEqual(audiencia_creada.usuarioCreacion, self.usuario)

        # -----------------------------------------------
        # 7) Se registró la trazabilidad de creación.
        # -----------------------------------------------
        self.assertTrue(
            RegistroTrazabilidad.objects.filter(
                audiencia=audiencia_creada,
                usuario=self.usuario,
                accion=AccionTrazabilidad.CREACION,
            ).exists()
        )

        # -----------------------------------------------
        # 8) Si se vuelve a consultar la disponibilidad de esa
        #    sala/fecha, el bloque ahora debe verse "Ocupado" por
        #    la audiencia recién creada.
        # -----------------------------------------------
        respuesta_disponibilidad_final = self.client.post(
            reverse("ver_disponibilidad_audiencia"), datos_comunes
        )
        disponibilidad_final = respuesta_disponibilidad_final.context["disponibilidad"]
        fila_final = next(
            item for item in disponibilidad_final if item["bloque"] == self.bloque
        )
        self.assertEqual(fila_final["audiencia"], audiencia_creada)

    def test_registro_bloqueado_por_sala_inactiva_no_crea_audiencia(self):
        sala_inactiva = Sala.objects.create(
            nombre="Sala Flujo Inactiva", activa=False
        )
        # AudienciaForm filtra por activa=True en su __init__, así
        # que una sala inactiva no puede llegar mediante el propio
        # queryset del formulario; se envía igual su ID para
        # confirmar que, aunque llegara manipulado, el servidor la
        # rechaza igual (ValidadorAgendamiento la vuelve a validar).
        respuesta = self.client.post(
            reverse("registrar_audiencia"),
            {
                "competencia": self.competencia.pk,
                "rit": self.causa.rit,
                "tipoAudiencia": self.tipo_audiencia.pk,
                "sala": sala_inactiva.pk,
                "fecha": "2027-04-01",
                "cantidadBloques": 1,
                "bloqueInicio": self.bloque.pk,
            },
        )

        self.assertEqual(Audiencia.objects.count(), 0)
        self.assertFalse(respuesta.context.get("requiere_confirmacion"))


# =====================================================
# CONSULTA DE AGENDA
# =====================================================

class ConsultaAgendaIntegrationTests(TestCase):
    """
    Prueba de integración de la agenda diaria (agenda_diaria):
    consulta de solo lectura de las audiencias PROGRAMADAS de una
    fecha.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_agenda_integracion",
            email="agenda_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Agenda Integración",
        )
        self.competencia = Competencia.objects.create(nombre="Competencia Agenda Integración")
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Agenda Integración", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Agenda Integración", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="6002-2027",
            ruc="2700060020-2",
            caratulado="Causa Agenda Integración",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9602, horaInicio=datetime.time(10, 0), horaTermino=datetime.time(10, 30)
        )
        self.fecha = datetime.date(2027, 4, 5)

        self.audiencia = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=self.fecha,
            horaInicio=self.bloque.horaInicio,
            horaTermino=self.bloque.horaTermino,
            usuarioCreacion=self.usuario,
        )

        self.client.login(username=self.usuario.email, password="ClaveSegura123")

    def test_agenda_muestra_la_audiencia_programada_de_la_fecha_consultada(self):
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?fecha={self.fecha.isoformat()}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["hay_audiencias"])
        self.assertContains(respuesta, self.causa.rit)
        self.assertContains(respuesta, self.causa.caratulado)

    def test_agenda_de_una_fecha_sin_audiencias_no_muestra_ninguna(self):
        fecha_sin_audiencias = self.fecha + datetime.timedelta(days=1)

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?fecha={fecha_sin_audiencias.isoformat()}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["hay_audiencias"])
        self.assertNotContains(respuesta, self.causa.rit)


# =====================================================
# PROPUESTA AUTOMÁTICA DE FECHAS
# =====================================================

class ProponerFechasIntegrationTests(TestCase):
    """
    Prueba de integración de la búsqueda automática de propuestas
    (proponer_fechas_audiencia), de punta a punta vía HTTP.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_proponer_integracion",
            email="proponer_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Proponer Integración",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Proponer Integración"
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Proponer Integración", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Proponer Integración", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="6003-2027",
            ruc="2700060030-3",
            caratulado="Causa Proponer Integración",
        )
        BloqueHorario.objects.create(
            orden=9603, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30),
            permiteAgendamientoAutomatico=True,
        )
        ConfiguracionAgendamiento.objects.create(
            horaInicioJornada=datetime.time(8, 0),
            horaTerminoJornada=datetime.time(18, 0),
            duracionBloque=30,
            horizonteBusquedaDias=60,
        )
        for dia, _ in DiaSemana.choices:
            DiaAtencion.objects.create(
                competencia=self.competencia, diaSemana=dia, activa=True
            )

        self.client.login(username=self.usuario.email, password="ClaveSegura123")

    def test_solicitar_propuestas_devuelve_al_menos_una_propuesta(self):
        respuesta = self.client.post(
            reverse("proponer_fechas_audiencia"),
            {
                "competencia": self.competencia.pk,
                "rit": self.causa.rit,
                "tipoAudiencia": self.tipo_audiencia.pk,
                "sala": self.sala.pk,
                "cantidadBloques": 1,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        propuestas = respuesta.context["propuestas"]
        self.assertGreaterEqual(len(propuestas), 1)
        self.assertContains(respuesta, "Propuesta")

    def test_solicitar_propuestas_con_sala_inactiva_no_devuelve_propuestas(self):
        sala_inactiva = Sala.objects.create(
            nombre="Sala Proponer Inactiva", activa=False
        )

        respuesta = self.client.post(
            reverse("proponer_fechas_audiencia"),
            {
                "competencia": self.competencia.pk,
                "rit": self.causa.rit,
                "tipoAudiencia": self.tipo_audiencia.pk,
                "sala": sala_inactiva.pk,
                "cantidadBloques": 1,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("propuestas", respuesta.context)


# =====================================================
# DEJAR SIN EFECTO (BAJA LÓGICA) - FLUJO HTTP COMPLETO
# =====================================================

class DejarSinEfectoAudienciaIntegrationTests(TestCase):
    """
    Prueba de integración del flujo real de "Dejar sin efecto"
    desde la agenda: envío POST tal como lo hace el modal Bootstrap
    de templates/audiencias/agenda.html hacia
    dejar_sin_efecto_audiencia, verificando que el resultado quede
    correctamente reflejado en la base de datos y en la agenda.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_baja_integracion",
            email="baja_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Baja Integración",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Baja Integración"
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Baja Integración", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Baja Integración", activa=True)
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="7002-2027",
            ruc="2700070020-2",
            caratulado="Causa Baja Integración",
        )
        self.fecha = datetime.date(2027, 5, 10)

        self.bloque_1 = BloqueHorario.objects.create(
            orden=9711, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )
        self.bloque_2 = BloqueHorario.objects.create(
            orden=9712, horaInicio=datetime.time(9, 30), horaTermino=datetime.time(10, 0)
        )

        self.audiencia = Audiencia.objects.create(
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

        # Segunda audiencia PROGRAMADA, el mismo día, que no debe
        # verse afectada por dar de baja la primera.
        self.otra_audiencia = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque_2,
            cantidadBloques=1,
            fecha=self.fecha,
            horaInicio=self.bloque_2.horaInicio,
            horaTermino=self.bloque_2.horaTermino,
            usuarioCreacion=self.usuario,
        )

        self.client.login(username=self.usuario.email, password="ClaveSegura123")

    def test_vista_dejar_sin_efecto_requiere_login(self):
        self.client.logout()

        respuesta = self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {"audiencia_id": self.audiencia.pk, "motivo_seleccionado": "SUSPENSION"},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)
        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.PROGRAMADA)

    def test_flujo_http_dejar_sin_efecto_con_motivo_valido(self):
        respuesta = self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "SUSPENSION",
            },
            follow=True,
        )

        self.assertRedirects(
            respuesta,
            f"{reverse('agenda_diaria')}?fecha={self.fecha.isoformat()}",
        )
        self.assertContains(respuesta, "Audiencia dejada sin efecto correctamente.")

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.ELIMINADA)
        self.assertEqual(self.audiencia.motivoBaja, "Suspensión de la audiencia")

        self.assertTrue(
            RegistroTrazabilidad.objects.filter(
                audiencia=self.audiencia,
                usuario=self.usuario,
                accion=AccionTrazabilidad.BAJA,
            ).exists()
        )

    def test_flujo_http_motivo_otro_con_explicacion_se_guarda_combinado(self):
        self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "OTRO",
                "motivo_otro": "Falla eléctrica en el edificio.",
            },
        )

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.ELIMINADA)
        self.assertEqual(
            self.audiencia.motivoBaja, "Otro: Falla eléctrica en el edificio."
        )

    def test_flujo_http_sin_motivo_no_aplica_la_baja(self):
        respuesta = self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {"audiencia_id": self.audiencia.pk},
            follow=True,
        )

        self.assertContains(respuesta, "Debes seleccionar un motivo.")

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.PROGRAMADA)
        self.assertFalse(
            RegistroTrazabilidad.objects.filter(
                audiencia=self.audiencia, accion=AccionTrazabilidad.BAJA
            ).exists()
        )

    def test_flujo_http_motivo_otro_sin_explicacion_no_aplica_la_baja(self):
        respuesta = self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {"audiencia_id": self.audiencia.pk, "motivo_seleccionado": "OTRO"},
            follow=True,
        )

        self.assertContains(
            respuesta,
            "Debes ingresar una explicación cuando el motivo es &#x27;Otro&#x27;.",
        )

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.PROGRAMADA)

    def test_no_se_permite_dejar_sin_efecto_una_audiencia_ya_eliminada(self):
        # Primera baja: exitosa.
        self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "REPROGRAMACION",
            },
        )

        # Segundo intento sobre la misma audiencia, ya ELIMINADA.
        respuesta = self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "ERROR_AGENDAMIENTO",
            },
            follow=True,
        )

        self.assertContains(
            respuesta, "Esta audiencia ya fue dejada sin efecto anteriormente."
        )

        # El motivo de la primera baja no fue sobreescrito.
        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.motivoBaja, "Reprogramación")
        self.assertEqual(
            RegistroTrazabilidad.objects.filter(
                audiencia=self.audiencia, accion=AccionTrazabilidad.BAJA
            ).count(),
            1,
        )

    def test_audiencia_eliminada_no_aparece_en_agenda_diaria(self):
        self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "SOLICITUD_TRIBUNAL",
            },
        )

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?fecha={self.fecha.isoformat()}"
        )

        audiencias_mostradas = [
            audiencia
            for item in respuesta.context["agenda_por_sala"]
            for audiencia in item["audiencias"]
        ]

        # La audiencia dada de baja ya no aparece...
        self.assertNotIn(self.audiencia, audiencias_mostradas)
        # ...pero la otra audiencia PROGRAMADA del mismo día sigue
        # apareciendo con normalidad.
        self.assertIn(self.otra_audiencia, audiencias_mostradas)
