"""
Módulo de vistas de la aplicación Reglas de Agendamiento.

Reúne las cuatro categorías de configuración del módulo visual
"Reglas de Agendamiento" (ver mockup): General, Plazos Legales,
Asignación de días por competencia y Días Bloqueados. Las
cuatro conviven en el mismo menú/pestañas
(templates/reglas_agendamiento/_tabs.html), aunque cada una
sigue teniendo su propia URL y su propia vista, sin mezclar su
lógica.

Los modelos de "General" (ConfiguracionAgendamiento, en la app
"bloques") y de "Días Bloqueados" (DiaNoDisponible, en la app
"dias_no_disponibles") se administran desde aquí -igual que
AudienciaForm ya usa modelos de otras apps sin tocarlas-, sin
modificar esas apps.

Ninguna vista de este módulo llama a los servicios de negocio
de audiencias (ValidadorAgendamiento, GeneradorPropuestaFecha,
ServicioCreacionAudiencia, ServicioTrazabilidad): esos servicios
solo LEEN estos catálogos cuando corresponda; esta app únicamente
administra su contenido.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso únicamente a solicitudes POST.
# Se usa en las vistas "cambiar_estado_*" porque modifican datos:
# igual que en Salas/Bloques/DiaAtencion, una acción que cambia el
# estado del sistema no debe poder dispararse con un simple
# enlace GET.
from django.views.decorators.http import require_POST

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Funciones para renderizar plantillas HTML, redirigir a otra
# URL y obtener un objeto o responder 404 si no existe.
from django.shortcuts import render, redirect, get_object_or_404

# Envuelve el guardado en lote de la matriz de días de atención
# (guardar_dias_atencion) en una única transacción: si algo
# fallara a mitad de camino, no queda una actualización parcial.
from django.db import transaction

# Convierte el texto recibido en "fecha" (formato AAAA-MM-DD, el
# mismo que entrega un <input type="date">) a un objeto date.
# Devuelve None si el texto no tiene ese formato, sin lanzar una
# excepción.
from django.utils.dateparse import parse_date

# Modelo de configuración general de agendamiento (app "bloques").
from bloques.models import ConfiguracionAgendamiento

# Modelo de competencias del sistema: se usa para agrupar el
# listado de días de atención por competencia.
from competencias.models import Competencia

# Modelo de días no disponibles (app "dias_no_disponibles").
from dias_no_disponibles.models import DiaNoDisponible

# Modelo de salas del sistema: se muestra (de solo lectura) en
# la pestaña "General", reutilizando el CRUD ya existente de la
# app "salas" para sus acciones (no se duplica esa lógica aquí).
from salas.models import Sala

# Formularios de este módulo.
from .forms import (
    ConfiguracionAgendamientoForm,
    DiaNoDisponibleForm,
    ReglaAgendamientoForm,
)

# Modelos de reglas de agendamiento del sistema.
from .models import DiaAtencion, DiaSemana, ReglaAgendamiento


# =====================================================
# PESTAÑA: GENERAL
# =====================================================

@login_required
def configuracion_general(request):
    """
    Muestra y permite editar la configuración general de
    agendamiento (jornada de atención, duración de bloque,
    horizonte de búsqueda), y muestra -de solo lectura- el
    catálogo de salas.

    ConfiguracionAgendamiento es un singleton (una única
    instancia posible, garantizada a nivel de base de datos por
    su campo "claveUnica"): esta vista busca esa instancia con
    ConfiguracionAgendamiento.objects.first() y se la pasa como
    "instance" al formulario. Si todavía no existe ninguna
    (nunca se guardó una), "instance" queda en None y
    form.save() simplemente crea la primera -y única- instancia;
    no se inventan valores por defecto para los campos que no
    los tienen en el modelo, es el propio formulario quien
    exige completarlos.

    La sección de Salas es de solo lectura: no se reimplementa
    su alta/edición/activación aquí (eso ya existe, completo y
    funcional, en la app "salas"); "+ Agregar sala" y "Editar"
    llevan directamente a esas vistas existentes.

    Solo los usuarios autenticados pueden acceder a esta vista.
    """

    configuracion = ConfiguracionAgendamiento.objects.first()

    if request.method == "POST":
        form = ConfiguracionAgendamientoForm(request.POST, instance=configuracion)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Configuración general de agendamiento guardada correctamente."
            )

            return redirect("configuracion_general")

    else:
        form = ConfiguracionAgendamientoForm(instance=configuracion)

    context = {
        "form": form,
        "salas": Sala.objects.all().order_by("nombre"),
        "pestana_activa": "general",
    }

    return render(
        request,
        "reglas_agendamiento/general.html",
        context
    )


# =====================================================
# PESTAÑA: PLAZOS LEGALES
# =====================================================

@login_required
def lista_reglas_agendamiento(request):
    """
    Muestra el listado de reglas de plazo legal
    (ReglaAgendamiento) registradas en el sistema.

    Corrige un error preexistente: la versión anterior de esta
    vista ordenaba por "diaSemana"
    (order_by("competencia", "diaSemana")), un campo que
    ReglaAgendamiento ya no tiene desde que este modelo se
    repurposó hacia el plazo legal (antes representaba el día
    de la semana; esa función la cumple ahora DiaAtencion). Se
    ordena aquí por los campos reales del modelo.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    reglas = ReglaAgendamiento.objects.all().select_related(
        "competencia", "tipoAudiencia"
    ).order_by("competencia", "tipoAudiencia")

    context = {
        "reglas": reglas,
        "pestana_activa": "plazos",
    }

    return render(
        request,
        "reglas_agendamiento/lista.html",
        context
    )


