"""
Módulo de vistas de la aplicación Salas.

Contiene las vistas de consulta, alta, edición y cambio de
estado del catálogo de salas del tribunal.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso a usuarios con rol
# Administrador: Salas es un módulo de Configuración (ver
# usuarios/decorators.py).
from usuarios.decorators import solo_administrador

# Decorador que restringe el acceso únicamente a solicitudes POST.
# Se usa en cambiar_estado_sala porque esa vista modifica datos:
# igual que ocurrió con el cierre de sesión, una acción que cambia
# el estado del sistema no debe poder dispararse con un simple
# enlace GET (evita ejecuciones accidentales por precarga del
# navegador, crawlers, etc.).
from django.views.decorators.http import require_POST

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Funciones para renderizar plantillas HTML, redirigir a otra
# URL y obtener un objeto o responder 404 si no existe.
from django.shortcuts import render, redirect, get_object_or_404

# Formulario de alta de salas.
from .forms import SalaForm

# Modelo de salas del sistema.
from .models import Sala


# =====================================================
# LISTADO DE SALAS
# =====================================================

@login_required
@solo_administrador
def lista_salas(request):
    """
    Muestra el listado de salas registradas
    en el sistema.

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista:
    Salas es un módulo de Configuración.
    """

    # -------------------------------------------------
    # Obtiene todas las salas ordenadas por nombre.
    # -------------------------------------------------

    salas = Sala.objects.all().order_by("nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "salas": salas
    }

    return render(
        request,
        "salas/lista.html",
        context
    )


# =====================================================
# ALTA DE SALAS
# =====================================================

@login_required
@solo_administrador
def crear_sala(request):
    """
    Permite registrar una nueva sala del sistema.

    En GET muestra el formulario vacío. En POST valida los
    datos ingresados y, si son correctos, guarda la sala,
    notifica el éxito mediante el framework de mensajes y
    redirige al listado de salas.

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista.
    """

    if request.method == "POST":
        # ---------------------------------------------
        # Se completó el formulario: se valida y, si es
        # correcto, se guarda la nueva sala.
        # ---------------------------------------------

        form = SalaForm(request.POST)

        if form.is_valid():
            sala = form.save()

            messages.success(
                request,
                f"Sala «{sala.nombre}» creada correctamente."
            )

            return redirect("lista_salas")

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario vacío.
        # ---------------------------------------------

        form = SalaForm()

    context = {
        "form": form
    }

    return render(
        request,
        "salas/formulario.html",
        context
    )


# =====================================================
# ACTIVAR / DESACTIVAR SALAS
# =====================================================

@login_required
@solo_administrador
@require_POST
def cambiar_estado_sala(request, pk):
    """
    Activa o desactiva lógicamente una sala del sistema.

    Invierte el valor actual del campo "activa" y lo guarda.
    No elimina ningún registro de la base de datos: la sala
    permanece almacenada, solo cambia su estado.

    Notifica el resultado mediante el framework de mensajes
    (texto distinto según haya quedado activa o inactiva) y
    redirige nuevamente al listado.

    Si la sala no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista, y
    solo mediante una solicitud POST.
    """

    # -------------------------------------------------
    # Carga la sala a modificar, o responde 404 si no existe.
    # -------------------------------------------------

    sala = get_object_or_404(Sala, pk=pk)

    # -------------------------------------------------
    # Invierte el estado actual y lo guarda. update_fields
    # limita el UPDATE únicamente a la columna "activa".
    # -------------------------------------------------

    sala.activa = not sala.activa
    sala.save(update_fields=["activa"])

    if sala.activa:
        messages.success(
            request,
            f"Sala «{sala.nombre}» activada correctamente."
        )
    else:
        messages.success(
            request,
            f"Sala «{sala.nombre}» desactivada correctamente."
        )

    return redirect("lista_salas")


# =====================================================
# EDICIÓN DE SALAS
# =====================================================

@login_required
@solo_administrador
def editar_sala(request, pk):
    """
    Permite modificar una sala existente del sistema.

    En GET muestra el formulario precargado con los datos
    actuales de la sala. En POST valida los datos ingresados
    y, si son correctos, actualiza la sala, notifica el éxito
    mediante el framework de mensajes y redirige al listado
    de salas.

    Si la sala no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista.
    """

    # -------------------------------------------------
    # Carga la sala a editar, o responde 404 si no existe.
    # -------------------------------------------------

    sala = get_object_or_404(Sala, pk=pk)

    if request.method == "POST":
        # ---------------------------------------------
        # Se completó el formulario: se valida y, si es
        # correcto, se actualiza la sala existente.
        # instance=sala indica al ModelForm que debe
        # modificar este registro en vez de crear uno nuevo.
        # ---------------------------------------------

        form = SalaForm(request.POST, instance=sala)

        if form.is_valid():
            sala = form.save()

            messages.success(
                request,
                f"Sala «{sala.nombre}» actualizada correctamente."
            )

            return redirect("lista_salas")

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario precargado con los datos actuales.
        # ---------------------------------------------

        form = SalaForm(instance=sala)

    context = {
        "form": form,
        # Se envía la sala para que la plantilla, compartida
        # con la creación, sepa que está en modo edición y
        # ajuste el título y el texto del botón "Guardar".
        "sala": sala,
    }

    return render(
        request,
        "salas/formulario.html",
        context
    )
