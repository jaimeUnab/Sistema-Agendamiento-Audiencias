"""
Módulo de formularios de la aplicación Usuarios.

Contiene los formularios utilizados para la administración
de usuarios del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Excepción utilizada para reportar errores de validación.
from django.core.exceptions import ValidationError

# Modelo de usuario personalizado del sistema.
from .models import Usuario


# =====================================================
# FORMULARIO
# =====================================================

class UsuarioForm(forms.ModelForm):
    """
    Formulario para el registro de nuevos usuarios.

    Incluye los campos propios del modelo Usuario
    más dos campos adicionales para el ingreso
    y confirmación de la contraseña.
    """

    # Contraseña ingresada por el usuario.
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput
    )

    # Confirmación de la contraseña.
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput
    )

    class Meta:
        model = Usuario

        # Campos del modelo que incluirá el formulario.
        fields = [
            "nombre",
            "email",
            "rol",
            "is_active",
        ]

    # Orden explícito de los campos en el formulario.
    #
    # Se usa field_order (en vez de confiar en el orden
    # implícito que resulta de combinar Meta.fields con los
    # campos declarados en la clase) para que la secuencia
    # quede garantizada y documentada, sin depender de cómo
    # Django decida mezclar ambos internamente.
    #
    # Criterio del orden: agrupa los campos por etapa lógica
    # del alta de un usuario -> primero su información
    # (nombre, email, rol), luego sus credenciales
    # (password1, password2) y por último su estado
    # operativo (is_active), que no es parte del flujo de
    # identidad/credenciales sino un dato administrativo.
    field_order = [
        "nombre",
        "email",
        "rol",
        "password1",
        "password2",
        "is_active",
    ]

    # =================================================
    # VALIDACIONES
    # =================================================

    def clean_email(self):
        """
        Valida que el correo electrónico ingresado
        no esté registrado previamente en el sistema.
        """

        email = self.cleaned_data.get("email")

        if Usuario.objects.filter(email=email).exists():
            raise ValidationError(
                "Ya existe un usuario registrado con este correo electrónico."
            )

        return email

    def clean(self):
        """
        Valida que las contraseñas ingresadas
        coincidan entre sí.
        """

        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError(
                "Las contraseñas ingresadas no coinciden."
            )

        return cleaned_data

    # =================================================
    # MÉTODO SAVE
    # =================================================

    def save(self, commit=True):
        """
        Guarda el usuario cifrando la contraseña
        mediante set_password(), evitando almacenarla
        en texto plano.
        """

        # Crea la instancia del usuario sin guardarla aún.
        usuario = super().save(commit=False)

        # Cifra y asigna la contraseña ingresada.
        usuario.set_password(self.cleaned_data["password1"])

        if commit:
            usuario.save()

        return usuario
