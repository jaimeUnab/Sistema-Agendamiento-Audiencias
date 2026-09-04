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

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import DatabaseError
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

    # -------------------------------------------------
    # ver_disponibilidad_audiencia: sala/fecha vacías o con un ID
    # no numérico no deben producir un ValueError (bug real
    # corregido), sino un mensaje amigable y específico, sin
    # ejecutar ninguna consulta de disponibilidad, conservando lo
    # que el usuario ya había ingresado en el formulario.
    # -------------------------------------------------

    def test_disponibilidad_sin_sala_muestra_mensaje_sin_excepcion(self):
        datos = {
            "competencia": self.competencia.pk,
            "rit": self.causa.rit,
            "tipoAudiencia": self.tipo_audiencia.pk,
            "sala": "",
            "fecha": "2027-04-01",
            "cantidadBloques": 1,
            "bloqueInicio": self.bloque.pk,
        }

        respuesta = self.client.post(reverse("ver_disponibilidad_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "audiencias/formulario.html")

        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar una sala antes de buscar disponibilidad.",
            mensajes,
        )

        # No se llegó a ejecutar la consulta de disponibilidad.
        self.assertNotIn("disponibilidad", respuesta.context)

        # El formulario conserva lo que el usuario ya había ingresado
        # (no se perdió el RIT ni el tipo de audiencia ya elegidos).
        self.assertEqual(respuesta.context["form"].data.get("rit"), self.causa.rit)
        self.assertEqual(
            respuesta.context["form"].data.get("tipoAudiencia"),
            str(self.tipo_audiencia.pk),
        )

    def test_disponibilidad_sin_fecha_muestra_mensaje_sin_excepcion(self):
        datos = {
            "competencia": self.competencia.pk,
            "rit": self.causa.rit,
            "tipoAudiencia": self.tipo_audiencia.pk,
            "sala": self.sala.pk,
            "fecha": "",
            "cantidadBloques": 1,
            "bloqueInicio": self.bloque.pk,
        }

        respuesta = self.client.post(reverse("ver_disponibilidad_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "audiencias/formulario.html")

        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar una fecha antes de buscar disponibilidad.",
            mensajes,
        )
        self.assertNotIn("disponibilidad", respuesta.context)
        self.assertEqual(respuesta.context["form"].data.get("rit"), self.causa.rit)

    def test_disponibilidad_sala_no_numerica_muestra_mensaje_sin_excepcion(self):
        datos = {
            "competencia": self.competencia.pk,
            "rit": self.causa.rit,
            "tipoAudiencia": self.tipo_audiencia.pk,
            "sala": "abc",
            "fecha": "2027-04-01",
            "cantidadBloques": 1,
            "bloqueInicio": self.bloque.pk,
        }

        respuesta = self.client.post(reverse("ver_disponibilidad_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "audiencias/formulario.html")

        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar una sala antes de buscar disponibilidad.",
            mensajes,
        )
        self.assertNotIn("disponibilidad", respuesta.context)

    def test_disponibilidad_tipo_audiencia_no_numerico_no_bloquea(self):
        """
        tipoAudiencia sigue siendo opcional en esta vista: un valor
        no numérico ya no debe lanzar ValueError (antes de esta
        corrección, un id no numérico rompía igual que uno vacío),
        pero tampoco debe bloquear la consulta -sala y fecha son
        válidas, así que la tabla de disponibilidad debe mostrarse
        con normalidad, simplemente sin la previsualización
        "Seleccionado".
        """
        datos = {
            "competencia": self.competencia.pk,
            "rit": self.causa.rit,
            "tipoAudiencia": "abc",
            "sala": self.sala.pk,
            "fecha": "2027-04-01",
            "cantidadBloques": 1,
            "bloqueInicio": self.bloque.pk,
        }

        respuesta = self.client.post(reverse("ver_disponibilidad_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("disponibilidad", respuesta.context)
        self.assertIsNone(respuesta.context["tipo_audiencia_seleccionado"])


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
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["hay_audiencias"])
        self.assertContains(respuesta, self.causa.rit)
        self.assertContains(respuesta, self.causa.caratulado)

    def test_agenda_de_una_fecha_sin_audiencias_no_muestra_ninguna(self):
        fecha_sin_audiencias = self.fecha + datetime.timedelta(days=1)

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={fecha_sin_audiencias.isoformat()}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["hay_audiencias"])
        self.assertNotContains(respuesta, self.causa.rit)

    def test_agenda_sin_sala_seleccionada_no_muestra_ninguna_audiencia(self):
        """
        Sin "sala" en la URL (primer ingreso a la pantalla, o
        cualquier consulta que no la incluya), la agenda no debe
        mostrar automáticamente todas las salas ni ninguna audiencia
        -pedido explícito-, aunque exista una audiencia PROGRAMADA
        ese mismo día.
        """
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?fecha={self.fecha.isoformat()}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["sala_seleccionada"])
        self.assertFalse(respuesta.context["hay_audiencias"])
        self.assertNotContains(respuesta, self.causa.rit)
        self.assertContains(respuesta, "Seleccione una sala para ver su agenda.")

    def test_agenda_muestra_solo_las_audiencias_de_la_sala_seleccionada(self):
        """
        Con dos salas que tienen audiencias PROGRAMADAS el mismo día,
        seleccionar una de las dos debe mostrar únicamente sus
        audiencias, sin mezclar las de la otra sala.
        """
        otra_sala = Sala.objects.create(
            nombre="Otra Sala Agenda Integración", activa=True
        )
        otro_bloque = BloqueHorario.objects.create(
            orden=9603, horaInicio=datetime.time(11, 0), horaTermino=datetime.time(11, 30)
        )
        audiencia_otra_sala = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=otra_sala,
            bloqueInicio=otro_bloque,
            cantidadBloques=1,
            fecha=self.fecha,
            horaInicio=otro_bloque.horaInicio,
            horaTermino=otro_bloque.horaTermino,
            usuarioCreacion=self.usuario,
        )

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        # "otra_sala.nombre" sí aparece en el HTML -es una de las
        # opciones del <select> "Sala"-, así que no corresponde
        # comprobar su ausencia total en la respuesta: lo que importa
        # es que sus audiencias no queden listadas en el resultado.
        self.assertContains(respuesta, self.causa.rit)
        self.assertContains(respuesta, self.sala.nombre)
        audiencias_mostradas = list(respuesta.context["audiencias"])
        self.assertIn(self.audiencia, audiencias_mostradas)
        self.assertNotIn(audiencia_otra_sala, audiencias_mostradas)

    def test_agenda_sala_seleccionada_sin_audiencias_muestra_mensaje(self):
        fecha_sin_audiencias = self.fecha + datetime.timedelta(days=1)

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={fecha_sin_audiencias.isoformat()}"
        )

        self.assertContains(
            respuesta,
            "Sin audiencias programadas para esta sala en la fecha seleccionada.",
        )

    def test_flecha_izquierda_consulta_el_dia_anterior_conservando_la_sala(self):
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        dia_anterior = self.fecha - datetime.timedelta(days=1)
        self.assertContains(
            respuesta,
            f"?sala={self.sala.pk}&fecha={dia_anterior.isoformat()}",
        )

    def test_flecha_derecha_consulta_el_dia_siguiente_conservando_la_sala(self):
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        dia_siguiente = self.fecha + datetime.timedelta(days=1)
        self.assertContains(
            respuesta,
            f"?sala={self.sala.pk}&fecha={dia_siguiente.isoformat()}",
        )

    def test_selector_de_sala_de_la_agenda_no_ofrece_salas_inactivas(self):
        """
        El <select> "Sala" del filtro de la agenda debe ofrecer
        únicamente salas activa=True -mismo criterio que
        AudienciaForm ya aplica en "Nueva Audiencia" (ver
        audiencias/forms.py)-. Una sala inactiva no debe poder
        elegirse para consultar una agenda nueva.
        """
        sala_inactiva = Sala.objects.create(
            nombre="Sala Agenda Inactiva", activa=False
        )

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        salas_del_selector = list(respuesta.context["salas"])
        self.assertIn(self.sala, salas_del_selector)
        self.assertNotIn(sala_inactiva, salas_del_selector)

    def test_sala_desactivada_despues_de_registrada_no_altera_la_audiencia_historica(self):
        """
        Si la sala de una audiencia ya registrada se desactiva
        después, la audiencia histórica no se modifica ni se
        elimina (conserva su sala, fecha y horario tal cual), y su
        agenda sigue pudiendo consultarse -es la sala NUEVA la que
        deja de ofrecerse como opción del selector, no el acceso a
        lo ya agendado-.
        """
        sala_id_original = self.audiencia.sala_id
        fecha_original = self.audiencia.fecha
        hora_inicio_original = self.audiencia.horaInicio
        hora_termino_original = self.audiencia.horaTermino

        self.sala.activa = False
        self.sala.save(update_fields=["activa"])

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.sala_id, sala_id_original)
        self.assertEqual(self.audiencia.fecha, fecha_original)
        self.assertEqual(self.audiencia.horaInicio, hora_inicio_original)
        self.assertEqual(self.audiencia.horaTermino, hora_termino_original)
        self.assertTrue(Sala.objects.filter(pk=sala_id_original).exists())

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        # El acceso directo/histórico a esa sala sigue funcionando...
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.causa.rit)
        # ...pero ya no aparece entre las OPCIONES del selector.
        self.assertNotIn(self.sala, list(respuesta.context["salas"]))

    # =================================================
    # FILTRO DE ESTADO
    # =================================================

    def _crear_audiencia_eliminada(self, orden_bloque=9605):
        """
        Crea una segunda audiencia, en la misma sala/fecha que
        self.audiencia, ya con estado=ELIMINADA -para probar el
        filtro de estado sin depender del flujo HTTP de "Dejar sin
        efecto" (ya probado aparte en
        DejarSinEfectoAudienciaIntegrationTests)-.
        """
        bloque = BloqueHorario.objects.create(
            orden=orden_bloque,
            horaInicio=datetime.time(12, 0),
            horaTermino=datetime.time(12, 30),
        )
        return Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=bloque,
            cantidadBloques=1,
            fecha=self.fecha,
            horaInicio=bloque.horaInicio,
            horaTermino=bloque.horaTermino,
            estado=EstadoAudiencia.ELIMINADA,
            motivoBaja="Prueba de filtro de estado",
            usuarioCreacion=self.usuario,
        )

    def test_filtro_estado_todas_muestra_programadas_y_eliminadas(self):
        audiencia_eliminada = self._crear_audiencia_eliminada()

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={self.fecha.isoformat()}&estado="
        )

        audiencias_mostradas = list(respuesta.context["audiencias"])
        self.assertIn(self.audiencia, audiencias_mostradas)
        self.assertIn(audiencia_eliminada, audiencias_mostradas)

    def test_filtro_estado_programadas_excluye_dejadas_sin_efecto(self):
        audiencia_eliminada = self._crear_audiencia_eliminada()

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={self.fecha.isoformat()}&estado=PROGRAMADA"
        )

        audiencias_mostradas = list(respuesta.context["audiencias"])
        self.assertIn(self.audiencia, audiencias_mostradas)
        self.assertNotIn(audiencia_eliminada, audiencias_mostradas)

    def test_filtro_estado_dejadas_sin_efecto_excluye_programadas(self):
        audiencia_eliminada = self._crear_audiencia_eliminada()

        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={self.fecha.isoformat()}&estado=ELIMINADA"
        )

        audiencias_mostradas = list(respuesta.context["audiencias"])
        self.assertNotIn(self.audiencia, audiencias_mostradas)
        self.assertIn(audiencia_eliminada, audiencias_mostradas)

    def test_mensaje_vacio_es_especifico_segun_el_estado_filtrado(self):
        fecha_sin_audiencias = self.fecha + datetime.timedelta(days=30)

        respuesta_programadas = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={fecha_sin_audiencias.isoformat()}&estado=PROGRAMADA"
        )
        self.assertContains(
            respuesta_programadas,
            "No existen audiencias programadas para los filtros seleccionados.",
        )

        respuesta_eliminadas = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={fecha_sin_audiencias.isoformat()}&estado=ELIMINADA"
        )
        self.assertContains(
            respuesta_eliminadas,
            "No existen audiencias dejadas sin efecto para los filtros seleccionados.",
        )

        # "Todas" conserva el mensaje general de siempre, sin cambios.
        respuesta_todas = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={fecha_sin_audiencias.isoformat()}"
        )
        self.assertContains(
            respuesta_todas,
            "Sin audiencias programadas para esta sala en la fecha seleccionada.",
        )

    def test_flechas_de_dia_conservan_el_filtro_de_estado(self):
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={self.fecha.isoformat()}&estado=PROGRAMADA"
        )

        dia_anterior = self.fecha - datetime.timedelta(days=1)
        dia_siguiente = self.fecha + datetime.timedelta(days=1)
        self.assertContains(
            respuesta,
            f"fecha={dia_anterior.isoformat()}&estado=PROGRAMADA",
        )
        self.assertContains(
            respuesta,
            f"fecha={dia_siguiente.isoformat()}&estado=PROGRAMADA",
        )

    def test_filtro_de_estado_no_modifica_las_audiencias_en_la_base_de_datos(self):
        estado_original = self.audiencia.estado

        self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={self.fecha.isoformat()}&estado=ELIMINADA"
        )

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, estado_original)


