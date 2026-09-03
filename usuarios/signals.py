"""
Módulo de señales de la aplicación Usuarios.

Conecta las señales de autenticación de Django
(user_logged_in, user_logged_out, user_login_failed) a
ServicioRegistroAcceso, para que cada login exitoso, login
fallido y logout quede registrado en RegistroAcceso.

Se importa desde UsuariosConfig.ready() (ver usuarios/apps.py)
para que los receptores queden conectados al iniciar la
aplicación, siguiendo el patrón estándar de Django para
señales de autenticación.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from .services import ServicioRegistroAcceso


# =====================================================
# LOGIN EXITOSO
# =====================================================

@receiver(user_logged_in)
def registrarLoginExitoso(sender, request, user, **kwargs):
    """
    UsuarioLoginView (usuarios/views.py) es una subclase
    directa de LoginView sin overrides propios: es
    AuthenticationForm/LoginView quien dispara esta señal al
    autenticar correctamente, con "request" y "user" ya
    resueltos.
    """
    ServicioRegistroAcceso.registrarLoginExitoso(user, request)


# =====================================================
# LOGOUT
# =====================================================

@receiver(user_logged_out)
def registrarLogout(sender, request, user, **kwargs):
    """
    UsuarioLogoutView (usuarios/views.py) es una subclase
    directa de LogoutView: es LogoutView quien dispara esta
    señal antes de cerrar la sesión, con "user" todavía
    resuelto.
    """
    ServicioRegistroAcceso.registrarLogout(user, request)


# =====================================================
# LOGIN FALLIDO
# =====================================================

@receiver(user_login_failed)
def registrarLoginFallido(sender, credentials, request=None, **kwargs):
    """
    Django ya sanea "credentials" antes de emitir esta señal
    (django.contrib.auth._clean_credentials reemplaza
    "password" por asteriscos): este receptor nunca recibe la
    contraseña en texto plano.

    AuthenticationForm entrega el valor ingresado bajo la
    clave "username" del diccionario "credentials", sin
    importar cuál sea USERNAME_FIELD (en este proyecto es
    "email", ver Usuario.USERNAME_FIELD en usuarios/models.py);
    por eso se lee literalmente esa clave.
    """
    nombreUsuarioIntentado = credentials.get("username", "")

    ServicioRegistroAcceso.registrarLoginFallido(
        nombreUsuarioIntentado, request
    )