@login_required
def crear_regla_agendamiento(request):
    """
    Permite configurar una regla de plazo legal
    ("+ Agregar regla"): el funcionario elige competencia, tipo
    de audiencia, plazo mínimo, plazo máximo, unidad y si queda
    activa.

    Si la combinación competencia + tipoAudiencia YA EXISTE,
    esta vista NO intenta crear un segundo registro (lo que
    violaría la UniqueConstraint del modelo): en vez de eso,
    localiza la ReglaAgendamiento existente y la actualiza,
    tal como lo haría editar_regla_agendamiento. Mismo patrón
    que configurar_dia_atencion: se busca el registro existente
    ANTES de instanciar ReglaAgendamientoForm, y se le pasa como
    "instance", para que form.save() ejecute un UPDATE sobre
    ese registro en vez de un INSERT.

    En GET muestra el formulario vacío. En POST valida los
    datos ingresados y, si son correctos, guarda (crea o
    actualiza, según corresponda), notifica el resultado
    mediante el framework de mensajes y redirige al listado de
    reglas.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    if request.method == "POST":
        # ---------------------------------------------
        # Busca si ya existe una ReglaAgendamiento para la
        # combinación competencia + tipoAudiencia recién
        # enviada, ANTES de validar el formulario. Si existe,
        # se edita ese registro en vez de crear uno nuevo.
        # ---------------------------------------------

        competencia_id = request.POST.get("competencia")
        tipo_audiencia_id = request.POST.get("tipoAudiencia")

        regla_existente = None
        if competencia_id and tipo_audiencia_id:
            regla_existente = ReglaAgendamiento.objects.filter(
                competencia_id=competencia_id,
                tipoAudiencia_id=tipo_audiencia_id,
            ).first()

        form = ReglaAgendamientoForm(request.POST, instance=regla_existente)

        if form.is_valid():
            regla = form.save()

            if regla_existente:
                messages.success(
                    request,
                    f"«{regla}» ya estaba configurada; se actualizó "
                    f"con los nuevos datos."
                )
            else:
                messages.success(
                    request,
                    f"«{regla}» configurada correctamente."
                )

            return redirect("lista_reglas_agendamiento")

    else:
        form = ReglaAgendamientoForm()

    context = {
        "form": form,
        "pestana_activa": "plazos",
    }

    return render(
        request,
        "reglas_agendamiento/regla_formulario.html",
        context
    )


@login_required
def editar_regla_agendamiento(request, pk):
    """
    Permite modificar una ReglaAgendamiento existente
    (competencia, tipo de audiencia, plazo mínimo, plazo
    máximo, unidad y/o si queda activa), accedido desde el
    botón "Editar" del listado.

    Si el cambio genera una combinación competencia+
    tipoAudiencia que ya existe en OTRO registro,
    ReglaAgendamientoForm no guarda: la validación de unicidad
    del ModelForm excluye únicamente la propia instancia que se
    está editando, por lo que detecta el choque con ese otro
    registro y devuelve un error, sin modificar ni combinar
    ambos registros.

    Si la regla no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    regla = get_object_or_404(ReglaAgendamiento, pk=pk)

    if request.method == "POST":
        form = ReglaAgendamientoForm(request.POST, instance=regla)

        if form.is_valid():
            regla = form.save()

            messages.success(
                request,
                f"«{regla}» actualizada correctamente."
            )

            return redirect("lista_reglas_agendamiento")

    else:
        form = ReglaAgendamientoForm(instance=regla)

    context = {
        "form": form,
        # Se envía la regla para que la plantilla, compartida
        # con la creación, sepa que está en modo edición y
        # ajuste el título y el texto del botón "Guardar".
        "regla": regla,
        "pestana_activa": "plazos",
    }

    return render(
        request,
        "reglas_agendamiento/regla_formulario.html",
        context
    )