# =====================================================
# AGENDA SEMANAL
# =====================================================

class ConsultaAgendaSemanalIntegrationTests(TestCase):
    """
    Prueba de integración de la agenda semanal (agenda_semanal):
    consulta de solo lectura de las audiencias PROGRAMADAS de una
    sala, para la semana (lunes a domingo) de una fecha de
    referencia. Mismo criterio de permisos que agenda_diaria: solo
    exige login, sin restricción adicional de rol -no existe ningún
    "@solo_administrador" en agenda_diaria, así que agregarlo
    únicamente acá rompería la consistencia entre ambas agendas-.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_agenda_semanal_integracion",
            email="agenda_semanal_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Agenda Semanal Integración",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Agenda Semanal Integración"
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Agenda Semanal Integración", activo=True
        )
        self.sala = Sala.objects.create(
            nombre="Sala Agenda Semanal Integración", activa=True
        )
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="6003-2027",
            ruc="2700060030-3",
            caratulado="Causa Agenda Semanal Integración",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9613, horaInicio=datetime.time(10, 0), horaTermino=datetime.time(10, 30)
        )

        # Fecha de referencia arbitraria; el lunes de su semana se
        # calcula acá mismo (no se asume qué día de la semana es),
        # con el mismo criterio que la propia vista usa.
        self.fecha_referencia = datetime.date(2027, 4, 9)
        self.lunes_semana = self.fecha_referencia - datetime.timedelta(
            days=self.fecha_referencia.weekday()
        )

        self.audiencia = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=self.bloque,
            cantidadBloques=1,
            fecha=self.fecha_referencia,
            horaInicio=self.bloque.horaInicio,
            horaTermino=self.bloque.horaTermino,
            usuarioCreacion=self.usuario,
        )

        self.client.login(username=self.usuario.email, password="ClaveSegura123")

    def test_requiere_login(self):
        self.client.logout()

        respuesta = self.client.get(reverse("agenda_semanal"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

    def test_usuario_autenticado_puede_acceder(self):
        respuesta = self.client.get(reverse("agenda_semanal"))

        self.assertEqual(respuesta.status_code, 200)

    def test_sin_sala_seleccionada_no_muestra_audiencias(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?fecha={self.fecha_referencia.isoformat()}"
        )

        self.assertIsNone(respuesta.context["sala_seleccionada"])
        self.assertFalse(respuesta.context["hay_audiencias"])
        self.assertNotContains(respuesta, self.causa.rit)
        self.assertContains(
            respuesta, "Seleccione una sala para consultar la agenda semanal."
        )

    def test_selector_de_sala_no_ofrece_salas_inactivas(self):
        sala_inactiva = Sala.objects.create(
            nombre="Sala Agenda Semanal Inactiva", activa=False
        )

        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        salas_del_selector = list(respuesta.context["salas"])
        self.assertIn(self.sala, salas_del_selector)
        self.assertNotIn(sala_inactiva, salas_del_selector)

    def test_solo_muestra_audiencias_de_la_sala_seleccionada(self):
        """
        Combina la verificación de "sala seleccionada filtra
        correctamente" y "audiencia de otra sala no aparece": una
        segunda sala con una audiencia PROGRAMADA la misma semana no
        debe mezclarse con los resultados de la sala consultada.
        """
        otra_sala = Sala.objects.create(
            nombre="Otra Sala Agenda Semanal", activa=True
        )
        otro_bloque = BloqueHorario.objects.create(
            orden=9614, horaInicio=datetime.time(11, 0), horaTermino=datetime.time(11, 30)
        )
        audiencia_otra_sala = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=otra_sala,
            bloqueInicio=otro_bloque,
            cantidadBloques=1,
            fecha=self.fecha_referencia,
            horaInicio=otro_bloque.horaInicio,
            horaTermino=otro_bloque.horaTermino,
            usuarioCreacion=self.usuario,
        )

        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        self.assertContains(respuesta, self.causa.rit)
        audiencias_mostradas = [
            audiencia
            for dia in respuesta.context["dias_semana"]
            for audiencia in dia["audiencias"]
        ]
        self.assertIn(self.audiencia, audiencias_mostradas)
        self.assertNotIn(audiencia_otra_sala, audiencias_mostradas)

    def test_la_semana_se_calcula_de_lunes_a_domingo_de_la_fecha_referencia(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        self.assertEqual(respuesta.context["inicio_semana"], self.lunes_semana)
        self.assertEqual(
            respuesta.context["fin_semana"],
            self.lunes_semana + datetime.timedelta(days=6),
        )

        dias = respuesta.context["dias_semana"]
        self.assertEqual(len(dias), 7)
        self.assertEqual(dias[0]["fecha"], self.lunes_semana)
        self.assertEqual(dias[0]["nombre"], "Lunes")
        self.assertEqual(dias[6]["fecha"], self.lunes_semana + datetime.timedelta(days=6))
        self.assertEqual(dias[6]["nombre"], "Domingo")

    def test_semana_anterior_retrocede_siete_dias(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        semana_anterior = self.fecha_referencia - datetime.timedelta(days=7)
        self.assertContains(
            respuesta,
            f"?sala={self.sala.pk}&fecha={semana_anterior.isoformat()}",
        )

    def test_semana_siguiente_avanza_siete_dias(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        semana_siguiente = self.fecha_referencia + datetime.timedelta(days=7)
        self.assertContains(
            respuesta,
            f"?sala={self.sala.pk}&fecha={semana_siguiente.isoformat()}",
        )

    def test_navegacion_de_semana_conserva_la_sala_seleccionada(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        # Los tres enlaces de navegación (anterior/actual/siguiente)
        # deben incluir la misma sala ya seleccionada.
        self.assertContains(respuesta, f"?sala={self.sala.pk}&fecha=")
        self.assertEqual(
            respuesta.content.decode().count(f"sala={self.sala.pk}&fecha="),
            3,
        )

    def test_audiencia_aparece_agrupada_en_su_dia_correcto(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        dia_con_la_audiencia = next(
            dia
            for dia in respuesta.context["dias_semana"]
            if dia["fecha"] == self.fecha_referencia
        )
        self.assertIn(self.audiencia, dia_con_la_audiencia["audiencias"])

        # El resto de los días de la semana no la muestran.
        otros_dias = [
            dia
            for dia in respuesta.context["dias_semana"]
            if dia["fecha"] != self.fecha_referencia
        ]
        for dia in otros_dias:
            self.assertNotIn(self.audiencia, dia["audiencias"])

    def test_dia_sin_audiencias_muestra_mensaje(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        self.assertContains(respuesta, "Sin audiencias programadas.")

    def test_audiencia_eliminada_no_aparece_en_la_agenda_semanal(self):
        self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "SOLICITUD_TRIBUNAL",
            },
        )

        # Filtro estado=PROGRAMADA explícito: desde que existe el
        # filtro de estado, "Todas" (sin especificar "estado") ya
        # muestra ambos estados a propósito -esta prueba verifica
        # específicamente que la audiencia dada de baja no aparezca
        # al consultar solo las programadas, no que desaparezca de
        # cualquier consulta-.
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}&estado=PROGRAMADA"
        )

        audiencias_mostradas = [
            audiencia
            for dia in respuesta.context["dias_semana"]
            for audiencia in dia["audiencias"]
        ]
        self.assertNotIn(self.audiencia, audiencias_mostradas)

        # La audiencia sigue existiendo -baja lógica, no eliminación
        # física- y conserva su información histórica.
        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.ELIMINADA)
        self.assertEqual(self.audiencia.fecha, self.fecha_referencia)

    def test_enlace_ver_trazabilidad_aparece_en_la_agenda_semanal(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}"
        )

        self.assertContains(
            respuesta,
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk]),
        )

    def test_dejar_sin_efecto_desde_la_agenda_semanal_funciona(self):
        """
        El botón "Dejar sin efecto" de la agenda semanal envía al
        mismo <form>/misma vista (dejar_sin_efecto_audiencia) que ya
        usa agenda_diaria -sin ninguna lógica nueva-: se prueba el
        flujo HTTP real, igual que
        DejarSinEfectoAudienciaIntegrationTests.
        """
        respuesta = self.client.post(
            reverse("dejar_sin_efecto_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "motivo_seleccionado": "SUSPENSION",
            },
            follow=True,
        )

        self.assertContains(respuesta, "Audiencia dejada sin efecto correctamente.")
        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, EstadoAudiencia.ELIMINADA)
        self.assertEqual(self.audiencia.motivoBaja, "Suspensión de la audiencia")

    # =================================================
    # FILTRO DE ESTADO
    # =================================================

    def _crear_audiencia_eliminada(self, orden_bloque=9616):
        """
        Crea una segunda audiencia, en la misma sala/semana que
        self.audiencia, ya con estado=ELIMINADA -mismo criterio que
        ConsultaAgendaIntegrationTests._crear_audiencia_eliminada,
        para probar el filtro de estado sin depender del flujo HTTP
        de "Dejar sin efecto" (ya probado aparte)-.
        """
        bloque = BloqueHorario.objects.create(
            orden=orden_bloque,
            horaInicio=datetime.time(13, 0),
            horaTermino=datetime.time(13, 30),
        )
        return Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=bloque,
            cantidadBloques=1,
            fecha=self.fecha_referencia,
            horaInicio=bloque.horaInicio,
            horaTermino=bloque.horaTermino,
            estado=EstadoAudiencia.ELIMINADA,
            motivoBaja="Prueba de filtro de estado",
            usuarioCreacion=self.usuario,
        )

    def test_filtro_estado_todas_muestra_programadas_y_eliminadas_en_su_dia(self):
        audiencia_eliminada = self._crear_audiencia_eliminada()

        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}&estado="
        )

        dia = next(
            dia
            for dia in respuesta.context["dias_semana"]
            if dia["fecha"] == self.fecha_referencia
        )
        self.assertIn(self.audiencia, dia["audiencias"])
        self.assertIn(audiencia_eliminada, dia["audiencias"])

    def test_filtro_estado_programadas_excluye_dejadas_sin_efecto(self):
        audiencia_eliminada = self._crear_audiencia_eliminada()

        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}&estado=PROGRAMADA"
        )

        audiencias_mostradas = [
            audiencia
            for dia in respuesta.context["dias_semana"]
            for audiencia in dia["audiencias"]
        ]
        self.assertIn(self.audiencia, audiencias_mostradas)
        self.assertNotIn(audiencia_eliminada, audiencias_mostradas)

    def test_filtro_estado_dejadas_sin_efecto_excluye_programadas(self):
        audiencia_eliminada = self._crear_audiencia_eliminada()

        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}&estado=ELIMINADA"
        )

        audiencias_mostradas = [
            audiencia
            for dia in respuesta.context["dias_semana"]
            for audiencia in dia["audiencias"]
        ]
        self.assertNotIn(self.audiencia, audiencias_mostradas)
        self.assertIn(audiencia_eliminada, audiencias_mostradas)

    def test_navegacion_de_semana_conserva_el_filtro_de_estado(self):
        respuesta = self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}&estado=ELIMINADA"
        )

        semana_anterior = self.fecha_referencia - datetime.timedelta(days=7)
        semana_siguiente = self.fecha_referencia + datetime.timedelta(days=7)
        self.assertContains(
            respuesta, f"fecha={semana_anterior.isoformat()}&estado=ELIMINADA"
        )
        self.assertContains(
            respuesta, f"fecha={semana_siguiente.isoformat()}&estado=ELIMINADA"
        )

    def test_filtro_de_estado_no_modifica_las_audiencias_en_la_base_de_datos(self):
        estado_original = self.audiencia.estado

        self.client.get(
            f"{reverse('agenda_semanal')}?sala={self.sala.pk}"
            f"&fecha={self.fecha_referencia.isoformat()}&estado=ELIMINADA"
        )

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.estado, estado_original)


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

    # -------------------------------------------------
    # proponer_fechas_audiencia: competencia/tipoAudiencia/sala
    # vacíos o con un ID no numérico, y cantidadBloques ausente o
    # no numérica, no deben producir un ValueError (bug real
    # corregido), sino un mensaje amigable y específico, sin
    # ejecutar GeneradorPropuestaFecha, conservando lo ya
    # ingresado por el usuario.
    # -------------------------------------------------

    def _datos_validos(self):
        return {
            "competencia": self.competencia.pk,
            "rit": self.causa.rit,
            "tipoAudiencia": self.tipo_audiencia.pk,
            "sala": self.sala.pk,
            "cantidadBloques": 1,
        }

    def test_proponer_sin_competencia_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["competencia"] = ""

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Selecciona una competencia e ingresa un RIT para buscar la causa.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)

    def test_proponer_competencia_no_numerica_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["competencia"] = "abc"

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Selecciona una competencia e ingresa un RIT para buscar la causa.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)

    def test_proponer_sin_tipo_audiencia_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["tipoAudiencia"] = ""

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar un tipo de audiencia antes de solicitar "
            "propuestas de fechas.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)
        self.assertEqual(respuesta.context["form"].data.get("rit"), self.causa.rit)

    def test_proponer_tipo_audiencia_no_numerico_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["tipoAudiencia"] = "abc"

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar un tipo de audiencia antes de solicitar "
            "propuestas de fechas.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)

    def test_proponer_sin_sala_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["sala"] = ""

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar una sala antes de solicitar propuestas de fechas.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)

    def test_proponer_sala_no_numerica_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["sala"] = "abc"

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe seleccionar una sala antes de solicitar propuestas de fechas.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)

    def test_proponer_sin_cantidad_bloques_muestra_mensaje_sin_excepcion(self):
        datos = self._datos_validos()
        datos["cantidadBloques"] = ""

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn(
            "Debe indicar la cantidad de bloques antes de solicitar "
            "propuestas de fechas.",
            mensajes,
        )
        self.assertNotIn("propuestas", respuesta.context)

    def test_proponer_cantidad_bloques_no_numerica_muestra_mensaje_existente(self):
        datos = self._datos_validos()
        datos["cantidadBloques"] = "abc"

        respuesta = self.client.post(reverse("proponer_fechas_audiencia"), datos)

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn("La cantidad de bloques ingresada no es válida.", mensajes)
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

        # Filtro estado=PROGRAMADA explícito: desde que existe el
        # filtro de estado, "Todas" (sin especificar "estado") ya
        # muestra ambos estados a propósito -esta prueba verifica
        # específicamente que la audiencia dada de baja no aparezca
        # al consultar solo las programadas, no que desaparezca de
        # cualquier consulta-.
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}"
            f"&fecha={self.fecha.isoformat()}&estado=PROGRAMADA"
        )

        audiencias_mostradas = list(respuesta.context["audiencias"])

        # La audiencia dada de baja ya no aparece...
        self.assertNotIn(self.audiencia, audiencias_mostradas)
        # ...pero la otra audiencia PROGRAMADA del mismo día sigue
        # apareciendo con normalidad.
        self.assertIn(self.otra_audiencia, audiencias_mostradas)


# =====================================================
# TRAZABILIDAD DE LA ANOTACIÓN (AUDIENCIA YA REGISTRADA)
# =====================================================

class GuardarAnotacionAudienciaTrazabilidadIntegrationTests(TestCase):
    """
    Prueba de integración de guardar_anotacion_audiencia: verifica
    que modificar la anotación de una audiencia YA REGISTRADA quede
    reflejada en RegistroTrazabilidad (acción MODIFICACION), con el
    mismo mecanismo de fotografía que ya usan registrarCreacion() y
    registrarBaja() (ver audiencias/services.py:ServicioTrazabilidad).
    No cubre la anotación de una audiencia todavía "Seleccionada"
    (sin guardar): esa no pasa por esta vista, ver
    FlujoCompletoRegistroAudienciaIntegrationTests más arriba.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_anotacion_integracion",
            email="anotacion_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Anotación Integración",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Anotación Integración"
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Anotación Integración", activo=True
        )
        self.sala = Sala.objects.create(
            nombre="Sala Anotación Integración", activa=True
        )
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="7003-2027",
            ruc="2700070030-3",
            caratulado="Causa Anotación Integración",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9721,
            horaInicio=datetime.time(9, 0),
            horaTermino=datetime.time(9, 30),
        )
        self.fecha = datetime.date(2027, 5, 15)

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
            anotacion="Anotación original.",
        )

        self.client.login(username=self.usuario.email, password="ClaveSegura123")

    def test_modificar_anotacion_genera_un_registro_de_trazabilidad(self):
        self.client.post(
            reverse("guardar_anotacion_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "anotacion": "Se requiere presencia de perito.",
            },
        )

        self.assertEqual(
            RegistroTrazabilidad.objects.filter(audiencia=self.audiencia).count(),
            1,
        )

    def test_el_registro_corresponde_a_la_accion_de_modificacion(self):
        self.client.post(
            reverse("guardar_anotacion_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "anotacion": "Se requiere presencia de perito.",
            },
        )

        registro = RegistroTrazabilidad.objects.get(audiencia=self.audiencia)
        self.assertEqual(registro.accion, AccionTrazabilidad.MODIFICACION)

    def test_se_identifica_al_usuario_que_realizo_la_modificacion(self):
        self.client.post(
            reverse("guardar_anotacion_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "anotacion": "Se requiere presencia de perito.",
            },
        )

        registro = RegistroTrazabilidad.objects.get(audiencia=self.audiencia)
        self.assertEqual(registro.usuario, self.usuario)

    def test_fotografia_refleja_la_anotacion_anterior_y_la_nueva(self):
        self.client.post(
            reverse("guardar_anotacion_audiencia"),
            {
                "audiencia_id": self.audiencia.pk,
                "anotacion": "Se requiere presencia de perito.",
            },
        )

        registro = RegistroTrazabilidad.objects.get(audiencia=self.audiencia)
        self.assertEqual(
            registro.valoresAnteriores["anotacion"], "Anotación original."
        )
        self.assertEqual(
            registro.valoresNuevos["anotacion"], "Se requiere presencia de perito."
        )

        # La audiencia en base de datos también quedó con el valor
        # nuevo (la fotografía no es lo único que se verifica: debe
        # coincidir con el dato real).
        self.audiencia.refresh_from_db()
        self.assertEqual(
            self.audiencia.anotacion, "Se requiere presencia de perito."
        )

    def test_si_la_modificacion_falla_no_queda_un_cambio_parcial(self):
        # Simula una falla al registrar la trazabilidad (por ejemplo,
        # un problema de base de datos): registrarModificacion() se
        # reemplaza para que lance una excepción. Como el guardado de
        # "anotacion" y el registro de trazabilidad viajan dentro del
        # mismo transaction.atomic() (ver guardar_anotacion_audiencia
        # en audiencias/views.py), la excepción debe revertir también
        # el cambio sobre la audiencia: no debe quedar ni el nuevo
        # valor guardado ni ningún RegistroTrazabilidad creado.
        with patch(
            "audiencias.views.ServicioTrazabilidad.registrarModificacion",
            side_effect=RuntimeError("Falla simulada al registrar trazabilidad."),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("guardar_anotacion_audiencia"),
                    {
                        "audiencia_id": self.audiencia.pk,
                        "anotacion": "Este cambio no debe quedar guardado.",
                    },
                )

        self.audiencia.refresh_from_db()
        self.assertEqual(self.audiencia.anotacion, "Anotación original.")
        self.assertFalse(
            RegistroTrazabilidad.objects.filter(audiencia=self.audiencia).exists()
        )


