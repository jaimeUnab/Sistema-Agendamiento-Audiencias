"""
Módulo de pruebas de la aplicación Usuarios.

Contiene las pruebas automatizadas (Django Test Framework) de:

- RegistroAcceso: que un login exitoso, un login fallido y un
  acceso denegado (403) efectivamente generen su registro, con
  los datos esperados y sin exponer la contraseña ingresada.
- La expiración de sesión por inactividad (SESSION_COOKIE_AGE/
  SESSION_SAVE_EVERY_REQUEST, ver config/settings.py).

No se prueban aquí los flujos de alta/edición de usuarios
(UsuarioCreateView/UsuarioUpdateView) ni el control de acceso
por rol en sí (solo_administrador): esos ya están cubiertos en
las pruebas de cada módulo de Configuración (por ejemplo,
competencias/tests.py:PermisosListaCompetenciasTests). Esta
suite reutiliza uno de esos endpoints ya probados
(lista_competencias) solo como disparador de un 403 real, no
para volver a probar el permiso en sí.

Cada clase de prueba usa django.test.TestCase, que envuelve
cada método de prueba en su propia transacción y la revierte
al finalizar.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import RegistroAcceso, RolUsuario, TipoEventoAcceso

Usuario = get_user_model()


# =====================================================
# 1. LOGIN EXITOSO
# =====================================================

class LoginExitosoRegistroAccesoTests(TestCase):
    """
    Un login exitoso, realizado a través de la vista real
    (UsuarioLoginView), debe generar un RegistroAcceso
    LOGIN_EXITOSO asociado al usuario que inició sesión.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="login_exitoso_registro",
            email="login_exitoso_registro@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Login Exitoso",
            rol=RolUsuario.USUARIO,
        )

    def test_login_exitoso_genera_registro(self):
        respuesta = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.email,
                "password": "ClaveSegura123",
            },
        )

        # La vista redirige tras un login correcto
        # (LOGIN_REDIRECT_URL, ver config/settings.py):
        # confirma que efectivamente fue exitoso, no un
        # reintento del formulario.
        self.assertEqual(respuesta.status_code, 302)

        registros = RegistroAcceso.objects.filter(
            tipoEvento=TipoEventoAcceso.LOGIN_EXITOSO
        )
        self.assertEqual(registros.count(), 1)

        registro = registros.first()
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(
            registro.nombreUsuarioIntentado, self.usuario.email
        )
        self.assertTrue(registro.exitoso)


# =====================================================
# 2. LOGIN FALLIDO
# =====================================================

