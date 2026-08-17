"""
Módulo de pruebas de la aplicación Salas.

Contiene las pruebas automatizadas (Django Test Framework)
para los casos de uso "Crear Sala" (incluida la validación
de nombre duplicado) y "Cambiar Estado" de una sala.

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

from django.test import TestCase
from django.urls import reverse

# Salas es un módulo de Configuración: sus vistas ahora exigen
# rol Administrador (ver usuarios/decorators.py:
# solo_administrador). Los usuarios de prueba de este archivo se
# crean con ese rol para seguir probando el comportamiento real
# de crear_sala/cambiar_estado_sala, no el de un rol sin acceso.
from usuarios.models import RolUsuario

from .models import Sala

Usuario = get_user_model()


# =====================================================
# CREAR SALA
# =====================================================

class CrearSalaTests(TestCase):
    """
    Pruebas del caso de uso "Crear Sala" (vista crear_sala).
    """

    def setUp(self):
        """
        Crea un usuario autenticado. crear_sala exige login
        (@login_required), por lo que todas las pruebas de
        esta clase lo necesitan.
        """

        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_crear",
            email="pruebas_crear@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.force_login(self.usuario)

    def test_usuario_autenticado_puede_crear_sala(self):
        """
        Un usuario autenticado puede crear una sala mediante
        un POST válido: la respuesta redirige al listado, la
        sala queda almacenada en la base de datos y se
        muestra el mensaje de éxito.
        """

        respuesta = self.client.post(
            reverse("crear_sala"),
            {"nombre": "Sala de Pruebas 1", "activa": True},
            follow=True,
        )

        # El POST responde correctamente y redirige al listado.
        self.assertRedirects(respuesta, reverse("lista_salas"))

        # La sala queda almacenada en la base de datos.
        self.assertTrue(
            Sala.objects.filter(nombre="Sala de Pruebas 1", activa=True).exists()
        )

        # Se muestra el mensaje de éxito.
        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertIn(
            "Sala «Sala de Pruebas 1» creada correctamente.", mensajes
        )


class NombreDuplicadoSalaTests(TestCase):
    """
    Pruebas de la validación de nombre único al crear una
    sala.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_dup",
            email="pruebas_dup@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.force_login(self.usuario)

        # Sala ya existente, usada para forzar la colisión
        # de nombre en la prueba.
        self.sala_existente = Sala.objects.create(
            nombre="Sala Compartida", activa=True
        )

    def test_no_permite_crear_sala_con_nombre_duplicado(self):
        """
        Un POST con un nombre ya registrado no crea un
        segundo registro: el formulario vuelve a mostrarse
        con errores de validación (sin redirección).
        """

        respuesta = self.client.post(
            reverse("crear_sala"),
            {"nombre": "Sala Compartida", "activa": True},
        )

        # No hay redirección: el formulario se vuelve a
        # renderizar con errores (status 200, no 302).
        self.assertEqual(respuesta.status_code, 200)

        # El formulario vuelve con errores en el campo "nombre".
        # No se compara el texto exacto del mensaje de Django
        # (varía según el idioma activo); solo que exista un
        # error asociado a ese campo.
        self.assertTrue(respuesta.context["form"].errors)
        self.assertIn("nombre", respuesta.context["form"].errors)

        # No se crea un segundo registro: sigue existiendo una
        # única sala con ese nombre.
        self.assertEqual(
            Sala.objects.filter(nombre="Sala Compartida").count(), 1
        )


# =====================================================
# CAMBIAR ESTADO
# =====================================================

class CambiarEstadoSalaTests(TestCase):
    """
    Pruebas del caso de uso "Cambiar Estado" (activar o
    desactivar) de una sala (vista cambiar_estado_sala).
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_estado",
            email="pruebas_estado@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )

        # Sala de prueba, activa por defecto.
        self.sala = Sala.objects.create(nombre="Sala de Estado", activa=True)

    def test_requiere_login(self):
        """
        Sin sesión iniciada, la vista redirige al login en
        vez de cambiar el estado de la sala.
        """

        respuesta = self.client.post(
            reverse("cambiar_estado_sala", args=[self.sala.pk])
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

        # El estado no cambió.
        self.sala.refresh_from_db()
        self.assertTrue(self.sala.activa)

    def test_get_no_permitido(self):
        """
        Un GET sobre la URL de cambio de estado responde 405
        (Method Not Allowed): la vista solo acepta POST.
        """

        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("cambiar_estado_sala", args=[self.sala.pk])
        )

        self.assertEqual(respuesta.status_code, 405)

    def test_post_desactiva_y_un_segundo_post_reactiva_la_sala(self):
        """
        Un primer POST desactiva la sala (activa -> inactiva)
        y muestra el mensaje correspondiente; un segundo POST
        la reactiva (vuelve al estado anterior), sin que el
        registro se elimine en ningún momento.
        """

        self.client.force_login(self.usuario)
        url = reverse("cambiar_estado_sala", args=[self.sala.pk])

        # ---------------------------------------------
        # Primer POST: activa -> inactiva.
        # ---------------------------------------------

        respuesta_1 = self.client.post(url, follow=True)

        self.sala.refresh_from_db()
        self.assertFalse(self.sala.activa)

        # El registro nunca se elimina.
        self.assertTrue(Sala.objects.filter(pk=self.sala.pk).exists())

        mensajes_1 = [str(m) for m in get_messages(respuesta_1.wsgi_request)]
        self.assertIn(
            f"Sala «{self.sala.nombre}» desactivada correctamente.",
            mensajes_1,
        )

        # ---------------------------------------------
        # Segundo POST: inactiva -> activa (vuelve al
        # estado anterior).
        # ---------------------------------------------

        respuesta_2 = self.client.post(url, follow=True)

        self.sala.refresh_from_db()
        self.assertTrue(self.sala.activa)

        self.assertTrue(Sala.objects.filter(pk=self.sala.pk).exists())

        mensajes_2 = [str(m) for m in get_messages(respuesta_2.wsgi_request)]
        self.assertIn(
            f"Sala «{self.sala.nombre}» activada correctamente.",
            mensajes_2,
        )
