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

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Funciones para renderizar plantillas HTML y redirigir a otra URL.
from django.shortcuts import render, redirect

# Fecha de hoy respetando la zona horaria configurada del
# proyecto (TIME_ZONE = America/Santiago, USE_TZ=True). No se
# usa datetime.date.today(): esta lectura del reloj es
# responsabilidad de la vista, nunca de services.py.
from django.utils import timezone

# Convierte el texto recibido en "?fecha=" (formato AAAA-MM-DD,
# el mismo que entrega un <input type="date">) a un objeto
# date. Devuelve None si el texto no tiene ese formato, sin
# lanzar una excepción: permite validar la fecha recibida sin
# try/except.
from django.utils.dateparse import parse_date

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

# Formulario de entrada para registrar una audiencia.
from .forms import AudienciaForm

# Modelo de audiencia del propio módulo: se usa en
# ver_disponibilidad_audiencia para consultar (solo lectura)
# qué bloques de una sala/fecha ya están ocupados.
from .models import Audiencia, EstadoAudiencia

# Servicios de negocio: coordinan la creación y generan
# propuestas automáticas de fecha. Toda regla de negocio vive
# aquí, no en esta vista.
from .services import GeneradorPropuestaFecha, ServicioCreacionAudiencia


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
    audiencia reales- y cuáles están disponibles.

    Es una consulta de presentación, de solo lectura: no valida
    plazos legales, no calcula disponibilidad "propuesta", no
    crea ni modifica nada, y no repite ninguna regla de
    ValidadorAgendamiento ni de GeneradorPropuestaFecha (no
    decide qué bloques podrían proponerse automáticamente; solo
    lista lo que ya existe en la base de datos). El funcionario
    sigue eligiendo manualmente "bloqueInicio" en el propio
    AudienciaForm; esta vista únicamente le muestra información
    para decidir con criterio.

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

    disponibilidad = [
        {
            "bloque": bloque,
            "audiencia": ordenes_ocupados.get(bloque.orden),
        }
        for bloque in BloqueHorario.objects.all().order_by("orden")
    ]

    return render(
        request,
        "audiencias/formulario.html",
        {
            "form": form,
            "causa_encontrada": causa_encontrada,
            "disponibilidad": disponibilidad,
            "sala_disponibilidad": sala,
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
        }
    )