# =====================================================
# CONSULTA DE TRAZABILIDAD (audiencia ya registrada)
# =====================================================

class VerTrazabilidadAudienciaIntegrationTests(TestCase):
    """
    Prueba de integración de ver_trazabilidad_audiencia: verifica
    que la pantalla "Ver trazabilidad" (accesible desde la agenda
    diaria) muestre, para cada RegistroTrazabilidad, la información
    legible correspondiente a la operación real que representa
    -Creación, Baja/Dejar sin efecto o Anotación (ver
    audiencias/views.py:_preparar_registro_trazabilidad)-, filtrada
    por la audiencia correcta y ordenada del más antiguo al más
    reciente. Una audiencia registrada no se puede modificar: no
    existe una cuarta operación de "edición".
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_trazabilidad_integracion",
            email="trazabilidad_integracion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Trazabilidad Integración",
        )
        self.competencia = Competencia.objects.create(
            nombre="Competencia Trazabilidad Integración"
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Trazabilidad Integración", activo=True
        )
        self.sala = Sala.objects.create(
            nombre="Sala Trazabilidad Integración", activa=True
        )
        self.causa = Causa.objects.create(
            competencia=self.competencia,
            rit="7004-2027",
            ruc="2700070040-4",
            caratulado="Causa Trazabilidad Integración",
        )
        self.bloque = BloqueHorario.objects.create(
            orden=9731,
            horaInicio=datetime.time(9, 0),
            horaTermino=datetime.time(9, 30),
        )
        self.fecha = datetime.date(2027, 5, 20)

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

        # Otra audiencia, con su propio registro de trazabilidad:
        # NO debe aparecer al consultar la primera.
        self.otra_audiencia = Audiencia.objects.create(
            causa=self.causa,
            tipoAudiencia=self.tipo_audiencia,
            sala=self.sala,
            bloqueInicio=BloqueHorario.objects.create(
                orden=9732,
                horaInicio=datetime.time(9, 30),
                horaTermino=datetime.time(10, 0),
            ),
            cantidadBloques=1,
            fecha=self.fecha,
            horaInicio=datetime.time(9, 30),
            horaTermino=datetime.time(10, 0),
            usuarioCreacion=self.usuario,
        )
        RegistroTrazabilidad.objects.create(
            audiencia=self.otra_audiencia,
            usuario=self.usuario,
            accion=AccionTrazabilidad.CREACION,
            valoresAnteriores=None,
            valoresNuevos={"id": self.otra_audiencia.id},
        )

        self.client.login(username=self.usuario.email, password="ClaveSegura123")

    def test_requiere_login(self):
        self.client.logout()

        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

    def test_sin_registros_muestra_mensaje(self):
        # self.audiencia no tiene ningún RegistroTrazabilidad
        # asociado (el único creado en setUp pertenece a
        # self.otra_audiencia).
        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["registros"]), [])
        self.assertContains(
            respuesta,
            "No existen registros de trazabilidad para esta audiencia.",
        )

    def test_muestra_unicamente_los_registros_de_esa_audiencia(self):
        RegistroTrazabilidad.objects.create(
            audiencia=self.audiencia,
            usuario=self.usuario,
            accion=AccionTrazabilidad.CREACION,
            valoresAnteriores=None,
            valoresNuevos={"id": self.audiencia.id},
        )

        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        # El contexto "registros" ya no es el QuerySet crudo: es una
        # lista de dicts armada por _preparar_registro_trazabilidad
        # (ver audiencias/views.py). Si el filtro por audiencia
        # fallara, aquí aparecerían 2 registros (el de self.audiencia
        # y el de self.otra_audiencia creado en setUp), no 1.
        registros = respuesta.context["registros"]
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["accionLabel"], "Creación de audiencia")

    def test_registros_ordenados_del_mas_antiguo_al_mas_reciente(self):
        """
        fechaHora es auto_now_add (audiencias/models.py): ya no se
        puede forzar el orden con un .update() posterior, porque
        audiencias_registrotrazabilidad tiene un trigger BEFORE
        UPDATE OR DELETE que lo rechaza a nivel de base de datos
        (ver la migración de RunSQL correspondiente y
        ProteccionBaseDatosRegistroTrazabilidadTests, más abajo en
        este mismo archivo). En su lugar, se controla fechaHora en
        el momento mismo de crear cada registro, mockeando
        django.utils.timezone.now() -la función que auto_now_add
        usa internamente al hacer INSERT-. No requiere freezegun
        (no es una dependencia del proyecto, ver requirements.txt):
        alcanza con unittest.mock.patch, ya usado en este archivo.
        """
        primeraFecha = datetime.datetime(
            2027, 5, 20, 9, 0, tzinfo=datetime.timezone.utc
        )
        segundaFecha = datetime.datetime(
            2027, 5, 20, 10, 0, tzinfo=datetime.timezone.utc
        )

        with patch("django.utils.timezone.now", return_value=primeraFecha):
            RegistroTrazabilidad.objects.create(
                audiencia=self.audiencia,
                usuario=self.usuario,
                accion=AccionTrazabilidad.CREACION,
                valoresAnteriores=None,
                valoresNuevos={"estado": "PROGRAMADA"},
            )

        with patch("django.utils.timezone.now", return_value=segundaFecha):
            RegistroTrazabilidad.objects.create(
                audiencia=self.audiencia,
                usuario=self.usuario,
                accion=AccionTrazabilidad.MODIFICACION,
                valoresAnteriores={"anotacion": ""},
                valoresNuevos={"anotacion": "Texto nuevo"},
            )

        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        # Se compara por fechaHora (el dato que realmente define el
        # orden), no por pk: el contexto "registros" ya no es el
        # QuerySet crudo, es una lista de dicts (ver
        # _preparar_registro_trazabilidad), que no exponen ".pk".
        registros = list(respuesta.context["registros"])
        self.assertEqual(
            [r["fechaHora"] for r in registros],
            [primeraFecha, segundaFecha],
        )

    def _snapshot_base(self):
        """
        Snapshot base con la misma forma que produce
        ServicioTrazabilidad.fotografiar() (audiencias/services.py)
        para self.audiencia, usado por las pruebas de abajo para
        armar valoresAnteriores/valoresNuevos realistas sin depender
        de llamar al servicio de creación completo.
        """
        return {
            "id": self.audiencia.id,
            "causaId": self.causa.id,
            "tipoAudienciaId": self.tipo_audiencia.id,
            "salaId": self.sala.id,
            "bloqueInicioId": self.bloque.id,
            "cantidadBloques": 1,
            "fecha": self.fecha.isoformat(),
            "horaInicio": self.bloque.horaInicio.isoformat(),
            "horaTermino": self.bloque.horaTermino.isoformat(),
            "estado": "PROGRAMADA",
            "motivoBaja": "",
            "anotacion": "",
            "fechaCreacion": "2027-05-20T08:00:00",
            "usuarioCreacionId": self.usuario.id,
        }

    def test_registro_de_creacion_muestra_datos_legibles_y_oculta_ids_tecnicos(self):
        """
        Un registro de Creación debe mostrar "Creación de audiencia",
        el nombre del tipo de audiencia y de la sala (no sus IDs),
        fecha/horario agendado y cantidad de bloques. No debe
        mostrar ningún ID técnico ni "estado"/"motivoBaja"/
        "fechaCreacion" (ver audiencias/views.py:_detalleCreacion).
        """
        RegistroTrazabilidad.objects.create(
            audiencia=self.audiencia,
            usuario=self.usuario,
            accion=AccionTrazabilidad.CREACION,
            valoresAnteriores=None,
            valoresNuevos=self._snapshot_base(),
        )

        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        self.assertContains(respuesta, "Creación de audiencia")
        self.assertContains(respuesta, self.tipo_audiencia.nombre)
        self.assertContains(respuesta, self.sala.nombre)

        # Ningún ID técnico debe filtrarse a la pantalla: la vista
        # los resuelve a nombre legible o los descarta.
        self.assertNotContains(respuesta, "causaId")
        self.assertNotContains(respuesta, "tipoAudienciaId")
        self.assertNotContains(respuesta, "salaId")
        self.assertNotContains(respuesta, "bloqueInicioId")
        self.assertNotContains(respuesta, "usuarioCreacionId")
        self.assertNotContains(respuesta, "fechaCreacion")

    def test_registro_de_baja_muestra_motivo_y_transicion_de_estado(self):
        """
        Un registro de Baja debe mostrar "Audiencia dejada sin
        efecto", la transición "Programada → Eliminada" y el motivo
        ingresado por el funcionario. No debe repetir el resto del
        snapshot (tipo de audiencia, sala, cantidad de bloques, IDs):
        ninguno de esos campos cambia al dar de baja una audiencia
        (ver audiencias/views.py:_detalleBaja).
        """
        anteriores = self._snapshot_base()
        nuevos = {
            **self._snapshot_base(),
            "estado": "ELIMINADA",
            "motivoBaja": "Reprogramación",
        }

        RegistroTrazabilidad.objects.create(
            audiencia=self.audiencia,
            usuario=self.usuario,
            accion=AccionTrazabilidad.BAJA,
            valoresAnteriores=anteriores,
            valoresNuevos=nuevos,
        )

        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        self.assertContains(respuesta, "Audiencia dejada sin efecto")
        self.assertContains(respuesta, "Reprogramación")
        self.assertContains(respuesta, "Programada")
        self.assertContains(respuesta, "Eliminada")

        self.assertNotContains(respuesta, "tipoAudienciaId")
        self.assertNotContains(respuesta, "salaId")
        self.assertNotContains(respuesta, "bloqueInicioId")
        self.assertNotContains(respuesta, "usuarioCreacionId")

    def test_registro_de_anotacion_muestra_accion_y_contenido_legible(self):
        """
        AccionTrazabilidad no tiene un valor "ANOTACION": el registro
        se guarda con accion=MODIFICACION (único flujo real que la
        produce en todo el sistema, ver
        guardar_anotacion_audiencia/audiencias/views.py), pero en
        pantalla debe mostrarse como "Anotación" -no "Modificación"-,
        junto con el contenido anterior/nuevo, sin repetir el resto
        del snapshot (ver audiencias/views.py:_detalleAnotacion).
        """
        RegistroTrazabilidad.objects.create(
            audiencia=self.audiencia,
            usuario=self.usuario,
            accion=AccionTrazabilidad.MODIFICACION,
            valoresAnteriores={
                **self._snapshot_base(), "anotacion": "Texto anterior"
            },
            valoresNuevos={
                **self._snapshot_base(), "anotacion": "Texto nuevo"
            },
        )

        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        self.assertContains(respuesta, "Anotación")
        self.assertNotContains(respuesta, "Modificación")
        self.assertContains(respuesta, str(self.usuario))
        self.assertContains(respuesta, "Texto anterior")
        self.assertContains(respuesta, "Texto nuevo")

        self.assertNotContains(respuesta, "causaId")
        self.assertNotContains(respuesta, "tipoAudienciaId")
        self.assertNotContains(respuesta, "salaId")
        self.assertNotContains(respuesta, "bloqueInicioId")
        self.assertNotContains(respuesta, "usuarioCreacionId")

    def test_enlace_ver_trazabilidad_aparece_en_la_agenda_diaria(self):
        respuesta = self.client.get(
            f"{reverse('agenda_diaria')}?sala={self.sala.pk}&fecha={self.fecha.isoformat()}"
        )

        self.assertContains(
            respuesta,
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk]),
        )

    def test_volver_a_la_agenda_enlaza_a_la_fecha_de_la_audiencia(self):
        respuesta = self.client.get(
            reverse("ver_trazabilidad_audiencia", args=[self.audiencia.pk])
        )

        self.assertContains(
            respuesta,
            f"{reverse('agenda_diaria')}?fecha={self.fecha.isoformat()}",
        )


# =====================================================
# PROTECCIÓN DE RegistroTrazabilidad A NIVEL DE BASE DE DATOS
# =====================================================

class ProteccionBaseDatosRegistroTrazabilidadTests(TestCase):
    """
    Verifica el trigger BEFORE UPDATE OR DELETE agregado en la
    migración audiencias.0005_bloquear_modificacion_registrotrazabilidad:
    ni un UPDATE ni un DELETE directos sobre
    audiencias_registrotrazabilidad deben poder ejecutarse, sin
    importar que se hagan por fuera del ORM/servicios del proyecto
    -es justamente el escenario que un trigger de base de datos
    cubre y que ningún control a nivel de aplicación puede evitar-.

    Cada prueba envuelve la operación bloqueada en su propio
    transaction.atomic(): PostgreSQL aborta la transacción completa
    en cuanto el trigger lanza la excepción, así que sin un atomic()
    propio (que crea un SAVEPOINT) el resto de la prueba -incluida
    la limpieza automática de TestCase- fallaría con
    TransactionManagementError.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_proteccion_trazabilidad",
            email="proteccion_trazabilidad@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Protección Trazabilidad",
        )
        competencia = Competencia.objects.create(
            nombre="Competencia Protección Trazabilidad"
        )
        tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Protección Trazabilidad", activo=True
        )
        sala = Sala.objects.create(
            nombre="Sala Protección Trazabilidad", activa=True
        )
        causa = Causa.objects.create(
            competencia=competencia,
            rit="7005-2027",
            ruc="2700070050-4",
            caratulado="Causa Protección Trazabilidad",
        )
        bloque = BloqueHorario.objects.create(
            orden=9733,
            horaInicio=datetime.time(9, 0),
            horaTermino=datetime.time(9, 30),
        )
        self.audiencia = Audiencia.objects.create(
            causa=causa,
            tipoAudiencia=tipo_audiencia,
            sala=sala,
            bloqueInicio=bloque,
            cantidadBloques=1,
            fecha=datetime.date(2027, 5, 20),
            horaInicio=bloque.horaInicio,
            horaTermino=bloque.horaTermino,
            usuarioCreacion=self.usuario,
        )
        self.registro = RegistroTrazabilidad.objects.create(
            audiencia=self.audiencia,
            usuario=self.usuario,
            accion=AccionTrazabilidad.CREACION,
            valoresAnteriores=None,
            valoresNuevos={"estado": "PROGRAMADA"},
        )

    def test_update_directo_lanza_excepcion_de_base_de_datos(self):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                RegistroTrazabilidad.objects.filter(
                    pk=self.registro.pk
                ).update(accion=AccionTrazabilidad.BAJA)

        # El registro no cambió: el trigger rechazó el UPDATE antes
        # de que se aplicara.
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.accion, AccionTrazabilidad.CREACION)

    def test_delete_directo_lanza_excepcion_de_base_de_datos(self):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                self.registro.delete()

        # El registro sigue existiendo: el trigger rechazó el
        # DELETE antes de que se aplicara.
        self.assertTrue(
            RegistroTrazabilidad.objects.filter(pk=self.registro.pk).exists()
        )
