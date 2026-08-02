from django.contrib.auth.models import AbstractUser
from django.db import models


class RolUsuario(models.TextChoices):
    """
    Define los roles del sistema.
    """

    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    USUARIO = "USUARIO", "Usuario"


class Usuario(AbstractUser):
    """
    Modelo de usuario del sistema.

    Hereda de AbstractUser para reutilizar el sistema
    de autenticación de Django.
    """

    # =====================================================
    # CAMPOS DEL SISTEMA
    # =====================================================

    # Nombre completo del funcionario
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )

    # Correo institucional
    email = models.EmailField(
        unique=True,
        verbose_name="Correo"
    )

    # Rol del usuario
    rol = models.CharField(
        max_length=20,
        choices=RolUsuario.choices,
        default=RolUsuario.USUARIO,
        verbose_name="Rol"
    )

    # =====================================================
    # CONFIGURACIÓN DE AUTENTICACIÓN
    # =====================================================

    # El correo será utilizado para iniciar sesión
    USERNAME_FIELD = "email"

    # Campos obligatorios al crear un superusuario
    REQUIRED_FIELDS = [
        "username",
        "nombre",
    ]

    # =====================================================
    # MÉTODOS
    # =====================================================

    def tieneRol(self, rol):
        """
        Verifica si el usuario posee el rol indicado.
        """
        return self.rol == rol

    def __str__(self):
        """
        Devuelve el nombre del usuario.
        """
        return self.nombre