@login_required
@require_POST
def cambiar_estado_regla_agendamiento(request, pk):
    """
    Activa o desactiva lógicamente una regla de plazo legal
    existente (mismo patrón que cambiar_estado_sala y
    cambiar_estado_dia_atencion).

    Invierte el valor actual del campo "activa" y lo guarda. No
    elimina físicamente ningún registro de la base de datos: la
    regla permanece almacenada, solo cambia su estado -las
    reglas pueden haber sido utilizadas para audiencias ya
    agendadas y deben conservarse como configuración histórica-.

    Notifica el resultado mediante el framework de mensajes
    (texto distinto según haya quedado activa o inactiva) y
    redirige nuevamente al listado.

    Si la regla no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados pueden acceder a esta
    vista, y solo mediante una solicitud POST.
    """

    regla = get_object_or_404(ReglaAgendamiento, pk=pk)

    regla.activa = not regla.activa
    regla.save(update_fields=["activa"])

    if regla.activa:
        messages.success(request, f"«{regla}» activada correctamente.")
    else:
        messages.success(request, f"«{regla}» desactivada correctamente.")

    return redirect("lista_reglas_agendamiento")


# =====================================================
# PESTAÑA: ASIGNACIÓN DE DÍAS POR COMPETENCIA
# =====================================================

