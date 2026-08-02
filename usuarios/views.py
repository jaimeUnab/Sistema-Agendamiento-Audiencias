"""
Módulo de vistas de la aplicación Usuarios.

Contiene las vistas relacionadas con la autenticación
y administración de usuarios del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Mixins para restringir el acceso por autenticación y por rol.
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Vistas genéricas de Django para el inicio y cierre de sesión.
from django.contrib.auth.views import LoginView, LogoutView

# Vistas genéricas basadas en clases para creación y edición de objetos.
from django.views.generic import CreateView, UpdateView

# Construye una URL de forma perezosa (se resuelve al usarse, no al importar).
from django.urls import reverse_lazy

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Formulario de alta de usuarios.
from .forms import UsuarioForm

# Modelo de usuario personalizado del sistema.
from .models import RolUsuario, Usuario


# =====================================================
# VISTA DE INICIO DE SESIÓN
# =====================================================

class UsuarioLoginView(LoginView):
    """
    Vista encargada del inicio de sesión.

    Utiliza la plantilla login.html para autenticar
    a los usuarios del sistema.
    """

    template_name = "usuarios/login.html"


# =====================================================
# VISTA DE CIERRE DE SESIÓN
# =====================================================

class UsuarioLogoutView(LogoutView):
    """
    Vista encargada de cerrar la sesión del usuario.

    Una vez cerrada la sesión, redirige nuevamente
    a la pantalla de inicio de sesión.
    """

    next_page = "login"


# =====================================================
# LISTADO DE USUARIOS
# =====================================================

@login_required
def lista_usuarios(request):
    """
    Muestra el listado de usuarios registrados
    en el sistema.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todos los usuarios registrados
    # ordenados alfabéticamente por nombre.
    # -------------------------------------------------

    usuarios = Usuario.objects.all().order_by("nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "usuarios": usuarios
    }

    return render(
        request,
        "usuarios/lista.html",
        context
    )


# =====================================================
# ALTA DE USUARIOS
# =====================================================

class UsuarioCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Vista de alta de usuarios (HU-02).

    Permite crear nuevos usuarios del sistema mediante
    UsuarioForm. Solo pueden acceder usuarios autenticados
    con rol Administrador o superusuarios de Django.
    """

    # -------------------------------------------------
    # VISTA
    # -------------------------------------------------
    # Modelo, formulario y plantilla utilizados para el
    # alta de usuarios. Si el formulario tiene errores de
    # validación, ModelFormMixin vuelve a renderizar
    # automáticamente template_name mostrándolos, sin
    # necesidad de código adicional.

    model = Usuario
    form_class = UsuarioForm
    template_name = "usuarios/nuevo.html"

    # -------------------------------------------------
    # VALIDACIÓN DE PERMISOS
    # -------------------------------------------------
    # LoginRequiredMixin exige que el usuario esté
    # autenticado; si no lo está, Django lo redirige a la
    # pantalla de login (LOGIN_URL).
    #
    # UserPassesTestMixin ejecuta test_func() y solo deja
    # continuar si retorna True. Si el usuario ya está
    # autenticado pero no cumple la condición, responde
    # con un error 403 (prohibido) en vez de redirigir.

    def test_func(self):
        """
        Permite el acceso a usuarios con rol Administrador,
        o a cualquier superusuario de Django (evita que un
        superusuario quede bloqueado fuera del sistema si,
        por cualquier vía, su campo "rol" no quedó en
        Administrador).
        """
        return (
            self.request.user.is_superuser
            or self.request.user.tieneRol(RolUsuario.ADMINISTRADOR)
        )

    # -------------------------------------------------
    # REDIRECCIÓN
    # -------------------------------------------------
    # Una vez guardado el usuario correctamente, CreateView
    # redirige automáticamente a esta URL.

    success_url = reverse_lazy("lista_usuarios")

    def form_valid(self, form):
        """
        Guarda el nuevo usuario y notifica el éxito
        de la operación mediante el framework de mensajes.
        """
        respuesta = super().form_valid(form)

        messages.success(
            self.request,
            f"Usuario «{self.object.nombre}» creado correctamente."
        )

        return respuesta


# =====================================================
# EDICIÓN DE USUARIOS
# =====================================================

class UsuarioUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Vista de edición de usuarios (HU-03).

    Permite modificar un usuario existente mediante
    UsuarioForm. Solo pueden acceder usuarios autenticados
    con rol Administrador o superusuarios de Django, el
    mismo criterio que UsuarioCreateView.
    """

    # -------------------------------------------------
    # VISTA
    # -------------------------------------------------
    # Modelo, formulario y plantilla utilizados para editar
    # un usuario. UpdateView identifica automáticamente qué
    # usuario editar a partir del parámetro de la URL (pk o
    # slug) y precarga el formulario con sus datos actuales.

    model = Usuario
    form_class = UsuarioForm
    template_name = "usuarios/editar.html"

    # -------------------------------------------------
    # VALIDACIÓN DE PERMISOS
    # -------------------------------------------------
    # Mismo criterio que UsuarioCreateView: LoginRequiredMixin
    # exige autenticación (redirige al login si no la hay) y
    # UserPassesTestMixin exige rol Administrador o
    # is_superuser (responde 403 si no se cumple).

    def test_func(self):
        """
        Permite el acceso a usuarios con rol Administrador,
        o a cualquier superusuario de Django.
        """
        return (
            self.request.user.is_superuser
            or self.request.user.tieneRol(RolUsuario.ADMINISTRADOR)
        )

    # -------------------------------------------------
    # ACTUALIZACIÓN DEL USUARIO
    # -------------------------------------------------
    # UsuarioForm ya resuelve, en su propio __init__/clean()/
    # save(), que dejar password1 y password2 en blanco no
    # modifique la contraseña actual del usuario. Aquí solo
    # se notifica el resultado de la operación.

    def form_valid(self, form):
        """
        Guarda los cambios del usuario y notifica el éxito
        de la operación mediante el framework de mensajes.
        """
        respuesta = super().form_valid(form)

        messages.success(
            self.request,
            f"Usuario «{self.object.nombre}» actualizado correctamente."
        )

        return respuesta

    # -------------------------------------------------
    # REDIRECCIÓN
    # -------------------------------------------------
    # Una vez guardados los cambios, UpdateView redirige
    # automáticamente a esta URL.

    success_url = reverse_lazy("lista_usuarios")
