"""
Módulo de vistas de la aplicación Audiencias.

Contiene las vistas HTTP para registrar una audiencia y para
solicitar propuestas automáticas de fecha. Coordinan
AudienciaForm y los servicios de negocio de
audiencias/services.py, pero no reimplementan ninguna de sus
reglas: solo interpretan el resultado estructurado que cada
servicio devuelve para decidir qué renderizar.

Este módulo también resuelve la Causa a partir de
"competencia" + "rit" (búsqueda de solo lectura, ver
_resolver_causa): AudienciaForm ya no incluye un selector de
Causa, así que es esta capa -HTTP- quien la busca, no
services.py ni el formulario.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso únicamente a solicitudes POST.
# Se usa en guardar_anotacion_audiencia porque esa vista modifica
# datos: mismo criterio que cambiar_estado_sala/
# cambiar_agendamiento_automatico en otras apps del proyecto.
from django.views.decorators.http import require_POST

# Agrupa el guardado de la audiencia y el registro de su
# trazabilidad en una única operación atómica (ver
# guardar_anotacion_audiencia): si registrarModificacion() fallara,
# el cambio sobre la audiencia también se revierte. Mismo criterio
# que ya usan ServicioCreacionAudiencia/ServicioBajaAudiencia en
# audiencias/services.py.
from django.db import transaction

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Funciones para renderizar plantillas HTML, redirigir a otra URL,
# y obtener un objeto o responder 404 si no existe.
from django.shortcuts import render, redirect, get_object_or_404

# Construye la URL de "agenda_diaria" para redirigir con un
# parámetro "?fecha=" (ver guardar_anotacion_audiencia).
from django.urls import reverse

# Fecha de hoy respetando la zona horaria configurada del
# proyecto (TIME_ZONE = America/Santiago, USE_TZ=True). No se
# usa datetime.date.today(): esta lectura del reloj es
# responsabilidad de la vista, nunca de services.py.
from django.utils import timezone

# Convierten el texto guardado en los snapshots de trazabilidad
# (fecha/hora en formato ISO, el mismo que produce
# ServicioTrazabilidad.fotografiar() con isoformat()) a objetos
# date/time reales, para que el template los formatee con los
# mismos filtros que el resto de la app (|date:"d/m/Y",
# |time:"H:i"). parse_date también se usa para "?fecha=" en
# agenda_diaria/ver_disponibilidad_audiencia (ver más abajo).
# Ambas devuelven None si el texto no tiene el formato esperado,
# sin lanzar una excepción.
from django.utils.dateparse import parse_date, parse_time

# Modelos necesarios para resolver los datos recibidos desde
# los distintos pasos del flujo (buscar causa, solicitar
# propuestas, ver disponibilidad de agenda): todavía no pasan
# por AudienciaForm en esos pasos, o se necesitan para la
# búsqueda de la Causa.
from bloques.models import BloqueHorario
from causas.models import Causa
from competencias.models import Competencia
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

# Formularios de entrada: registrar una audiencia, y validar el
# motivo al dejarla sin efecto.
from .forms import AudienciaForm, DejarSinEfectoAudienciaForm, MotivoBaja

# Modelo de audiencia del propio módulo: se usa en
# ver_disponibilidad_audiencia para consultar (solo lectura)
# qué bloques de una sala/fecha ya están ocupados. AccionTrazabilidad
# y EstadoAudiencia se usan en _preparar_registro_trazabilidad (ver
# más abajo) para interpretar, solo para mostrar en pantalla, los
# snapshots ya guardados por ServicioTrazabilidad -sin tocar cómo se
# generan ni se almacenan-.
from .models import AccionTrazabilidad, Audiencia, EstadoAudiencia

# Servicios de negocio: coordinan la creación, la baja lógica, la
# trazabilidad, y generan propuestas automáticas de fecha. Toda
# regla de negocio vive aquí, no en esta vista.
from .services import (
    GeneradorPropuestaFecha,
    ServicioBajaAudiencia,
    ServicioCreacionAudiencia,
    ServicioTrazabilidad,
)


# =====================================================
# BÚSQUEDA DE CAUSA (solo lectura, compartida)
# =====================================================

def _resolver_causa(competencia, rit):
    """
    Busca la Causa correspondiente a "competencia" + "rit".

    Es una operación de solo lectura, sin ninguna regla de
    negocio de agendamiento: no valida plazos, ni bloques, ni
    conflictos. Se usa desde los tres flujos de esta app
    (buscar, registrar, proponer) para no repetir esta lógica
    tres veces.

    Devuelve (causa, error):
    - Si se encuentra exactamente una Causa: (causa, None).
    - Si no se encuentra ninguna, o falta competencia/rit:
      (None, mensaje).
    - Si existiera más de una Causa con la misma combinación
      (el modelo no impone unicidad sobre competencia+rit), NO
      se elige ninguna arbitrariamente: (None, mensaje).

    IMPORTANTE: siempre se busca contra la base de datos en
    este momento, con la competencia y el rit recién recibidos
    en la solicitud actual. Nunca se confía en un identificador
    de causa que hubiera viajado desde el navegador en una
    solicitud anterior.
    """

    if not (competencia and rit):
        return None, (
            "Selecciona una competencia e ingresa un RIT para buscar la causa."
        )

    coincidencias = Causa.objects.filter(competencia=competencia, rit=rit)
    cantidad = coincidencias.count()

    if cantidad == 0:
        return None, (
            "No se encontró una causa con el RIT indicado para la "
            "competencia seleccionada."
        )

    if cantidad > 1:
        return None, (
            "Existe más de una causa registrada con ese RIT para la "
            "competencia seleccionada; no es posible determinar cuál "
            "utilizar."
        )

    return coincidencias.first(), None


# =====================================================
# REGISTRO DE AUDIENCIA
# =====================================================

@login_required
def registrar_audiencia(request):
    """
    Permite registrar una nueva audiencia.

    En GET muestra AudienciaForm vacío.

    En POST distingue tres flujos, sin mezclarlos:

    A) Buscar causa (request.POST["buscar_causa"] == "1"): solo
       busca la Causa vía competencia+rit y la muestra (RUC,
       carátula). No valida el resto del formulario -fecha y
       bloqueInicio pueden seguir vacíos a propósito- ni llama
       a ningún servicio de agendamiento.

    B) Registrar (o confirmar) audiencia: valida AudienciaForm
       por completo. Si es válido, vuelve a resolver la Causa
       (nunca se confía en un ID de causa que hubiera viajado
       desde una solicitud anterior) y, si existe, llama a
       ServicioCreacionAudiencia con confirmarAdvertencias
       según si viene o no el campo "confirmar_advertencias"
       (la confirmación reenvía los mismos datos del formulario
       principal: no se usa sesión ni se agrega ningún campo al
       modelo Audiencia). Cada llamada -primera y de
       confirmación- vuelve a ejecutar el servicio completo
       desde cero, sin reutilizar el resultado anterior.

    Solo los usuarios autenticados pueden acceder a esta vista
    (mismo criterio que el resto del proyecto: sin restricción
    de rol, como crear_sala/crear_bloque).
    """

    if request.method == "POST":

        # ---------------------------------------------
        # Flujo A: buscar causa. No se llama a
        # form.is_valid(): en este paso, tipoAudiencia/sala/
        # fecha/bloqueInicio todavía pueden estar vacíos a
        # propósito. Tampoco se llama a ningún servicio de
        # agendamiento (ServicioCreacionAudiencia ni
        # GeneradorPropuestaFecha).
        # ---------------------------------------------

        if request.POST.get("buscar_causa") == "1":
            form = AudienciaForm(request.POST)

            competencia = Competencia.objects.filter(
                pk=request.POST.get("competencia")
            ).first()
            rit = (request.POST.get("rit") or "").strip()

            causa_encontrada, error = _resolver_causa(competencia, rit)

            if error:
                messages.error(request, error)

            return render(
                request,
                "audiencias/formulario.html",
                {
                    "form": form,
                    "causa_encontrada": causa_encontrada,
                }
            )

        # ---------------------------------------------
        # Flujo B: registrar (primera vez) o confirmar. Se
        # valida el formulario completo antes que nada. Si no
        # es válido, no se busca la causa ni se llama a
        # ningún servicio.
        # ---------------------------------------------

        form = AudienciaForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                "audiencias/formulario.html",
                {"form": form}
            )

        # -----------------------------------------------
        # Se vuelve a resolver la Causa contra la base de
        # datos usando competencia+rit del propio
        # form.cleaned_data (ya validados): esta es la
        # verificación real, no un identificador que hubiera
        # viajado desde el navegador.
        # -----------------------------------------------

        competencia = form.cleaned_data["competencia"]
        rit = form.cleaned_data["rit"]
        causa, error = _resolver_causa(competencia, rit)

        if error:
            messages.error(request, error)
            return render(
                request,
                "audiencias/formulario.html",
                {"form": form}
            )

        # ---------------------------------------------
        # El campo "confirmar_advertencias" solo lo envía el
        # botón "Confirmar programación" (ver template); en
        # la primera solicitud no viene, por lo que
        # confirmar_advertencias queda en False.
        # ---------------------------------------------

        confirmar_advertencias = (
            request.POST.get("confirmar_advertencias") == "1"
        )

        resultado = ServicioCreacionAudiencia(
            causa=causa,
            tipoAudiencia=form.cleaned_data["tipoAudiencia"],
            sala=form.cleaned_data["sala"],
            cantidadBloques=form.cleaned_data["cantidadBloques"],
            fecha=form.cleaned_data["fecha"],
            bloqueInicio=form.cleaned_data["bloqueInicio"],
            usuario=request.user,
            fecha_referencia=timezone.localdate(),
            confirmarAdvertencias=confirmar_advertencias,
            # Anotación libre asociada a la audiencia completa,
            # armada en la interfaz mientras la audiencia todavía
            # estaba solo "Seleccionada" (ver
            # templates/audiencias/formulario.html: campo oculto
            # "anotacion" dentro de este mismo <form>). No es un
            # dato que se valide; se guarda tal como llega.
            anotacion=form.cleaned_data.get("anotacion", ""),
        ).crear()

        # ---------------------------------------------
        # Éxito: se guardó la audiencia (y, dentro de
        # ServicioCreacionAudiencia, su RegistroTrazabilidad
        # de creación). Esta vista no crea trazabilidad
        # directamente.
        # ---------------------------------------------

        if resultado["guardada"]:
            messages.success(
                request,
                f"«{resultado['audiencia']}» registrada correctamente."
            )
            return redirect("registrar_audiencia")

        # ---------------------------------------------
        # Hay advertencias y ningún error: no se guarda
        # todavía. Se muestran las advertencias y se ofrece
        # confirmar, conservando los datos ya ingresados
        # (mismo form, con sus valores, y la causa ya
        # encontrada).
        # ---------------------------------------------

        if resultado["requiereConfirmacion"]:
            return render(
                request,
                "audiencias/formulario.html",
                {
                    "form": form,
                    "causa_encontrada": causa,
                    "advertencias": resultado["advertencias"],
                    "requiere_confirmacion": True,
                }
            )

        # ---------------------------------------------
        # Hay errores bloqueantes: no se guarda nada. Se
        # notifican mediante el framework de mensajes (mismo
        # criterio que el resto del proyecto) y se vuelve a
        # mostrar el formulario con los datos ingresados. Si
        # además vinieran advertencias junto con los errores,
        # también se muestran (no se ocultan).
        # ---------------------------------------------

        for err in resultado["errores"]:
            messages.error(request, err)

        return render(
            request,
            "audiencias/formulario.html",
            {
                "form": form,
                "causa_encontrada": causa,
                "advertencias": resultado["advertencias"],
            }
        )

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario vacío. No se guarda ninguna audiencia.
        # ---------------------------------------------

        form = AudienciaForm()

    return render(
        request,
        "audiencias/formulario.html",
        {"form": form}
    )


# =====================================================
# PROPUESTAS DE FECHA
# =====================================================

@login_required
def proponer_fechas_audiencia(request):
    """
    Solicita hasta 3 propuestas automáticas de fecha/bloques
    para los datos ya seleccionados por el funcionario (causa
    -localizada vía competencia+rit-, tipoAudiencia, sala,
    cantidadBloques), usando GeneradorPropuestaFecha.

    En este paso "fecha" y "bloqueInicio" del AudienciaForm
    todavía no están completados (es justamente lo que las
    propuestas ayudan a elegir), por lo que aquí NO se llama a
    form.is_valid(): ese método fallaría siempre, porque esos
    dos campos son obligatorios para registrar la audiencia
    pero no para pedir propuestas. En su lugar, competencia/
    rit/tipoAudiencia/sala/cantidadBloques se leen directamente
    de request.POST y se resuelven a sus objetos -incluida la
    Causa, mediante _resolver_causa(), la misma función que usa
    el flujo de búsqueda y el de registro-.

    Esta vista no decide si una fecha está dentro o fuera de
    plazo, no busca otra sala si la elegida tiene conflictos,
    ni repite ninguna otra regla de negocio: todo eso ya lo
    resuelve GeneradorPropuestaFecha. Si la sala está inactiva,
    el generador lanza ValueError, que aquí se captura y se
    muestra como error, sin cambiar de sala automáticamente.

    Solo los usuarios autenticados pueden acceder a esta
    vista.
    """

    if request.method != "POST":
        return redirect("registrar_audiencia")

    # -------------------------------------------------
    # Se conserva lo ya ingresado por el funcionario para
    # volver a mostrarlo (formulario "vinculado" a estos
    # datos, sin llamar a is_valid(): ver docstring).
    # -------------------------------------------------

    form = AudienciaForm(request.POST)

    competencia = Competencia.objects.filter(
        pk=request.POST.get("competencia")
    ).first()
    rit = (request.POST.get("rit") or "").strip()

    causa, error = _resolver_causa(competencia, rit)

    if error:
        messages.error(request, error)
        return render(request, "audiencias/formulario.html", {"form": form})

    tipo_audiencia = TipoAudiencia.objects.filter(
        pk=request.POST.get("tipoAudiencia")
    ).first()
    sala = Sala.objects.filter(pk=request.POST.get("sala")).first()
    cantidad_bloques_raw = request.POST.get("cantidadBloques")

    if not (tipo_audiencia and sala and cantidad_bloques_raw):
        messages.error(
            request,
            "Selecciona tipo de audiencia, sala y cantidad de bloques "
            "antes de solicitar propuestas."
        )
        return render(
            request,
            "audiencias/formulario.html",
            {"form": form, "causa_encontrada": causa}
        )

    try:
        cantidad_bloques = int(cantidad_bloques_raw)
    except (TypeError, ValueError):
        messages.error(request, "La cantidad de bloques ingresada no es válida.")
        return render(
            request,
            "audiencias/formulario.html",
            {"form": form, "causa_encontrada": causa}
        )

    # -------------------------------------------------
    # Genera las propuestas. Si la sala está inactiva,
    # GeneradorPropuestaFecha lanza ValueError: se captura
    # aquí y se muestra como error, sin buscar otra sala.
    # -------------------------------------------------

    try:
        propuestas = GeneradorPropuestaFecha(
            causa=causa,
            tipoAudiencia=tipo_audiencia,
            sala=sala,
            cantidadBloques=cantidad_bloques,
            fecha_referencia=timezone.localdate(),
        ).generar()
    except ValueError as error_generador:
        messages.error(request, str(error_generador))
        return render(
            request,
            "audiencias/formulario.html",
            {"form": form, "causa_encontrada": causa}
        )

    return render(
        request,
        "audiencias/formulario.html",
        {
            "form": form,
            "causa_encontrada": causa,
            "propuestas": propuestas,
        }
    )


# =====================================================
# DISPONIBILIDAD DE AGENDA (consulta de solo lectura)
# =====================================================

@login_required
def ver_disponibilidad_audiencia(request):
    """
    Muestra, para la sala y fecha ya seleccionadas, qué bloques
    horarios configurados (BloqueHorario) están ocupados por
    otra Audiencia PROGRAMADA -con su RIT, carátula y tipo de
    audiencia reales-, cuáles están disponibles, y cuáles caen
    dentro del rango que el funcionario está a punto de elegir
    (bloqueInicio + cantidadBloques), mostrados como
    "Seleccionado" con el RIT/carátula/tipo de audiencia que se
    está armando.

    "Seleccionado" es puramente una previsualización en
    memoria: no crea ni guarda ninguna Audiencia ni ningún otro
    registro (ver más abajo). Un bloque ya "Ocupado" por una
    Audiencia real conserva siempre esa prioridad -es
    información real, no una posibilidad-, aunque también caiga
    dentro del rango recién elegido.

    Es una consulta de presentación, de solo lectura: no valida
    plazos legales, no calcula disponibilidad "propuesta", no
    crea ni modifica nada, y no repite ninguna regla de
    ValidadorAgendamiento ni de GeneradorPropuestaFecha (no
    decide qué bloques podrían proponerse automáticamente; solo
    lista lo que ya existe en la base de datos, más lo que el
    propio funcionario ya escribió en este mismo envío). El
    funcionario sigue eligiendo manualmente "bloqueInicio" en el
    propio AudienciaForm; esta vista únicamente le muestra
    información para decidir con criterio.

    Requiere que "sala" y "fecha" ya estén completados en el
    formulario (no requiere causa ni el resto de los campos,
    que pueden seguir vacíos a propósito).

    Solo los usuarios autenticados pueden acceder a esta
    vista.
    """

    if request.method != "POST":
        return redirect("registrar_audiencia")

    form = AudienciaForm(request.POST)

    sala = Sala.objects.filter(pk=request.POST.get("sala")).first()
    fecha = request.POST.get("fecha")

    # -------------------------------------------------
    # Conserva la causa ya encontrada, si competencia+rit
    # siguen presentes en esta misma solicitud (misma función
    # de búsqueda que usan los otros dos flujos, sin repetirla).
    # -------------------------------------------------

    competencia = Competencia.objects.filter(
        pk=request.POST.get("competencia")
    ).first()
    rit = (request.POST.get("rit") or "").strip()
    causa_encontrada, _error_causa = _resolver_causa(competencia, rit)

    if not (sala and fecha):
        messages.error(
            request,
            "Selecciona una sala y una fecha para ver la disponibilidad "
            "de agenda."
        )
        return render(
            request,
            "audiencias/formulario.html",
            {"form": form, "causa_encontrada": causa_encontrada}
        )

    # -------------------------------------------------
    # "fecha" (string "AAAA-MM-DD", tal como llega de
    # request.POST) se sigue usando tal cual para la consulta
    # de más abajo -no se toca esa lógica-. fecha_disponibilidad
    # es, en cambio, un objeto date, solo para que el template
    # pueda mostrar "Jueves 14 de agosto de 2026" (día de la
    # semana + fecha en español) junto a la tabla. parse_date
    # devuelve None si el texto no tuviera un formato válido
    # -no debería ocurrir, ya que siempre llega desde un
    # <input type="date"> o desde el mismo formato que arma el
    # script de navegación por flechas-, en cuyo caso el
    # template simplemente no muestra el encabezado de fecha.
    # -------------------------------------------------

    fecha_disponibilidad = parse_date(fecha)

    # -------------------------------------------------
    # Arma, para cada "orden" de bloque, qué Audiencia lo
    # ocupa (si alguna), a partir de bloqueInicio.orden +
    # cantidadBloques -mismo criterio de rango ya usado en
    # services.py, aplicado aquí solo para listar, no para
    # validar ni decidir nada-.
    # -------------------------------------------------

    ordenes_ocupados = {}

    audiencias_del_dia = Audiencia.objects.filter(
        sala=sala,
        fecha=fecha,
        estado=EstadoAudiencia.PROGRAMADA,
    ).select_related("causa", "tipoAudiencia", "bloqueInicio")

    for audiencia in audiencias_del_dia:
        inicio = audiencia.bloqueInicio.orden
        fin = inicio + audiencia.cantidadBloques - 1
        for orden in range(inicio, fin + 1):
            ordenes_ocupados[orden] = audiencia

    # -------------------------------------------------
    # Previsualización de los bloques que el funcionario está a
    # punto de elegir (bloqueInicio + cantidadBloques), tal como
    # vienen en ESTE MISMO envío. Es solo de presentación: no se
    # guarda nada -ninguna Audiencia ni ningún otro registro-;
    # únicamente se calcula, en memoria, qué "orden" de bloque
    # caería dentro de ese rango, con el mismo criterio
    # (bloqueInicio.orden + cantidadBloques - 1) que ya usa
    # services.py al guardar de verdad. Si falta causa
    # encontrada, tipo de audiencia, bloque de inicio o cantidad
    # de bloques, simplemente no hay nada que previsualizar
    # todavía: la tabla se comporta exactamente igual que antes
    # (solo Ocupado/Disponible).
    # -------------------------------------------------

    # "Ver disponibilidad" tiene formnovalidate: es normal que el
    # funcionario lo presione antes de haber elegido tipoAudiencia/
    # bloqueInicio/cantidadBloques todavía. En ese caso llegan como
    # cadena vacía "" (no ausentes), y un id vacío no es un id
    # válido para consultar por pk -.filter(pk="") lanza ValueError
    # en un campo numérico, a diferencia de pk=None, que
    # simplemente no encuentra nada-. Por eso se comprueba primero
    # que el valor no esté vacío antes de consultar.

    tipoAudiencia_id = request.POST.get("tipoAudiencia")
    tipo_audiencia_seleccionado = (
        TipoAudiencia.objects.filter(pk=tipoAudiencia_id).first()
        if tipoAudiencia_id else None
    )

    bloqueInicio_id = request.POST.get("bloqueInicio")
    bloque_inicio_seleccionado = (
        BloqueHorario.objects.filter(pk=bloqueInicio_id).first()
        if bloqueInicio_id else None
    )

    try:
        cantidad_bloques_seleccionada = int(request.POST.get("cantidadBloques"))
    except (TypeError, ValueError):
        cantidad_bloques_seleccionada = None

    ordenes_seleccionados = set()

    if (
        causa_encontrada
        and tipo_audiencia_seleccionado
        and bloque_inicio_seleccionado
        and cantidad_bloques_seleccionada
        and cantidad_bloques_seleccionada > 0
    ):
        inicio_seleccion = bloque_inicio_seleccionado.orden
        fin_seleccion = inicio_seleccion + cantidad_bloques_seleccionada - 1
        ordenes_seleccionados = set(range(inicio_seleccion, fin_seleccion + 1))

    disponibilidad = []

    for bloque in BloqueHorario.objects.all().order_by("orden"):
        audiencia_ocupante = ordenes_ocupados.get(bloque.orden)

        disponibilidad.append({
            "bloque": bloque,
            "audiencia": audiencia_ocupante,
            # Un bloque ya "Ocupado" por una Audiencia real
            # conserva siempre esa prioridad sobre la
            # previsualización: es información real, no una
            # posibilidad. Si además cae dentro del rango recién
            # elegido, ese conflicto ya lo reporta
            # ValidadorAgendamiento como advertencia aparte; esta
            # tabla no lo disfraza de "Seleccionado".
            "seleccionado": (
                audiencia_ocupante is None
                and bloque.orden in ordenes_seleccionados
            ),
        })

    return render(
        request,
        "audiencias/formulario.html",
        {
            "form": form,
            "causa_encontrada": causa_encontrada,
            "disponibilidad": disponibilidad,
            "sala_disponibilidad": sala,
            "tipo_audiencia_seleccionado": tipo_audiencia_seleccionado,
            "fecha_disponibilidad": fecha_disponibilidad,
        }
    )


# =====================================================
# AGENDA DIARIA (consulta de solo lectura)
# =====================================================

@login_required
def agenda_diaria(request):
    """
    Muestra la agenda diaria de audiencias: para una fecha
    seleccionada, lista las audiencias PROGRAMADAS de ese día,
    agrupadas por sala.

    Es una vista de solo lectura, igual que
    ver_disponibilidad_audiencia: no crea, modifica ni da de
    baja ninguna Audiencia (nunca llama a audiencia.save()), y
    no repite ninguna regla de negocio de ValidadorAgendamiento
    ni de GeneradorPropuestaFecha -no decide disponibilidad ni
    propone nada, solo lista lo que ya existe en la base de
    datos-.

    La fecha a consultar llega por GET (?fecha=AAAA-MM-DD, el
    mismo formato que entrega un <input type="date">), porque
    es una consulta/filtro, no una operación que cambie datos.
    Si no viene ninguna fecha (primer ingreso a la pantalla) se
    usa timezone.localdate() -nunca date.today()-, la fecha
    actual respetando la zona horaria del proyecto
    (America/Santiago, ver TIME_ZONE en settings). Si la fecha
    recibida no tiene un formato válido, se informa mediante el
    framework de mensajes y se vuelve a usar la fecha actual.

    Solo los usuarios autenticados pueden acceder a esta vista
    (mismo criterio que el resto de las vistas del proyecto).
    """

    fecha_parametro = request.GET.get("fecha")

    if fecha_parametro:
        fecha = parse_date(fecha_parametro)
        if fecha is None:
            messages.error(request, "La fecha ingresada no es válida.")
            fecha = timezone.localdate()
    else:
        fecha = timezone.localdate()

    # ---------------------------------------------------
    # Consulta las audiencias PROGRAMADAS de la fecha
    # seleccionada, usando exactamente el nombre de estado ya
    # definido en audiencias/models.py -
    # EstadoAudiencia.PROGRAMADA-, sin inventar ningún nombre
    # nuevo. Las ELIMINADAS (baja lógica) quedan excluidas por
    # el propio filtro.
    #
    # select_related evita una consulta adicional por cada
    # audiencia al acceder a causa/tipoAudiencia/sala/
    # bloqueInicio desde el template.
    #
    # order_by("sala", "bloqueInicio__orden"): ordena primero
    # por sala y, dentro de cada sala, por el orden del bloque
    # de inicio, tal como fue pedido.
    # ---------------------------------------------------

    audiencias_del_dia = Audiencia.objects.filter(
        fecha=fecha,
        estado=EstadoAudiencia.PROGRAMADA,
    ).select_related(
        "causa",
        "tipoAudiencia",
        "sala",
        "bloqueInicio",
    ).order_by("sala", "bloqueInicio__orden")

    # ---------------------------------------------------
    # Agrupa las audiencias por sala en Python (una sola
    # consulta ya trae todo lo necesario, gracias a
    # select_related). Se muestran TODAS las salas existentes
    # -no solo las que tengan audiencias ese día-: si una sala
    # no tiene audiencias programadas, su sección igual
    # aparece, con "Sin audiencias programadas.".
    # Sala.objects.all() ya viene ordenada por nombre (Meta.
    # ordering de Sala), sin necesidad de buscar ni modificar
    # nada de la app Salas.
    # ---------------------------------------------------

    audiencias_por_sala = {}
    for audiencia in audiencias_del_dia:
        audiencias_por_sala.setdefault(audiencia.sala_id, []).append(audiencia)

    agenda_por_sala = [
        {
            "sala": sala,
            "audiencias": audiencias_por_sala.get(sala.id, []),
        }
        for sala in Sala.objects.all()
    ]

    return render(
        request,
        "audiencias/agenda.html",
        {
            "fecha": fecha,
            "agenda_por_sala": agenda_por_sala,
            "hay_audiencias": bool(audiencias_por_sala),
            # Opciones del <select> "Motivo de eliminación" del
            # modal "Dejar sin efecto" (ver
            # dejar_sin_efecto_audiencia más abajo). No es un
            # dato de la agenda en sí: se pasa aquí porque el
            # modal vive en este mismo template.
            "motivos_baja": MotivoBaja.choices,
        }
    )


# =====================================================
# ANOTACIÓN (audiencia ya registrada)
# =====================================================

@login_required
@require_POST
def guardar_anotacion_audiencia(request):
    """
    Agrega o modifica la anotación de una Audiencia YA
    REGISTRADA: se accede desde el botón 📝 de una fila
    "Ocupado" en la tabla de "Disponibilidad de agenda" (ver
    templates/audiencias/formulario.html), distinto del campo
    oculto "anotacion" del <form> principal -ese otro solo
    aplica MIENTRAS la audiencia todavía está en estado
    "Seleccionado", sin guardar (ver registrar_audiencia más
    arriba)-.

    La anotación pertenece a la audiencia completa (no a un
    bloque individual ni a la causa): se guarda directamente
    sobre el campo "anotacion" de la Audiencia indicada,
    idéntico en espíritu a cambiar_estado_sala/
    cambiar_agendamiento_automatico (otras apps del proyecto):
    una actualización puntual de un único campo, sin repetir
    ninguna regla de ValidadorAgendamiento ni de
    ServicioCreacionAudiencia -la anotación no es un dato que
    esas reglas validen ni que afecte el agendamiento-.

    A diferencia de cambiar_estado_sala/
    cambiar_agendamiento_automatico, este cambio SÍ queda
    registrado en RegistroTrazabilidad: se sigue exactamente el
    flujo de MODIFICACION ya documentado en el docstring de
    ServicioTrazabilidad (audiencias/services.py) -fotografiar
    ANTES de modificar, guardar, y recién ahí
    registrarModificacion() con esa fotografía previa-, envuelto
    en transaction.atomic() para que, si registrarModificacion()
    fallara, el cambio sobre "anotacion" también se revierta y no
    quede una audiencia modificada sin su trazabilidad
    correspondiente. El usuario responsable es siempre
    request.user (el mismo criterio de autoría que usa
    ServicioCreacionAudiencia/ServicioBajaAudiencia).

    Tras guardar, redirige a la agenda diaria de la fecha de esa
    audiencia (?fecha=...), para que el funcionario vea de
    inmediato que el cambio se aplicó sobre la audiencia
    correcta. No se modificó agenda_diaria ni su plantilla para
    esto: solo se navega hacia esa vista ya existente, igual que
    cualquier enlace del sidebar.

    Si la audiencia no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados pueden acceder a esta vista,
    y solo mediante una solicitud POST.
    """

    audiencia = get_object_or_404(
        Audiencia, pk=request.POST.get("audiencia_id")
    )

    nueva_anotacion = (request.POST.get("anotacion") or "").strip()

    # Fotografía ANTES de modificar, tal como exige el contrato
    # documentado en ServicioTrazabilidad: una vez guardado el
    # nuevo valor, el valor anterior ya no existe en la instancia.
    anterior = ServicioTrazabilidad.fotografiar(audiencia)

    with transaction.atomic():
        audiencia.anotacion = nueva_anotacion
        audiencia.save(update_fields=["anotacion"])
        ServicioTrazabilidad.registrarModificacion(
            audiencia, request.user, valoresAnteriores=anterior
        )

    if audiencia.anotacion:
        messages.success(request, "Anotación guardada correctamente.")
    else:
        messages.success(request, "Anotación eliminada correctamente.")

    return redirect(
        f"{reverse('agenda_diaria')}?fecha={audiencia.fecha.isoformat()}"
    )


# =====================================================
# BAJA LÓGICA (audiencia ya registrada)
# =====================================================

@login_required
@require_POST
def dejar_sin_efecto_audiencia(request):
    """
    Deja sin efecto (baja lógica) una Audiencia PROGRAMADA, con
    motivo obligatorio (ver modal "Dejar sin efecto" en
    templates/audiencias/agenda.html). Mismo criterio de acceso
    que guardar_anotacion_audiencia: solo usuarios autenticados,
    solo mediante una solicitud POST.

    Toda la regla de negocio -no borrar físicamente, exigir
    estado PROGRAMADA, registrar trazabilidad- vive en
    ServicioBajaAudiencia; esta vista solo valida el motivo
    recibido (DejarSinEfectoAudienciaForm), resuelve la Audiencia
    y traduce el resultado del servicio a mensajes para el
    funcionario.

    Si el formulario de motivo es inválido (motivo faltante, o
    "Otro" sin explicación), no se llama a ServicioBajaAudiencia:
    no se guarda ni se modifica nada.

    Si la audiencia no existe, responde con un error 404
    (get_object_or_404, mismo criterio que
    guardar_anotacion_audiencia).

    Tras la operación -exitosa o no- redirige a la agenda diaria
    de la fecha de esa audiencia, igual que
    guardar_anotacion_audiencia.
    """

    audiencia = get_object_or_404(
        Audiencia, pk=request.POST.get("audiencia_id")
    )

    form = DejarSinEfectoAudienciaForm(request.POST)

    if form.is_valid():
        resultado = ServicioBajaAudiencia(
            audiencia=audiencia,
            usuario=request.user,
            motivo=form.motivo_texto(),
        ).ejecutar()

        if resultado["exito"]:
            messages.success(
                request, "Audiencia dejada sin efecto correctamente."
            )
        else:
            messages.error(request, resultado["error"])
    else:
        for errores_campo in form.errors.values():
            for error in errores_campo:
                messages.error(request, error)

    return redirect(
        f"{reverse('agenda_diaria')}?fecha={audiencia.fecha.isoformat()}"
    )


# =====================================================
# TRAZABILIDAD (audiencia ya registrada, solo lectura)
# =====================================================
# Las funciones _nombreTipoAudiencia/_nombreSala/_etiquetaEstado/
# _fechaDelSnapshot/_detalleCreacion/_detalleBaja/_detalleAnotacion/
# _preparar_registro_trazabilidad, más abajo, son EXCLUSIVAMENTE de
# presentación: traducen los snapshots JSON que ServicioTrazabilidad
# ya guardó (fotografiar(), sin ningún cambio) a la información que
# le sirve a un funcionario para leer el historial de una audiencia.
# No crean, modifican ni recalculan ningún RegistroTrazabilidad; no
# tocan Audiencia; no agregan ningún valor a AccionTrazabilidad. Una
# audiencia registrada no se puede modificar -las únicas operaciones
# reales son Creación, Baja/Dejar sin efecto y Anotación-, así que
# esta interpretación cubre exactamente esas tres, nada más.

def _nombreTipoAudiencia(tipo_audiencia_id):
    """
    Resuelve el ID de tipo de audiencia guardado en un snapshot a
    su nombre legible. Como Audiencia.tipoAudiencia usa
    on_delete=PROTECT, el TipoAudiencia referenciado por un ID ya
    guardado nunca pudo eliminarse -pero igual se usa .first() (no
    .get()) para no romper la pantalla si de todos modos faltara.
    """
    tipo = TipoAudiencia.objects.filter(pk=tipo_audiencia_id).first()
    return tipo.nombre if tipo else "(tipo de audiencia no disponible)"


def _nombreSala(sala_id):
    """
    Resuelve el ID de sala guardado en un snapshot a su nombre
    legible. Mismo criterio que _nombreTipoAudiencia: Sala también
    usa on_delete=PROTECT en Audiencia.
    """
    sala = Sala.objects.filter(pk=sala_id).first()
    return sala.nombre if sala else "(sala no disponible)"


def _etiquetaEstado(codigo_estado):
    """
    Traduce un código de estado guardado en un snapshot ("PROGRAMADA"
    / "ELIMINADA") a la misma etiqueta legible que
    EstadoAudiencia.choices ya define (Audiencia.get_estado_display()
    no puede usarse aquí: el snapshot es un dict, no una instancia de
    Audiencia).
    """
    if not codigo_estado:
        return ""
    try:
        return EstadoAudiencia(codigo_estado).label
    except ValueError:
        # Defensivo: un código que no coincidiera con ningún valor
        # de EstadoAudiencia se muestra tal cual, en vez de fallar.
        return codigo_estado


def _fechaDelSnapshot(snapshot):
    """
    Extrae fecha/horaInicio/horaTermino de un snapshot (dict) y los
    convierte a objetos date/time reales -parse_date/parse_time,
    mismas funciones que ya usa el resto de este módulo-, para que
    el template los formatee con los filtros |date/|time de
    siempre. Común a Creación, Baja y Anotación: ninguna de las
    tres operaciones cambia la fecha ni el horario ya agendado de
    la audiencia.
    """
    return {
        "fecha": parse_date(snapshot.get("fecha")) if snapshot.get("fecha") else None,
        "horaInicio": (
            parse_time(snapshot.get("horaInicio"))
            if snapshot.get("horaInicio")
            else None
        ),
        "horaTermino": (
            parse_time(snapshot.get("horaTermino"))
            if snapshot.get("horaTermino")
            else None
        ),
    }


def _detalleCreacion(nuevos):
    """
    Arma el detalle a mostrar para un registro de Creación: tipo de
    audiencia y sala ya resueltos a su nombre, fecha/horario
    agendado, cantidad de bloques, y la anotación inicial SOLO si
    no llegó vacía. No incluye ningún ID técnico (audiencia, causa,
    tipoAudiencia, sala, bloqueInicio, usuarioCreacion), ni
    "estado" (siempre nace PROGRAMADA, es obvio en una creación), ni
    "motivoBaja" (siempre vacío acá), ni "fechaCreacion" (redundante
    con la propia fechaHora del registro).
    """
    detalle = _fechaDelSnapshot(nuevos)
    detalle["tipoAudiencia"] = _nombreTipoAudiencia(nuevos.get("tipoAudienciaId"))
    detalle["sala"] = _nombreSala(nuevos.get("salaId"))
    detalle["cantidadBloques"] = nuevos.get("cantidadBloques")

    anotacion_inicial = (nuevos.get("anotacion") or "").strip()
    detalle["anotacion"] = anotacion_inicial or None

    return detalle


def _detalleBaja(anteriores, nuevos):
    """
    Arma el detalle a mostrar para un registro de Baja: fecha/
    horario agendado (sin cambios, se incluye solo como contexto),
    la transición de estado ("Programada" -> "Eliminada") y el
    motivo de la baja. No repite el resto de los campos del
    snapshot (causa, tipo de audiencia, sala, bloque, cantidad de
    bloques, anotación): ninguno cambia al dar de baja una
    audiencia.
    """
    detalle = _fechaDelSnapshot(nuevos)
    detalle["estadoAnterior"] = _etiquetaEstado(anteriores.get("estado"))
    detalle["estadoNuevo"] = _etiquetaEstado(nuevos.get("estado"))
    detalle["motivo"] = nuevos.get("motivoBaja") or ""

    return detalle


def _detalleAnotacion(anteriores, nuevos):
    """
    Arma el detalle a mostrar para un registro de Anotación: fecha/
    horario agendado (sin cambios, se incluye solo como contexto), y
    la anotación anterior/nueva. No repite el resto de los campos
    del snapshot: ninguno cambia al modificar la anotación (es el
    único campo que guardar_anotacion_audiencia toca).
    """
    detalle = _fechaDelSnapshot(nuevos)
    detalle["anotacionAnterior"] = (anteriores.get("anotacion") or "").strip()
    detalle["anotacionNueva"] = (nuevos.get("anotacion") or "").strip()

    return detalle


def _preparar_registro_trazabilidad(registro):
    """
    Traduce un RegistroTrazabilidad ya guardado (fechaHora, usuario,
    accion, valoresAnteriores, valoresNuevos -tal cual los guarda
    ServicioTrazabilidad, sin ningún cambio aquí ni en el modelo-) a
    lo que realmente le sirve al funcionario, según la operación real
    que representa.

    IMPORTANTE: AccionTrazabilidad (audiencias/models.py) no tiene un
    valor "ANOTACION". Hoy el único flujo de todo el sistema que
    invoca ServicioTrazabilidad.registrarModificacion() es
    guardar_anotacion_audiencia -no existe ninguna otra forma de
    "modificar" una audiencia ya registrada, porque no se puede
    editar-. Por eso, únicamente en esta interpretación para
    pantalla (sin tocar el modelo ni el enum), un registro con
    accion=MODIFICACION se rotula como "Anotación".

    Devuelve un dict con "fechaHora", "usuario", "accionLabel", "tipo"
    ("creacion"/"baja"/"anotacion", para que el template elija qué
    bloque de detalle mostrar) y "detalle" (dict con las claves
    específicas de esa operación, armado por _detalleCreacion/
    _detalleBaja/_detalleAnotacion).
    """
    anteriores = registro.valoresAnteriores or {}
    nuevos = registro.valoresNuevos or {}

    if registro.accion == AccionTrazabilidad.CREACION:
        tipo = "creacion"
        accion_label = "Creación de audiencia"
        detalle = _detalleCreacion(nuevos)
    elif registro.accion == AccionTrazabilidad.BAJA:
        tipo = "baja"
        accion_label = "Audiencia dejada sin efecto"
        detalle = _detalleBaja(anteriores, nuevos)
    else:
        # AccionTrazabilidad.MODIFICACION: ver nota de la sección
        # arriba, hoy siempre corresponde al flujo de anotación.
        tipo = "anotacion"
        accion_label = "Anotación"
        detalle = _detalleAnotacion(anteriores, nuevos)

    return {
        "fechaHora": registro.fechaHora,
        "usuario": registro.usuario,
        "accionLabel": accion_label,
        "tipo": tipo,
        "detalle": detalle,
    }


@login_required
def ver_trazabilidad_audiencia(request, pk):
    """
    Muestra los registros de RegistroTrazabilidad asociados a una
    Audiencia, del más antiguo al más reciente. Es una vista de
    solo lectura: no crea, modifica ni elimina ningún
    RegistroTrazabilidad (esos ya quedaron creados por
    ServicioTrazabilidad al momento de cada operación real -
    creación, baja, anotación-; esta vista únicamente consulta e
    interpreta lo que ya existe, mediante
    _preparar_registro_trazabilidad).

    Se accede desde el botón "Ver trazabilidad" de una fila de la
    agenda diaria (ver templates/audiencias/agenda.html). La
    audiencia se identifica por su "pk" en la propia URL (a
    diferencia de guardar_anotacion_audiencia/
    dejar_sin_efecto_audiencia, que la reciben por POST: esta vista
    es de solo consulta, por GET, así que puede -y conviene- que la
    URL identifique directamente qué audiencia se está consultando).

    Los registros se obtienen a través de
    audiencia.registros_trazabilidad (related_name definido en
    RegistroTrazabilidad.audiencia), filtrando así, de forma
    automática, únicamente los que pertenecen a esta Audiencia. Se
    ordenan explícitamente por "fechaHora" ascendente (del más
    antiguo al más reciente): el Meta.ordering por defecto del
    modelo es descendente (ver audiencias/models.py), pensado para
    un historial general; acá se pide el orden cronológico inverso,
    así que se especifica explícitamente en la consulta en vez de
    apoyarse en ese valor por defecto.

    select_related("usuario") evita una consulta adicional por cada
    registro al mostrar su usuario responsable en el template. El
    contexto "registros" ya NO es el QuerySet crudo: es una lista de
    dicts (uno por cada RegistroTrazabilidad, en el mismo orden),
    armada por _preparar_registro_trazabilidad, lista para que el
    template la recorra sin interpretar JSON ni resolver ningún ID.

    Si la audiencia no existe, responde con un error 404
    (get_object_or_404, mismo criterio que el resto de las vistas
    de esta app que reciben un identificador de Audiencia).

    Solo los usuarios autenticados pueden acceder a esta vista
    (mismo criterio que agenda_diaria, guardar_anotacion_audiencia y
    dejar_sin_efecto_audiencia: sin restricción adicional de rol).
    """

    audiencia = get_object_or_404(Audiencia, pk=pk)

    registros_crudos = audiencia.registros_trazabilidad.select_related(
        "usuario"
    ).order_by("fechaHora")

    registros = [
        _preparar_registro_trazabilidad(registro) for registro in registros_crudos
    ]

    return render(
        request,
        "audiencias/trazabilidad.html",
        {
            "audiencia": audiencia,
            "registros": registros,
        },
    )