@login_required
def dias_atencion(request):
    """
    Muestra la matriz Competencia × Día de la semana de días de
    atención: una celda por cada combinación posible, marcada
    como habilitada (verde) si existe un DiaAtencion ACTIVO
    para esa competencia y ese día, o no habilitada (gris) si
    no existe el registro o existe pero está inactivo.

    Es una vista de consulta: no crea, edita ni cambia el
    estado de ningún registro. El guardado de los cambios que
    el funcionario haga sobre la matriz ocurre en un único POST
    aparte (ver guardar_dias_atencion), disparado por el botón
    "Guardar cambios" del template, no celda por celda.

    Solo se muestran los 5 días que ya admite DiaSemana (Lunes
    a Viernes, en ese orden): el tribunal no atiende sábado ni
    domingo, así que la matriz no incluye esas dos columnas.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    dias_semana = list(DiaSemana.choices)

    # -------------------------------------------------
    # Un único query trae TODOS los DiaAtencion activos del
    # sistema; se arma un conjunto de (competencia_id, diaSemana)
    # para poder consultar cada celda de la matriz en memoria
    # (in), en vez de una consulta por cada celda o por cada
    # competencia.
    # -------------------------------------------------

    activos = set(
        DiaAtencion.objects.filter(activa=True).values_list(
            "competencia_id", "diaSemana"
        )
    )

    filas = []
    for competencia in Competencia.objects.all().order_by("nombre"):
        celdas = [
            {
                "dia": valor,
                "habilitado": (competencia.id, valor) in activos,
            }
            for valor, _etiqueta in dias_semana
        ]
        filas.append({"competencia": competencia, "celdas": celdas})

    context = {
        "dias_semana": dias_semana,
        "filas": filas,
        "pestana_activa": "dias_atencion",
    }

    return render(
        request,
        "reglas_agendamiento/dias_atencion.html",
        context
    )


@login_required
@require_POST
def guardar_dias_atencion(request):
    """
    Aplica de una sola vez todos los cambios que el funcionario
    haya hecho sobre la matriz Competencia × Día de la semana
    (ver dias_atencion): pudo haber tocado varias celdas antes
    de presionar "Guardar cambios"; esta vista compara, para
    CADA combinación competencia + día, el estado actual en la
    base de datos contra el estado deseado recién enviado, y
    solo escribe lo que efectivamente cambió:

    - existe y activo, deseado=habilitado -> sin cambios;
    - existe y activo, deseado=no habilitado -> desactivar
      (activa=False; nunca se elimina físicamente el registro);
    - existe e inactivo, deseado=habilitado -> activar
      (activa=True; nunca se crea un segundo registro, ya que
      seguiría chocando con la UniqueConstraint(competencia,
      diaSemana));
    - existe e inactivo, deseado=no habilitado -> sin cambios;
    - no existe, deseado=habilitado -> crear (activa=True);
    - no existe, deseado=no habilitado -> sin cambios (no se
      crean registros inactivos "de relleno": la ausencia del
      registro YA significa "no habilitado").

    Cada celda llega como un campo de formulario
    "dia_<competencia_id>_<diaSemana>", presente en el POST
    solo si el checkbox de esa celda quedó marcado (habilitado)
    al enviar el formulario. Se recorren TODAS las combinaciones
    competencia × día que dias_atencion ya mostró (no solo las
    que vinieron en el POST), para no depender de qué claves
    decida enviar el navegador y para poder desactivar
    correctamente una celda que el funcionario haya destildado.

    Todo el guardado ocurre dentro de una única transacción: si
    algo fallara a mitad de camino, no queda una actualización
    parcial de la matriz.

    Solo los usuarios autenticados pueden acceder a esta vista,
    y solo mediante una solicitud POST.
    """

    dias_semana = [valor for valor, _etiqueta in DiaSemana.choices]

    creados = 0
    activados = 0
    desactivados = 0

    with transaction.atomic():
        for competencia in Competencia.objects.all():
            for dia in dias_semana:
                deseado_habilitado = (
                    request.POST.get(f"dia_{competencia.id}_{dia}") == "on"
                )

                dia_atencion = DiaAtencion.objects.filter(
                    competencia=competencia, diaSemana=dia
                ).first()

                if dia_atencion is None:
                    if deseado_habilitado:
                        DiaAtencion.objects.create(
                            competencia=competencia,
                            diaSemana=dia,
                            activa=True,
                        )
                        creados += 1
                    # No existe y no se desea habilitado: no se hace nada.
                    continue

                if dia_atencion.activa and not deseado_habilitado:
                    dia_atencion.activa = False
                    dia_atencion.save(update_fields=["activa"])
                    desactivados += 1
                elif not dia_atencion.activa and deseado_habilitado:
                    dia_atencion.activa = True
                    dia_atencion.save(update_fields=["activa"])
                    activados += 1
                # El estado deseado coincide con el actual: no se hace nada.

    total_cambios = creados + activados + desactivados

    if total_cambios:
        messages.success(
            request,
            f"Se guardaron los cambios de la matriz de días de atención "
            f"({total_cambios} celda(s) actualizadas)."
        )
    else:
        messages.info(request, "No había cambios que guardar.")

    return redirect("dias_atencion")


# =====================================================
# PESTAÑA: DÍAS BLOQUEADOS
# =====================================================

@login_required
def dias_bloqueados(request):
    """
    Muestra el listado de días no disponibles
    (DiaNoDisponible) registrados en el sistema: fecha, tipo,
    motivo y estado.

    Es una vista de consulta: no crea, edita ni cambia el
    estado de ningún registro; solo lista lo que ya existe en
    la base de datos.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    dias = DiaNoDisponible.objects.all().order_by("fecha")

    context = {
        "dias_no_disponibles": dias,
        "pestana_activa": "dias_bloqueados",
    }

    return render(
        request,
        "reglas_agendamiento/dias_bloqueados.html",
        context
    )


