"""
Módulo de pruebas de la aplicación Bloques.

Contiene las pruebas automatizadas (Django Test Framework)
para el caso de uso "Cambiar Agendamiento Automático" y para
la carga inicial de bloques horarios (comando de gestión
cargar_bloques).

Cada clase de prueba usa django.test.TestCase, que envuelve
cada método de prueba en su propia transacción y la revierte
al finalizar: no es necesario limpiar manualmente los datos
creados en cada prueba, y ninguna prueba depende del estado
que haya dejado otra.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Permite crear usuarios de prueba sin acoplarse directamente
# a la clase Usuario (buena práctica recomendada por Django
# cuando el proyecto usa un modelo de usuario personalizado).
from django.contrib.auth import get_user_model

# Permite leer los mensajes (django.contrib.messages) que
# quedaron disponibles para la request final de la respuesta.
from django.contrib.messages import get_messages

# Permite invocar el management command "cargar_bloques" desde
# la propia prueba (ver el comentario en CargaInicialBloquesTests
# sobre por qué es necesario hacerlo así).
from django.core.management import call_command

from django.test import TestCase
from django.urls import reverse

# Bloques Horarios es un módulo de Configuración: sus vistas
# ahora exigen rol Administrador (ver usuarios/decorators.py:
# solo_administrador). El usuario de prueba de este archivo se
# crea con ese rol para seguir probando el comportamiento real
# de cambiar_agendamiento_automatico, no el de un rol sin acceso.
from usuarios.models import RolUsuario

from .models import BloqueHorario

Usuario = get_user_model()


# =====================================================
# CAMBIAR AGENDAMIENTO AUTOMÁTICO
# =====================================================

class CambiarAgendamientoAutomaticoTests(TestCase):
    """
    Pruebas del caso de uso "Cambiar Agendamiento
    Automático" de un bloque horario (vista
    cambiar_agendamiento_automatico).
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_bloques",
            email="pruebas_bloques@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )

        # Bloque de prueba con un "orden" fuera del rango que
        # genera cargar_bloques (1 a ~32), para no colisionar
        # con la carga inicial si esta prueba llega a correr
        # sobre una base de datos que ya la tenga cargada.
        self.bloque = BloqueHorario.objects.create(
            orden=9001,
            horaInicio="08:00",
            horaTermino="08:30",
            permiteAgendamientoAutomatico=True,
        )

    def test_requiere_login(self):
        """
        Sin sesión iniciada, la vista redirige al login en
        vez de cambiar el indicador de agendamiento
        automático.
        """

        respuesta = self.client.post(
            reverse("cambiar_agendamiento_automatico", args=[self.bloque.pk])
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

        # El indicador no cambió.
        self.bloque.refresh_from_db()
        self.assertTrue(self.bloque.permiteAgendamientoAutomatico)

    def test_get_no_permitido(self):
        """
        Un GET sobre la URL de cambio de agendamiento
        automático responde 405 (Method Not Allowed): la
        vista solo acepta POST.
        """

        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("cambiar_agendamiento_automatico", args=[self.bloque.pk])
        )

        self.assertEqual(respuesta.status_code, 405)

    def test_post_invierte_y_un_segundo_post_revierte_el_valor(self):
        """
        Un primer POST invierte permiteAgendamientoAutomatico
        (True -> False) y muestra el mensaje correspondiente;
        un segundo POST lo revierte (False -> True), sin que
        el registro se elimine en ningún momento.
        """

        self.client.force_login(self.usuario)
        url = reverse(
            "cambiar_agendamiento_automatico", args=[self.bloque.pk]
        )
        horario = "08:00 - 08:30"

        # ---------------------------------------------
        # Primer POST: True -> False.
        # ---------------------------------------------

        respuesta_1 = self.client.post(url, follow=True)

        self.bloque.refresh_from_db()
        self.assertFalse(self.bloque.permiteAgendamientoAutomatico)

        # El registro nunca se elimina.
        self.assertTrue(
            BloqueHorario.objects.filter(pk=self.bloque.pk).exists()
        )

        mensajes_1 = [str(m) for m in get_messages(respuesta_1.wsgi_request)]
        self.assertIn(
            f"El bloque {horario} ya no será considerado por el "
            f"agendamiento automático.",
            mensajes_1,
        )

        # ---------------------------------------------
        # Segundo POST: False -> True (revierte el valor).
        # ---------------------------------------------

        respuesta_2 = self.client.post(url, follow=True)

        self.bloque.refresh_from_db()
        self.assertTrue(self.bloque.permiteAgendamientoAutomatico)

        self.assertTrue(
            BloqueHorario.objects.filter(pk=self.bloque.pk).exists()
        )

        mensajes_2 = [str(m) for m in get_messages(respuesta_2.wsgi_request)]
        self.assertIn(
            f"El bloque {horario} ahora será considerado por el "
            f"agendamiento automático.",
            mensajes_2,
        )


# =====================================================
# CARGA INICIAL
# =====================================================

class CargaInicialBloquesTests(TestCase):
    """
    Pruebas de la carga inicial de bloques horarios
    (comando de gestión "cargar_bloques").

    A diferencia de Competencia (que carga sus datos
    iniciales mediante una migración con RunPython),
    BloqueHorario los carga mediante un management command,
    que no forma parte del historial de migraciones. La base
    de datos de pruebas que arma "manage.py test" se
    construye aplicando únicamente migraciones, por lo que
    "cargar_bloques" no se ejecuta ahí automáticamente. Por
    eso esta clase invoca el comando explícitamente en
    setUp(): es la única forma de probar la carga inicial de
    forma autocontenida, sin depender de que alguien lo haya
    ejecutado manualmente de antemano sobre esta base de
    datos de pruebas.
    """

    def setUp(self):
        call_command("cargar_bloques")

    def test_existen_bloques_horarios_cargados(self):
        """
        Tras ejecutar la carga inicial, existe al menos un
        bloque horario registrado. No se asume una cantidad
        fija: la prueba sigue siendo válida si más adelante
        se amplía el horario oficial y cargar_bloques genera
        más bloques.
        """

        self.assertGreater(BloqueHorario.objects.count(), 0)

    def test_bloques_quedan_ordenados_correctamente(self):
        """
        Los bloques quedan numerados de forma consecutiva y
        creciente en su campo "orden", empezando en 1 (tal
        como los genera cargar_bloques), sin asumir cuántos
        bloques existen en total.
        """

        ordenes = list(
            BloqueHorario.objects.order_by("orden").values_list(
                "orden", flat=True
            )
        )

        self.assertEqual(ordenes, list(range(1, len(ordenes) + 1)))

    def test_no_existen_bloques_duplicados(self):
        """
        No existen dos bloques con el mismo valor de "orden".
        El modelo ya lo garantiza con unique=True; esta
        prueba confirma que la carga inicial en sí no intenta
        insertar duplicados (por ejemplo, si se ejecutara el
        comando más de una vez).
        """

        call_command("cargar_bloques")  # Segunda ejecución: debe ser idempotente.

        ordenes = list(
            BloqueHorario.objects.values_list("orden", flat=True)
        )

        self.assertEqual(len(ordenes), len(set(ordenes)))

    def test_todos_los_bloques_tienen_horarios_validos(self):
        """
        Todos los bloques cargados tienen horaInicio y
        horaTermino asignadas (ninguno queda con un horario
        vacío o nulo).
        """

        self.assertGreater(BloqueHorario.objects.count(), 0)

        for bloque in BloqueHorario.objects.all():
            self.assertIsNotNone(bloque.horaInicio)
            self.assertIsNotNone(bloque.horaTermino)