class LoginFallidoRegistroAccesoTests(TestCase):
    """
    Un login fallido debe generar un RegistroAcceso
    LOGIN_FALLIDO, sin usuario asociado (ver docstring de
    ServicioRegistroAcceso.registrarLoginFallido) y, sobre
    todo, sin que la contraseña ingresada quede almacenada en
    ningún campo del registro.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="login_fallido_registro",
            email="login_fallido_registro@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Login Fallido",
            rol=RolUsuario.USUARIO,
        )

    def test_login_fallido_genera_registro_sin_contrasena(self):
        contrasenaIncorrecta = "ClaveIncorrecta999"

        respuesta = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.email,
                "password": contrasenaIncorrecta,
            },
        )

        # La vista vuelve a mostrar el formulario (200), no
        # redirige: confirma que el login efectivamente falló.
        self.assertEqual(respuesta.status_code, 200)

        registros = RegistroAcceso.objects.filter(
            tipoEvento=TipoEventoAcceso.LOGIN_FALLIDO
        )
        self.assertEqual(registros.count(), 1)

        registro = registros.first()
        self.assertIsNone(registro.usuario)
        self.assertEqual(
            registro.nombreUsuarioIntentado, self.usuario.email
        )
        self.assertFalse(registro.exitoso)

        # RegistroAcceso no tiene ningún campo de contraseña
        # (ver usuarios/models.py): esto verifica, además, que
        # la contraseña ingresada no haya terminado guardada
        # por accidente en alguno de los campos de texto que sí
        # existen.
        self.assertNotEqual(
            registro.nombreUsuarioIntentado, contrasenaIncorrecta
        )
        self.assertNotIn(
            contrasenaIncorrecta, registro.rutaSolicitada
        )

    def test_login_fallido_con_usuario_inexistente_tambien_genera_registro(self):
        """
        El correo ingresado ni siquiera corresponde a un
        Usuario registrado: igual debe quedar el registro, con
        "usuario" en None y "nombreUsuarioIntentado" con el
        valor ingresado (es, de hecho, el caso típico para el
        que existe ese campo).
        """
        respuesta = self.client.post(
            reverse("login"),
            {
                "username": "no_existe@tribunal.cl",
                "password": "ClaveCualquiera123",
            },
        )

        self.assertEqual(respuesta.status_code, 200)

        registro = RegistroAcceso.objects.get(
            tipoEvento=TipoEventoAcceso.LOGIN_FALLIDO
        )
        self.assertIsNone(registro.usuario)
        self.assertEqual(
            registro.nombreUsuarioIntentado, "no_existe@tribunal.cl"
        )


# =====================================================
# 3. ACCESO DENEGADO
# =====================================================

class AccesoDenegadoRegistroAccesoTests(TestCase):
    """
    Un usuario autenticado sin el rol requerido que recibe un
    403 (PermissionDenied) al intentar acceder a una vista de
    Configuración debe generar un RegistroAcceso
    ACCESO_DENEGADO con la ruta solicitada.

    Usa lista_competencias (protegida por
    solo_administrador) solo como disparador de un 403 real;
    el permiso en sí ya está probado en
    competencias/tests.py:PermisosListaCompetenciasTests.
    """

    def setUp(self):
        self.usuario_sin_permiso = Usuario.objects.create_user(
            username="acceso_denegado_registro",
            email="acceso_denegado_registro@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Sin Permiso",
            rol=RolUsuario.USUARIO,
        )
        self.client.login(
            username=self.usuario_sin_permiso.email,
            password="ClaveSegura123",
        )

    def test_acceso_denegado_genera_registro_con_la_ruta(self):
        ruta = reverse("lista_competencias")

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 403)

        registros = RegistroAcceso.objects.filter(
            tipoEvento=TipoEventoAcceso.ACCESO_DENEGADO
        )
        self.assertEqual(registros.count(), 1)

        registro = registros.first()
        self.assertEqual(registro.usuario, self.usuario_sin_permiso)
        self.assertEqual(
            registro.nombreUsuarioIntentado,
            self.usuario_sin_permiso.email,
        )
        self.assertFalse(registro.exitoso)
        self.assertEqual(registro.rutaSolicitada, ruta)

    def test_login_requerido_sin_sesion_no_genera_acceso_denegado(self):
        """
        El redirect de @login_required por falta de sesión NO
        debe registrarse como ACCESO_DENEGADO (decisión
        explícita: solo se registra PermissionDenied de un
        usuario ya autenticado, ver
        usuarios/middleware.py:RegistroAccesoMiddleware).
        """
        self.client.logout()

        respuesta = self.client.get(reverse("lista_competencias"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            RegistroAcceso.objects.filter(
                tipoEvento=TipoEventoAcceso.ACCESO_DENEGADO
            ).count(),
            0,
        )


# =====================================================
# 4. EXPIRACIÓN DE SESIÓN POR INACTIVIDAD
# =====================================================

class ExpiracionSesionPorInactividadTests(TestCase):
    """
    Pruebas de SESSION_COOKIE_AGE/SESSION_SAVE_EVERY_REQUEST
    (ver config/settings.py): sesión de 15 minutos con ventana
    deslizante por actividad.

    No usan ningún mock de tiempo (freezegun ni similar):
    manipulan directamente Session.expire_date -el modelo real
    que respalda el backend de sesiones por defecto,
    django.contrib.sessions.backends.db, ya en uso por el
    proyecto- para simular de forma determinista "hace poco que
    no hay actividad" o "ya pasaron los 15 minutos", sin
    depender de esperas reales ni de dependencias nuevas.

    Usa dashboard.views.inicio (name="inicio") como vista
    protegida de prueba: es la única vista con @login_required
    sin exigir además un rol -el resto de las vistas protegidas
    del sistema son de Configuración y exigen rol Administrador
    (solo_administrador), lo que mezclaría permisos con lo que
    esta clase prueba-.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="expiracion_sesion",
            email="expiracion_sesion@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Expiracion Sesion",
            rol=RolUsuario.USUARIO,
        )

    def _expireDateDeLaSesionActual(self):
        return Session.objects.get(
            session_key=self.client.session.session_key
        ).expire_date

    # -------------------------------------------------
    # CONFIGURACIÓN
    # -------------------------------------------------

    def test_configuracion_de_sesion_es_15_minutos_con_renovacion(self):
        """
        Sanity check de los dos settings que implementan el
        requisito: si alguno de los dos se revierte por error,
        esta prueba lo detecta antes que cualquier otra.
        """
        self.assertEqual(settings.SESSION_COOKIE_AGE, 900)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    # -------------------------------------------------
    # RENOVACIÓN POR ACTIVIDAD
    # -------------------------------------------------

    def test_una_request_autenticada_renueva_la_ventana_de_15_minutos(self):
        """
        Adelanta artificialmente expire_date a solo 5 minutos en
        el futuro (simulando que ya pasaron 10 de los 15 minutos
        permitidos) y hace una request autenticada:
        SESSION_SAVE_EVERY_REQUEST=True debe reescribir la
        sesión con una ventana COMPLETA de 15 minutos desde ese
        momento, no seguir contando desde el valor anterior.
        """
        self.client.login(
            username=self.usuario.email, password="ClaveSegura123"
        )

        sesion = Session.objects.get(
            session_key=self.client.session.session_key
        )
        sesion.expire_date = timezone.now() + timedelta(minutes=5)
        sesion.save()

        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.status_code, 200)

        nuevoExpireDate = self._expireDateDeLaSesionActual()

        # Si la ventana se hubiera seguido contando desde el
        # valor viejo, seguiría a ~5 minutos de "ahora". Al
        # renovarse, queda a ~15 minutos: la diferencia es de
        # varios minutos, no de milisegundos.
        self.assertGreater(
            nuevoExpireDate - timezone.now(), timedelta(minutes=10)
        )

    # -------------------------------------------------
    # EXPIRACIÓN
    # -------------------------------------------------

    def test_sesion_expirada_desautentica_y_redirige_al_login(self):
        """
        Con expire_date ya en el pasado (15+ minutos de
        inactividad ya transcurridos), la siguiente request a
        una vista protegida debe tratar al usuario como anónimo
        -sin llamar a ningún logout explícito, es el
        comportamiento nativo del backend de sesiones- y
        redirigir a LOGIN_URL, igual que con cualquier usuario
        no autenticado.
        """
        self.client.login(
            username=self.usuario.email, password="ClaveSegura123"
        )

        sesion = Session.objects.get(
            session_key=self.client.session.session_key
        )
        sesion.expire_date = timezone.now() - timedelta(minutes=1)
        sesion.save()

        respuesta = self.client.get(reverse("inicio"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_sesion_expirada_no_genera_acceso_denegado(self):
        """
        Decisión ya tomada para RegistroAcceso: los redirects a
        login por falta de sesión no son un "acceso denegado"
        (ver RegistroAccesoMiddleware). Una sesión expirada es,
        para el sistema, indistinguible de un usuario que nunca
        inició sesión: no debe generar ningún RegistroAcceso
        nuevo.
        """
        self.client.login(
            username=self.usuario.email, password="ClaveSegura123"
        )
        RegistroAcceso.objects.all().delete()

        sesion = Session.objects.get(
            session_key=self.client.session.session_key
        )
        sesion.expire_date = timezone.now() - timedelta(minutes=1)
        sesion.save()

        self.client.get(reverse("inicio"))

        self.assertEqual(
            RegistroAcceso.objects.filter(
                tipoEvento=TipoEventoAcceso.ACCESO_DENEGADO
            ).count(),
            0,
        )