@login_required
def crear_dia_no_disponible(request):
    """
    Permite registrar una fecha no disponible
    ("+ Agregar día bloqueado"): el funcionario indica fecha,
    tipo, motivo y si queda activo.

    Si la fecha YA EXISTE, esta vista NO intenta crear un
    segundo registro (lo que violaría la unicidad de "fecha"
    en el modelo): en vez de eso, localiza el DiaNoDisponible
    existente y lo actualiza, tal como lo haría
    editar_dia_no_disponible. Mismo patrón que
    configurar_dia_atencion/crear_regla_agendamiento: se busca
    el registro existente ANTES de instanciar
    DiaNoDisponibleForm, y se le pasa como "instance", para que
    form.save() ejecute un UPDATE sobre ese registro en vez de
    un INSERT.

    En GET muestra el formulario vacío. En POST valida los
    datos ingresados y, si son correctos, guarda (crea o
    actualiza, según corresponda), notifica el resultado
    mediante el framework de mensajes y redirige al listado de
    días bloqueados.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    if request.method == "POST":
        # ---------------------------------------------
        # Busca si ya existe un DiaNoDisponible para la
        # fecha recién enviada, ANTES de validar el
        # formulario. Si existe, se edita ese registro en
        # vez de crear uno nuevo. parse_date evita fallar
        # con una fecha con formato inválido: en ese caso
        # simplemente no encuentra coincidencia y el propio
        # formulario informará el error de formato.
        # ---------------------------------------------

        fecha = parse_date(request.POST.get("fecha") or "")

        dia_no_disponible_existente = None
        if fecha:
            dia_no_disponible_existente = DiaNoDisponible.objects.filter(
                fecha=fecha
            ).first()

        form = DiaNoDisponibleForm(request.POST, instance=dia_no_disponible_existente)

        if form.is_valid():
            dia_no_disponible = form.save()

            if dia_no_disponible_existente:
                messages.success(
                    request,
                    f"«{dia_no_disponible}» ya estaba registrado; se "
                    f"actualizó con los nuevos datos."
                )
            else:
                messages.success(
                    request,
                    f"«{dia_no_disponible}» registrado correctamente."
                )

            return redirect("dias_bloqueados")

    else:
        form = DiaNoDisponibleForm()

    context = {
        "form": form,
        "pestana_activa": "dias_bloqueados",
    }

    return render(
        request,
        "reglas_agendamiento/dia_no_disponible_formulario.html",
        context
    )


@login_required
def editar_dia_no_disponible(request, pk):
    """
    Permite modificar un DiaNoDisponible existente (fecha,
    tipo, motivo y/o si queda activo), accedido desde el botón
    "Editar" del listado.

    Si el cambio genera una fecha que ya existe en OTRO
    registro, DiaNoDisponibleForm no guarda: la validación de
    unicidad del ModelForm excluye únicamente la propia
    instancia que se está editando, por lo que detecta el
    choque con ese otro registro y devuelve un error, sin
    modificar ni combinar ambos registros.

    Si el día no disponible no existe, responde con un error
    404 (get_object_or_404).

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    dia_no_disponible = get_object_or_404(DiaNoDisponible, pk=pk)

    if request.method == "POST":
        form = DiaNoDisponibleForm(request.POST, instance=dia_no_disponible)

        if form.is_valid():
            dia_no_disponible = form.save()

            messages.success(
                request,
                f"«{dia_no_disponible}» actualizado correctamente."
            )

            return redirect("dias_bloqueados")

    else:
        form = DiaNoDisponibleForm(instance=dia_no_disponible)

    context = {
        "form": form,
        # Se envía el día no disponible para que la plantilla,
        # compartida con la creación, sepa que está en modo
        # edición y ajuste el título y el texto del botón
        # "Guardar".
        "dia_no_disponible": dia_no_disponible,
        "pestana_activa": "dias_bloqueados",
    }

    return render(
        request,
        "reglas_agendamiento/dia_no_disponible_formulario.html",
        context
    )


@login_required
@require_POST
def cambiar_estado_dia_no_disponible(request, pk):
    """
    Activa o desactiva lógicamente un día no disponible
    existente (mismo patrón que cambiar_estado_sala y
    cambiar_estado_dia_atencion).

    Invierte el valor actual del campo "activo" y lo guarda. No
    elimina físicamente ningún registro de la base de datos: el
    día no disponible permanece almacenado, solo cambia su
    estado -se conserva como configuración histórica-.

    Notifica el resultado mediante el framework de mensajes
    (texto distinto según haya quedado activo o inactivo) y
    redirige nuevamente al listado.

    Si el día no disponible no existe, responde con un error
    404 (get_object_or_404).

    Solo los usuarios autenticados pueden acceder a esta
    vista, y solo mediante una solicitud POST.
    """

    dia_no_disponible = get_object_or_404(DiaNoDisponible, pk=pk)

    dia_no_disponible.activo = not dia_no_disponible.activo
    dia_no_disponible.save(update_fields=["activo"])

    if dia_no_disponible.activo:
        messages.success(request, f"«{dia_no_disponible}» activado correctamente.")
    else:
        messages.success(request, f"«{dia_no_disponible}» desactivado correctamente.")

    return redirect("dias_bloqueados")
