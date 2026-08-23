# =====================================================
# LOCUSTFILE - PRUEBA DE CARGA
# (autenticación + consultas + creación controlada de audiencias)
# =====================================================
#
# Contiene DOS cosas independientes:
#
# 1) La clase UsuarioAgendaDiaria (HttpUser): el escenario de carga
#    en sí, ejecutado por "locust -f locustfile.py". Cada usuario
#    virtual inicia sesión y luego repite, al azar, alguna de estas
#    tareas:
#      - Consultar Agenda diaria     (GET, solo lectura)
#      - Consultar Agenda semanal    (GET, solo lectura)
#      - Crear audiencia - LOADTEST  (POST, repite un ciclo completo
#        de creación + verificación + "Dejar sin efecto" +
#        verificación, hasta CICLOS_POR_USUARIO veces por usuario
#        virtual -no una sola vez-, siempre con la MISMA causa
#        LOADTEST asignada de forma determinista a ese usuario en
#        on_start(). Cada pick de esta tarea por parte de Locust
#        ejecuta UN ciclo; el propio wait_time entre tareas de Locust
#        -sin ningún bucle manual ni gevent.sleep()- es lo que separa
#        un ciclo del siguiente. Al llegar a CICLOS_POR_USUARIO, la
#        tarea queda como no-operación para el resto de la corrida de
#        ese usuario, sin afectar a Agenda diaria/semanal)
#
# 2) La función limpiar_audiencias_loadtest(): un script de limpieza
#    SEPARADO, que NO es una tarea de Locust y que Locust nunca
#    ejecuta por sí solo. Deja sin efecto (nunca elimina físicamente)
#    las audiencias que "Crear audiencia - LOADTEST" fue registrando
#    en un archivo de texto durante la corrida. Solo se ejecuta
#    invocando este archivo directamente como script de Python -ver
#    su docstring más abajo para el comando exacto-, nunca con el
#    comando "locust".
#
# URLs verificadas en el proyecto (no inventadas):
#   - Login:               "/usuarios/login/"        (usuarios/urls.py,
#                           name="login"; LOGIN_URL en config/settings.py)
#   - Agenda diaria:        "/audiencias/agenda/"     (audiencias/urls.py,
#                           name="agenda_diaria")
#   - Agenda semanal:       "/audiencias/agenda-semanal/"
#                           (audiencias/urls.py, name="agenda_semanal")
#   - Nueva audiencia:      "/audiencias/nueva/"      (audiencias/urls.py,
#                           name="registrar_audiencia"; vista
#                           audiencias.views.registrar_audiencia)
#   - Propuestas de fecha:  "/audiencias/proponer/"   (audiencias/urls.py,
#                           name="proponer_fechas_audiencia"; vista
#                           audiencias.views.proponer_fechas_audiencia)
#   - Dejar sin efecto:     "/audiencias/dejar-sin-efecto/"
#                           (audiencias/urls.py, name="dejar_sin_efecto_audiencia";
#                           vista audiencias.views.dejar_sin_efecto_audiencia,
#                           usada por crear_audiencia_loadtest() -ver más
#                           abajo- y también por limpiar_audiencias_loadtest()
#                           como red de seguridad ante audiencias que
#                           hubieran quedado PROGRAMADA por algún fallo)
#
# Campos reales verificados en audiencias/forms.py (AudienciaForm) y
# templates/audiencias/formulario.html (mismos <input>/<select> que
# usa un navegador real):
#   - competencia (pk de Competencia activa)
#   - rit (texto: RIT de una Causa YA EXISTENTE para esa competencia)
#   - tipoAudiencia (pk de TipoAudiencia activo)
#   - sala (pk de Sala activa)
#   - cantidadBloques (1 a 10)
#   - fecha ("AAAA-MM-DD")
#   - bloqueInicio (pk de BloqueHorario)
#   - anotacion (opcional)
# "causa" NO es un campo del formulario: la vista busca la Causa a
# partir de competencia+rit (ver _resolver_causa en audiencias/views.py).
# Por eso mismo, ESTE SCRIPT NO CREA CAUSAS -no existe ningún endpoint
# HTTP para crear una Causa individual; causas/urls.py solo ofrece
# "importar/" (importación masiva desde Excel, ver
# causas/services.py:ServicioImportacionCausas)-. Ver la sección
# "PRECONDICIÓN" más abajo.
#
# Cómo se elige una fecha/bloque VÁLIDOS (respetando las reglas de
# agendamiento reales, sin reimplementarlas aquí): se usa el mismo
# mecanismo que ya usa la interfaz ("Solicitar propuestas"), POST a
# proponer_fechas_audiencia, que internamente ejecuta
# GeneradorPropuestaFecha (audiencias/services.py) -evalúa
# DiaAtencion, DiaNoDisponible, ReglaAgendamiento (plazo legal) y
# disponibilidad real de bloques- y devuelve hasta 3 propuestas ya
# validadas. Este script toma la primera y la usa tal cual, mediante
# los mismos dos atributos que el botón "Usar esta propuesta" ya
# expone en el HTML real (data-fecha/data-bloque, ver
# templates/audiencias/formulario.html).
#
# Qué responde el servidor cuando la audiencia se guarda:
# registrar_audiencia redirige (302) a sí misma y deja un mensaje
# vía el framework de mensajes de Django: "«Audiencia RIT <rit> -
# <fecha> <hora>» registrada correctamente." (ver
# audiencias/views.py). Ese mensaje se renderiza en la página
# siguiente (templates/base_dashboard.html, bloque "{% if messages
# %}"), así que basta con seguir la redirección -el propio cliente
# HTTP de Locust lo hace automáticamente- y buscar ese texto.
#
# Cómo se identifica después una audiencia creada por esta prueba:
# por el RIT de su Causa asociada (Audiencia no tiene "rit" propio:
# usa audiencia.causa.rit, ver audiencias/models.py). Todo RIT usado
# por esta prueba empieza con el prefijo LOCUST_CAUSA_RIT_PREFIJO
# ("LOADTEST-" por defecto), dentro del pool de RENDIMIENTO
# (LOADTEST-101..LOADTEST-200, ver "PRECONDICIÓN OBLIGATORIA" y
# "ASIGNACIÓN DE CAUSAS" más abajo).
#
# Cómo se obtiene el ID REAL (pk) de la audiencia recién creada: NI
# registrar_audiencia NI su mensaje de éxito exponen ese ID en
# ninguna parte de la respuesta. Se obtiene de la MISMA forma que ya
# usa la interfaz real: consultando la Agenda diaria (GET
# agenda_diaria?sala=...&fecha=...) y leyendo el atributo
# data-audiencia-id del botón "Dejar sin efecto" de esa fila -mismo
# botón, con los mismos data-* (data-audiencia-id, data-rit,
# data-caratula), que ve un funcionario en pantalla, ver
# templates/audiencias/agenda.html-. Ese botón solo se renderiza para
# audiencias PROGRAMADA, así que encontrarlo confirma a la vez el ID
# y que la audiencia quedó correctamente programada.
#
# Endpoint real de "Dejar sin efecto" (verificado, no inventado):
#   - URL: "/audiencias/dejar-sin-efecto/" (audiencias/urls.py,
#     name="dejar_sin_efecto_audiencia")
#   - Método: POST (con @require_POST, ver audiencias/views.py)
#   - Parámetros: "audiencia_id" (el pk real, obtenido como se explicó
#     arriba), "motivo_seleccionado" (uno de los valores reales de
#     MotivoBaja -audiencias/forms.py-: SUSPENSION, REPROGRAMACION,
#     ERROR_AGENDAMIENTO, SOLICITUD_TRIBUNAL, OTRO; esta prueba usa
#     "OTRO" + "motivo_otro" con texto identificable), y
#     "csrfmiddlewaretoken".
#   - Respuesta de éxito: redirige (302) a agenda_diaria y deja el
#     mensaje "Audiencia dejada sin efecto correctamente." (idéntico
#     mecanismo de mensajes que "registrada correctamente.", ver más
#     arriba).
#   - Estado resultante: EstadoAudiencia.ELIMINADA ("Eliminada", baja
#     lógica -nunca eliminación física, ver ServicioBajaAudiencia en
#     audiencias/services.py y Audiencia.estado en
#     audiencias/models.py-). Se verifica leyendo el badge de "Estado"
#     de esa misma fila en una nueva consulta a la Agenda diaria (ver
#     _extraer_estado_por_rit más abajo).
#
# DIAGNÓSTICO cuando una creación NO se confirma ("registrada
# correctamente" no aparece en la respuesta): esto puede deberse a un
# error de validación bloqueante (ValidadorAgendamiento, reportado vía
# el framework de mensajes de Django, MESSAGE_TAGS mapea ERROR ->
# "danger" en config/settings.py) o a que existan advertencias de
# negocio sin confirmar (ServicioCreacionAudiencia devuelve
# requiereConfirmacion=True y NO guarda la audiencia; el template
# muestra entonces la tarjeta "Advertencias de programación" en vez
# del mensaje de éxito, ver templates/audiencias/formulario.html). En
# ambos casos el servidor responde HTTP 200 igual -por eso el criterio
# de éxito/fallo de este script sigue basándose únicamente en el
# contenido de la respuesta, nunca en el status_code-. Ver
# _extraer_diagnostico_formulario/_formatear_diagnostico_creacion más
# abajo: extraen solo esos fragmentos puntuales (mensajes, errores de
# formulario, advertencias) y los registran -por consola y dentro del
# propio response.failure() de Locust- únicamente cuando la creación
# falla, sin incluir nunca el HTML completo ni datos sensibles
# (csrfmiddlewaretoken, cookies, credenciales).
#
# CONFIRMACIÓN AUTOMÁTICA DE ADVERTENCIAS: cuando la creación pide
# confirmar (requiereConfirmacion=True, ver arriba) -por ejemplo, ante
# la advertencia real "Ya existe una audiencia programada en la sala y
# horario seleccionados..." de
# ValidadorAgendamiento.validarConflicto()-, este script NO lo trata
# como fallo: registra la advertencia como diagnóstico
# (_registrar_advertencia_confirmacion) y reenvía la MISMA solicitud
# con "confirmar_advertencias": "1" -exactamente el campo/valor real
# que envía el botón "Confirmar programación" de
# templates/audiencias/formulario.html (ver "Audiencia - confirmación"
# en crear_audiencia_loadtest más abajo)-, sin inventar ningún campo ni
# endpoint. Solo si esa confirmación TAMPOCO logra registrar la
# audiencia se marca fallo.
#
# MÉTRICAS: una advertencia NUNCA se cuenta como creación exitosa hasta
# que una confirmación real la registra. Para que esto sea medible en
# Locust -no solo una decisión interna del código-, cada resultado de
# negocio queda en su PROPIA fila de Statistics/CSV (ver
# _registrar_resultado_categoria más abajo: usa
# self.environment.events.request.fire(), el mismo evento público que
# Locust ya usa internamente para reportar cualquier solicitud, sin
# inventar ninguna API nueva):
#   1) Intentos de creación       -> fila "Audiencia - intento creación"
#      (su cantidad total de solicitudes ES la métrica).
#   2) Creaciones directas éxito  -> fila "Audiencia - creación directa"
#      (solo cuando NO hubo advertencia).
#   3) Advertencias detectadas    -> fila "Audiencia - advertencia"
#      (registrada como condición de negocio, nunca como error técnico).
#   4) Confirmaciones intentadas  -> fila "Audiencia - confirmación"
#      (su cantidad total de solicitudes ES la métrica).
#   5) Confirmaciones exitosas    -> éxitos de esa misma fila
#      "Audiencia - confirmación" (Locust ya separa éxito/fallo por
#      fila de forma nativa).
#   6) Confirmaciones fallidas    -> fallos de esa misma fila
#      "Audiencia - confirmación".
#   7) Errores reales de creación -> fila "Audiencia - error real de
#      creación" (y también el fallo nativo de "Audiencia - intento
#      creación" para ese mismo caso).
# El total de "creaciones exitosas" (directas + vía confirmación) es,
# entonces, (2) + (5): no se crea una fila aparte para esa suma, ya que
# se obtiene sumando dos filas ya existentes.
#
# =====================================================
# PRECONDICIÓN OBLIGATORIA (fuera de este archivo)
# =====================================================
# Como este script NO crea Causas (no existe esa API), deben existir
# de antemano en la base de datos, creadas por la vía normal ya
# existente en el sistema (Causas -> Importar desde Excel), NUNCA por
# este script. Ningún dato de esas Causas debe ser real (RUC/carátula
# también deben ser claramente ficticios).
#
# DOS GRUPOS DE CAUSAS LOADTEST, con propósitos distintos y
# DELIBERADAMENTE separados -este archivo, por ahora, solo usa el
# segundo grupo-:
#
#   - LOADTEST-001..LOADTEST-010 (10 causas, competencia Garantía):
#     RESERVADAS para una futura prueba específica de CONFLICTOS
#     (varios usuarios compitiendo a propósito por la misma causa/
#     sala/horario). Esta clase (UsuarioAgendaDiaria) NO las usa.
#
#   - LOADTEST-101..LOADTEST-200 (100 causas, ya importadas):
#     usadas por ESTA prueba de RENDIMIENTO, con una causa distinta
#     y exclusiva por usuario virtual (ver "ASIGNACIÓN DE CAUSAS" más
#     abajo) -precisamente para NO reintroducir la contención
#     artificial que producía el reparto anterior (con solo 10
#     causas) al superar 10 usuarios concurrentes-. Distribuidas por
#     competencia -verificado por lectura, no inventado- en 3 rangos
#     consecutivos dentro del mismo prefijo:
#       LOADTEST-101..134 (34) -> Garantía (pk=1, día de atención: MIERCOLES)
#       LOADTEST-135..167 (33) -> Familia  (pk=2, días de atención: MARTES, JUEVES)
#       LOADTEST-168..200 (33) -> Laboral  (pk=4, días de atención: JUEVES, VIERNES)
#     IMPORTANTE, detectado por lectura al momento de escribir esta
#     prueba: en la base de datos actual falta la causa LOADTEST-200
#     (quedaron 99 de las 100 esperadas: 34 Garantía + 33 Familia +
#     32 Laboral) -no corregido aquí, ver la sección "ASIGNACIÓN DE
#     CAUSAS": el usuario virtual que reciba justo LOADTEST-200
#     fallará en la creación ("causa no encontrada") hasta que se
#     re-importe esa fila faltante-.
#
# ASIGNACIÓN DE CAUSAS (determinista, sin reutilización, sin
# comodín): cada usuario virtual recibe, en on_start(), una causa
# LOADTEST-101..200 distinta y exclusiva (índice 0 -> LOADTEST-101,
# índice 1 -> LOADTEST-102, ..., índice 99 -> LOADTEST-200), y con
# ella la competencia que le corresponde según el rango de arriba
# (ya NO una única COMPETENCIA_ID fija para todos: las 100 causas
# abarcan 3 competencias distintas, así que la competencia enviada en
# cada creación también depende del usuario). Ver
# _rit_loadtest_para_indice/_competencia_id_para_numero_causa más
# abajo. Si se spawnearan más de 100 usuarios virtuales, el script NO
# reutiliza silenciosamente una causa ya asignada: on_start() lanza un
# RuntimeError explícito, con un mensaje claro indicando cuántas
# causas exclusivas hay disponibles -ver el propio mensaje del error-,
# en vez de introducir contención artificial sin avisar.
#
# La cantidad de usuarios concurrentes y el spawn rate NO se
# configuran aquí: se definen desde la interfaz web de Locust (o los
# parámetros --users/--spawn-rate) al iniciar la prueba.

import html as html_utils
import itertools
import json
import os
import re
import threading
from datetime import datetime

from locust import HttpUser, task, between

# =====================================================
# URLS DEL PROYECTO (verificadas, no inventadas)
# =====================================================

URL_LOGIN = "/usuarios/login/"
URL_AGENDA_DIARIA = "/audiencias/agenda/"
URL_AGENDA_SEMANAL = "/audiencias/agenda-semanal/"
URL_NUEVA_AUDIENCIA = "/audiencias/nueva/"
URL_PROPONER_FECHAS = "/audiencias/proponer/"
URL_DEJAR_SIN_EFECTO = "/audiencias/dejar-sin-efecto/"

# =====================================================
# CREDENCIALES DE PRUEBA
# =====================================================
#
# Se leen desde variables de entorno (LOCUST_USUARIO / LOCUST_CLAVE)
# en vez de escribirse directamente en el código: así el archivo no
# queda con una credencial real "quemada" y puede compartirse o
# versionarse sin exponer nada sensible. Los valores por defecto son
# solo un placeholder para dejar explícito qué se espera -deben
# reemplazarse exportando las variables de entorno antes de ejecutar
# Locust, apuntando a un usuario de prueba YA EXISTENTE en el sistema
# (este archivo no crea usuarios).

USUARIO_PRUEBA = os.environ.get("LOCUST_USUARIO", "usuario_prueba")
CLAVE_PRUEBA = os.environ.get("LOCUST_CLAVE", "clave_prueba")

# =====================================================
# CONFIGURACIÓN DE LA CREACIÓN DE AUDIENCIAS - LOADTEST
# =====================================================
#
# TIPO_AUDIENCIA_ID y SALA_ID deben ser de catálogos REALES y ya
# existentes (TipoAudiencia activo, Sala activa): este script no los
# inventa ni los crea, los recibe por variable de entorno porque
# cambian de una base de datos a otra. "competencia" YA NO es un
# valor único fijo aquí -ver "COMPETENCIA POR CAUSA" más abajo-: las
# 100 causas de esta prueba abarcan 3 competencias distintas, así que
# la competencia a enviar depende de qué causa le tocó a cada usuario.
#
# Los valores por defecto de abajo NO son inventados: se verificaron
# mediante una consulta de solo lectura (TipoAudiencia.objects.filter(...),
# Sala.objects.filter(...), sin ninguna escritura):
#   - TipoAudiencia activos encontrados: 6=Audiencia preparatoria,
#     7=Audiencia de juicio, 8=Audiencia de revisión -se usa 6-.
#   - Sala activa encontrada: 1=Sala 1 (única sala activa).
# Si la base de datos cambiara, hay que actualizar estas variables de
# entorno (no hace falta tocar este archivo).
#
# Ejemplo para sobrescribirlos (PowerShell), además de
# LOCUST_USUARIO/LOCUST_CLAVE:
#   $env:LOCUST_TIPO_AUDIENCIA_ID = "6"
#   $env:LOCUST_SALA_ID           = "1"
#   locust -f locustfile.py

TIPO_AUDIENCIA_ID = os.environ.get("LOCUST_TIPO_AUDIENCIA_ID", "6")
SALA_ID = os.environ.get("LOCUST_SALA_ID", "1")
CANTIDAD_BLOQUES = os.environ.get("LOCUST_CANTIDAD_BLOQUES", "1")

# Cantidad de veces que CADA usuario virtual repite el ciclo completo
# "crear audiencia -> verificar en agenda -> dejar sin efecto ->
# verificar estado" (ver crear_audiencia_loadtest más abajo). Se deja
# como variable de entorno -no hardcodeada dentro de la lógica- para
# poder ajustarla sin tocar este archivo, pero el valor pedido es 5:
# con 50 usuarios concurrentes, esto produce aproximadamente
# 50 x 5 = 250 ciclos completos. La cantidad de usuarios y el spawn
# rate siguen sin configurarse aquí -eso lo define la interfaz de
# Locust, como siempre-.
CICLOS_POR_USUARIO = int(os.environ.get("LOCUST_CICLOS_POR_USUARIO", "5"))

# -------------------------------------------------
# Pool de causas EXCLUSIVAS para esta prueba de rendimiento (ver
# "PRECONDICIÓN OBLIGATORIA" más arriba): LOADTEST-101..LOADTEST-200,
# 100 causas, una por usuario virtual, sin reutilización. Distinto
# del prefijo/pool de LOADTEST-001..010 -esas quedan reservadas para
# la futura prueba de conflictos, este archivo no las toca-.
PREFIJO_RIT_LOADTEST = os.environ.get("LOCUST_CAUSA_RIT_PREFIJO", "LOADTEST-")
CAUSA_LOADTEST_NUMERO_INICIAL = int(os.environ.get("LOCUST_CAUSA_RIT_INICIO", "101"))
CAUSA_LOADTEST_CANTIDAD = int(os.environ.get("LOCUST_CAUSA_RIT_CANTIDAD", "100"))

# -------------------------------------------------
# COMPETENCIA POR CAUSA: a diferencia del pool anterior (10 causas,
# todas de Garantía), este pool de 100 causas abarca 3 competencias
# distintas -Causa.objects.filter(competencia=..., rit=...) exige que
# AMBOS coincidan, así que enviar la competencia equivocada haría que
# el servidor no encuentre la causa-. Verificado por lectura, no
# inventado: cada rango de número de causa corresponde exactamente a
# como se importaron (ver el Excel generado para esta prueba).
# Sobrescribibles por variable de entorno si la base de datos cambia,
# igual que TIPO_AUDIENCIA_ID/SALA_ID de arriba.
_RANGOS_COMPETENCIA_RENDIMIENTO = [
    (101, 134, os.environ.get("LOCUST_COMPETENCIA_GARANTIA_ID", "1")),   # Garantía
    (135, 167, os.environ.get("LOCUST_COMPETENCIA_FAMILIA_ID", "2")),    # Familia
    (168, 200, os.environ.get("LOCUST_COMPETENCIA_LABORAL_ID", "4")),    # Laboral
]


def _competencia_id_para_numero_causa(numero_causa):
    """
    Devuelve el pk de Competencia que corresponde al número de causa
    LOADTEST (101..200) dado, según _RANGOS_COMPETENCIA_RENDIMIENTO.

    Lanza RuntimeError si el número no cae en ningún rango conocido
    -no se adivina ninguna competencia-: no debería ocurrir mientras
    _rit_loadtest_para_indice (más abajo) siga acotado a
    CAUSA_LOADTEST_NUMERO_INICIAL..+CAUSA_LOADTEST_CANTIDAD-1, pero se
    deja como resguardo explícito ante una configuración manual
    inconsistente (por ejemplo, LOCUST_CAUSA_RIT_INICIO/CANTIDAD
    ajustados sin actualizar los rangos de competencia).
    """
    for inicio, fin, competencia_id in _RANGOS_COMPETENCIA_RENDIMIENTO:
        if inicio <= numero_causa <= fin:
            return competencia_id
    raise RuntimeError(
        f"No hay ninguna competencia configurada para el número de "
        f"causa LOADTEST-{numero_causa:03d} (fuera de los rangos "
        f"conocidos: {_RANGOS_COMPETENCIA_RENDIMIENTO})."
    )

# Archivo donde "Crear audiencia - LOADTEST" registra cada audiencia
# creada (RIT, sala, fecha), para que limpiar_audiencias_loadtest()
# sepa después qué buscar y dejar sin efecto. Es un archivo de datos
# generado en tiempo de ejecución (no código fuente del proyecto):
# se crea solo/si se llega a ejecutar la prueba de carga real, nunca
# por el solo hecho de tener este locustfile.py.
ARCHIVO_REGISTRO_LOADTEST = os.environ.get(
    "LOCUST_ARCHIVO_REGISTRO", "loadtest_audiencias_creadas.jsonl"
)

# -------------------------------------------------
# Contador compartido para asignar, UNA SOLA VEZ por usuario virtual
# (en on_start, nunca en cada ciclo de una tarea), un índice
# secuencial 0, 1, 2, ... en el mismo orden en que cada usuario iba
# iniciando sesión -que con un ramp-up ordenado es, además, su orden
# real de aparición-. Ese índice determina, 1 a 1, qué causa LOADTEST
# usará: usuario virtual con índice 0 -> LOADTEST-101, índice 1 ->
# LOADTEST-102, ..., índice 49 -> LOADTEST-150 (50 usuarios), ...,
# índice 99 -> LOADTEST-200 (100 usuarios). Protegido con un Lock:
# aunque Locust corre sobre gevent (cooperativo, no hay preemption a
# mitad de una operación simple), este candado deja la intención
# explícita y evita cualquier duda al respecto.
#
# LIMITACIÓN CONOCIDA: este contador solo coordina usuarios virtuales
# dentro de UN MISMO proceso de Locust. En una corrida distribuida
# (--master/--worker, varios procesos) cada worker tendría su propio
# contador independiente, con riesgo de que dos workers asignen el
# mismo índice -y por lo tanto la misma causa- a usuarios distintos.
# Para esta prueba (hasta 100 usuarios, un solo proceso) no es un
# problema, pero queda documentado para no asumirlo sin más si el
# escenario cambiara a una corrida distribuida.
# -------------------------------------------------

_bloqueo_indice_usuario = threading.Lock()
_contador_usuarios = itertools.count(0)

# Protege tanto la lista en memoria como la escritura al archivo de
# registro, por la misma razón que _bloqueo_indice_usuario.
_bloqueo_registro = threading.Lock()
_audiencias_loadtest_creadas = []


def _siguiente_indice_usuario():
    """
    Entrega, de forma atómica, el siguiente índice de usuario virtual
    (0, 1, 2, ...). Se llama UNA SOLA VEZ por usuario virtual, en
    on_start(): no rota entre tareas ni entre ciclos, así que dos
    usuarios nunca pueden recibir el mismo índice ni, por lo tanto,
    la misma causa LOADTEST (ver _rit_loadtest_para_indice más abajo).
    """
    with _bloqueo_indice_usuario:
        return next(_contador_usuarios)


def _rit_loadtest_para_indice(indice_usuario):
    """
    Traduce el índice de un usuario virtual (0-based) al RIT LOADTEST
    EXCLUSIVO que le corresponde, 1 a 1: índice 0 -> "LOADTEST-101",
    índice 1 -> "LOADTEST-102", ..., índice 49 -> "LOADTEST-150" (50
    usuarios), ..., índice 99 -> "LOADTEST-200" (100 usuarios) -con
    CAUSA_LOADTEST_NUMERO_INICIAL=101/CAUSA_LOADTEST_CANTIDAD=100, los
    valores por defecto-.

    A DIFERENCIA de la versión anterior de este script (que hacía
    módulo y reutilizaba causas silenciosamente al superar 10
    usuarios): esta versión NUNCA reutiliza una causa entre usuarios
    concurrentes. Si se spawnea un usuario virtual cuyo índice ya no
    tiene una causa exclusiva disponible (más de CAUSA_LOADTEST_CANTIDAD
    usuarios, 100 por defecto), lanza un RuntimeError explícito -no
    envuelto en un try/except en ningún lugar de este archivo, así que
    Locust lo reporta como un fallo real de ese usuario (visible en su
    consola/log), en vez de introducir contención artificial sin
    avisar-.
    """
    if indice_usuario >= CAUSA_LOADTEST_CANTIDAD:
        numero_maximo = CAUSA_LOADTEST_NUMERO_INICIAL + CAUSA_LOADTEST_CANTIDAD - 1
        raise RuntimeError(
            f"No hay suficientes causas LOADTEST exclusivas para el "
            f"usuario virtual número {indice_usuario + 1} (índice "
            f"{indice_usuario}): solo hay {CAUSA_LOADTEST_CANTIDAD} "
            f"causas reservadas para esta prueba de rendimiento "
            f"(LOADTEST-{CAUSA_LOADTEST_NUMERO_INICIAL:03d}..LOADTEST-"
            f"{numero_maximo:03d}). Reduce la cantidad de usuarios a "
            f"{CAUSA_LOADTEST_CANTIDAD} o menos, o importa más causas "
            f"LOADTEST exclusivas antes de escalar esta prueba -este "
            f"script nunca reutiliza automáticamente una causa entre "
            f"usuarios concurrentes, para no introducir contención "
            f"artificial silenciosa-."
        )

    numero = CAUSA_LOADTEST_NUMERO_INICIAL + indice_usuario
    return f"{PREFIJO_RIT_LOADTEST}{numero:03d}"


def _registrar_audiencia_creada(rit, sala_id, fecha_iso):
    """
    Guarda en memoria y en ARCHIVO_REGISTRO_LOADTEST los datos
    mínimos para poder ubicar después esta audiencia y dejarla sin
    efecto (ver limpiar_audiencias_loadtest()). Un problema al
    escribir el archivo NO se trata como fallo de la solicitud HTTP
    -la audiencia ya quedó guardada en el sistema de todas formas-,
    solo se avisa por consola para que quede constancia.
    """
    registro = {
        "rit": rit,
        "sala_id": sala_id,
        "fecha": fecha_iso,
        "creadaEn": datetime.now().isoformat(timespec="seconds"),
    }

    with _bloqueo_registro:
        _audiencias_loadtest_creadas.append(registro)
        try:
            with open(ARCHIVO_REGISTRO_LOADTEST, "a", encoding="utf-8") as archivo:
                archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
        except OSError as error:
            print(
                f"[locustfile] No se pudo registrar en "
                f"{ARCHIVO_REGISTRO_LOADTEST} la audiencia {rit}: {error}"
            )


# Extrae data-fecha="AAAA-MM-DD" y data-bloque="<pk>" del botón "Usar
# esta propuesta" (ver templates/audiencias/formulario.html), en ese
# mismo orden de atributos -tal como los renderiza el template real,
# no un formato inventado-. proponer_fechas_audiencia devuelve las
# propuestas ya ordenadas cronológicamente (dentro_de_plazo[:3], ver
# GeneradorPropuestaFecha.generar() en audiencias/services.py) y el
# template las recorre en ese mismo orden ("Propuesta 1" primero), así
# que re.search() -que devuelve la PRIMERA coincidencia encontrada en
# el texto, no todas- ya corresponde exactamente a tomar
# EXCLUSIVAMENTE la primera propuesta, sin tener que filtrar nada
# aparte.
_PATRON_PROPUESTA = re.compile(
    r'data-fecha="([\d-]+)"\s+data-bloque="(\d+)"'
)


def _patron_boton_dejar_sin_efecto(rit):
    """
    Compila, para un RIT concreto, el patrón que localiza -dentro de
    la Agenda diaria real (templates/audiencias/agenda.html)- el
    botón "Dejar sin efecto" de la fila de ESE RIT, y captura el ID
    real (pk) de esa Audiencia desde su atributo data-audiencia-id.

    Ese botón SOLO se renderiza para audiencias en estado PROGRAMADA
    (ver el "{% if audiencia.estado == 'PROGRAMADA' %}" que lo
    envuelve en el template real): encontrarlo es, en sí mismo, la
    confirmación de que la audiencia quedó correctamente programada
    -no hace falta ninguna verificación de estado aparte para eso-.

    data-audiencia-id y data-rit son atributos del MISMO botón, en
    ese orden fijo (id antes que rit), tal como los renderiza el
    template real -no un formato inventado-, por lo que este patrón
    identifica sin ambigüedad la fila de este RIT específico, aunque
    la tabla tenga varias audiencias de otros usuarios/RIT en la
    misma sala y fecha.
    """
    return re.compile(
        r'data-audiencia-id="(\d+)"\s+data-rit="' + re.escape(rit) + r'"'
    )


# =====================================================
# DIAGNÓSTICO: qué respondió realmente el servidor cuando una
# creación de audiencia NO se confirma ("registrada correctamente"
# no aparece en la respuesta). NO cambia el criterio de éxito/fallo
# -eso lo sigue decidiendo únicamente ese mismo texto, nunca el
# status_code por sí solo, ver el POST a registrar_audiencia más
# abajo-: esta sección solo ENRIQUECE el mensaje de fallo ya
# detectado, para poder ver, sin adivinar, si el servidor devolvió
# un error de validación, una advertencia que pide confirmación, u
# otra cosa.
# =====================================================

# Redacta cualquier valor de csrfmiddlewaretoken que pudiera aparecer
# en un fragmento de HTML, ANTES de extraer o registrar nada de esa
# respuesta -nunca se registran tokens CSRF, cookies ni credenciales,
# ver "IMPORTANTE SOBRE SEGURIDAD"-. Los patrones de extracción de
# abajo ya evitan por diseño esa clase de contenido (solo capturan el
# TEXTO de mensajes/errores, con las etiquetas HTML ya recortadas),
# pero esta redacción se aplica primero, como resguardo adicional.
_PATRON_CSRF_INPUT = re.compile(
    r'(name="csrfmiddlewaretoken"\s+value=")[^"]*(")'
)


def _redactar_html_sensible(texto):
    return _PATRON_CSRF_INPUT.sub(r'\1[REDACTADO]\2', texto)


# Mensajes del framework de mensajes de Django (éxito/error/
# advertencia/info), tal como los renderiza
# templates/base_dashboard.html: <div class="alert alert-{{ tags }}
# ...">{{ message }}<button ...>. "danger" es el tag real para
# ERROR en este proyecto (MESSAGE_TAGS en config/settings.py mapea
# ERROR -> "danger"), no el "error" por defecto de Django.
_PATRON_MENSAJE_DJANGO = re.compile(
    r'<div class="alert alert-(\w+)[^"]*"[^>]*>\s*(.*?)\s*<button',
    re.DOTALL,
)

# Errores de validación en línea de un campo del formulario, tal como
# los renderiza {{ form.<campo>.errors }} con el ErrorList por
# defecto de Django (sin personalizar en este proyecto).
_PATRON_ERRORLIST = re.compile(r'<ul class="errorlist">(.*?)</ul>', re.DOTALL)
_PATRON_LI = re.compile(r'<li>(.*?)</li>', re.DOTALL)

# Bloque completo de "Advertencias de programación" (ver
# templates/audiencias/formulario.html): solo se renderiza cuando
# ServicioCreacionAudiencia devuelve requiereConfirmacion=True -hay
# advertencias de negocio, pero ningún error bloqueante- y la
# audiencia, en ese caso, NO se guarda todavía.
_PATRON_ADVERTENCIAS_CARD = re.compile(
    r'Advertencias de programaci\wn</h6>.*?<ul>(.*?)</ul>', re.DOTALL
)


def _texto_sin_etiquetas(fragmento_html):
    """
    Quita cualquier etiqueta HTML restante de un fragmento ya
    extraído (por ejemplo, el <span>/<br> que pudiera venir dentro
    de un mensaje) y decodifica entidades HTML (&amp;, &#39;, etc.)
    para que el texto quede legible en el diagnóstico.
    """
    return html_utils.unescape(re.sub(r'<[^>]+>', '', fragmento_html)).strip()


def _extraer_diagnostico_formulario(texto_respuesta):
    """
    Extrae, de una respuesta de registrar_audiencia
    (templates/audiencias/formulario.html), ÚNICAMENTE el texto
    relevante para diagnosticar por qué una creación no se confirmó:

    - "mensajes": los mensajes del framework de mensajes de Django
      (éxito/error/advertencia), con su tipo real (ver
      _PATRON_MENSAJE_DJANGO).
    - "errores_formulario": errores de validación en línea de campos
      del formulario (ver _PATRON_ERRORLIST).
    - "requiere_confirmacion": True si el servidor mostró el bloque
      "Advertencias de programación" -es decir,
      ServicioCreacionAudiencia devolvió requiereConfirmacion=True y
      todavía NO guardó la audiencia, a la espera de que alguien
      confirme-.
    - "advertencias": el texto de cada advertencia de ese bloque,
      cuando corresponde.

    Deliberadamente NO devuelve el HTML completo de la respuesta
    (puede superar varios KB e incluye el <form> entero): solo estos
    fragmentos puntuales, siempre sobre una copia ya redactada por
    _redactar_html_sensible().
    """
    texto_respuesta = _redactar_html_sensible(texto_respuesta)

    mensajes = [
        {"tipo": tipo, "texto": _texto_sin_etiquetas(texto)}
        for tipo, texto in _PATRON_MENSAJE_DJANGO.findall(texto_respuesta)
    ]

    errores_formulario = [
        _texto_sin_etiquetas(item)
        for bloque in _PATRON_ERRORLIST.findall(texto_respuesta)
        for item in _PATRON_LI.findall(bloque)
    ]

    coincidencia_advertencias = _PATRON_ADVERTENCIAS_CARD.search(texto_respuesta)
    requiere_confirmacion = coincidencia_advertencias is not None
    advertencias = (
        [
            _texto_sin_etiquetas(item)
            for item in _PATRON_LI.findall(coincidencia_advertencias.group(1))
        ]
        if coincidencia_advertencias
        else []
    )

    return {
        "mensajes": mensajes,
        "errores_formulario": errores_formulario,
        "requiere_confirmacion": requiere_confirmacion,
        "advertencias": advertencias,
    }


# Texto REAL de la advertencia de conflicto de horario -verificado en
# audiencias/services.py, ValidadorAgendamiento.validarConflicto()-,
# usado solo para distinguir en el diagnóstico este caso específico
# de cualquier otra advertencia de negocio; NO condiciona si se
# confirma o no (ver más abajo: se confirma ante CUALQUIER advertencia
# que pida confirmación, con el mismo mecanismo real, no solo ante
# esta).
_TEXTO_ADVERTENCIA_CONFLICTO_HORARIO = (
    "Ya existe una audiencia programada en la sala y horario seleccionados"
)


def _registrar_advertencia_confirmacion(rit, numero_ciclo, diagnostico):
    """
    Registra (por consola) que el primer intento de creación pidió
    confirmar advertencias -esto NO es un fallo: es el comportamiento
    real y esperado de ServicioCreacionAudiencia cuando hay
    advertencias de negocio sin confirmar, ver
    "requireConfirmacion"/"advertencias" en
    audiencias/services.py:ServicioCreacionAudiencia.crear()-, antes
    de reenviar la confirmación real (confirmar_advertencias=1, ver
    más abajo en crear_audiencia_loadtest).

    Si entre las advertencias está el conflicto de horario real
    (texto verificado, ver _TEXTO_ADVERTENCIA_CONFLICTO_HORARIO
    arriba), usa el formato específico pedido
    ("[ADVERTENCIA DE CONFLICTO]"). Para cualquier OTRA advertencia de
    negocio (por ejemplo, de plazo legal -ver
    ValidadorAgendamiento.validarPlazoLegal()-), usa un formato
    genérico equivalente: el mecanismo de confirmación
    (confirmar_advertencias=1) es exactamente el mismo para cualquier
    advertencia, no está condicionado a esta en particular -por eso
    esta prueba confirma ante requiere_confirmacion=True en general,
    no solo ante este texto exacto-.
    """
    es_conflicto_horario = any(
        _TEXTO_ADVERTENCIA_CONFLICTO_HORARIO in advertencia
        for advertencia in diagnostico["advertencias"]
    )

    lineas = (
        ["[ADVERTENCIA DE CONFLICTO]"]
        if es_conflicto_horario
        else ["[ADVERTENCIA DE PROGRAMACIÓN]"]
    )
    lineas.append(f"RIT={rit}")
    lineas.append(f"ciclo={numero_ciclo}/{CICLOS_POR_USUARIO}")

    if es_conflicto_horario:
        lineas.append("La primera fecha sugerida tenía una audiencia existente.")
        lineas.append("Se enviará confirmación de programación.")
    else:
        lineas.append(
            "El servidor pidió confirmar advertencias de programación "
            "(no es el conflicto de horario esperado)."
        )
        lineas.append("Se enviará confirmación de programación de todas formas.")

    for advertencia in diagnostico["advertencias"]:
        lineas.append(f"advertencia: {advertencia}")

    print("\n".join(lineas))


def _registrar_resultado_categoria(usuario, nombre, exito, motivo_fallo=None):
    """
    Registra un RESULTADO DE NEGOCIO (no una solicitud HTTP nueva) como
    su propia fila en las estadísticas de Locust (Statistics/CSV),
    separada de las filas de solicitudes HTTP reales -así "creación
    directa", "advertencia" y "error real de creación" pueden contarse
    de forma independiente entre sí y del "intento" que las originó, en
    vez de quedar todas mezcladas bajo un único success()/failure() de
    una sola solicitud-.

    Usa el mecanismo público y documentado de Locust para esto -no se
    inventa ninguna API-: locust.event.Events.request, el mismo evento
    que Locust dispara internamente por cada solicitud real (ver
    ResponseContextManager._report_request en el propio paquete locust
    instalado: "self._request_event.fire(**self.request_meta)"),
    disparado aquí manualmente vía self.environment.events.request.fire().
    self.environment es el atributo estándar de todo User de Locust
    (asignado en User.__init__), no algo agregado por este script.

    request_type="BIZ" (no es un verbo HTTP real) distingue a propósito,
    en la columna "Type" de Locust, estas filas de clasificación de
    negocio de las filas de solicitudes HTTP reales.

    response_time=0 y response_length=0 a propósito: esta fila no
    vuelve a medir una solicitud de red -esa medición ya ocurrió, por
    separado, en su propia fila real ("Audiencia - intento creación" o
    "Audiencia - confirmación")-; esta fila solo CUENTA cuántas veces
    ocurrió esta categoría de resultado, sin distorsionar los tiempos
    de respuesta agregados de la prueba.

    "exito" determina si esta fila queda registrada en Locust como
    éxito (una advertencia detectada, o una creación directa, NO son un
    fallo técnico: exito=True) o como fallo (un error real de creación:
    exito=False, con "motivo_fallo" como mensaje de la excepción, así
    aparece en la pestaña "Failures"/"Exceptions" de Locust igual que
    cualquier otro fallo real).
    """
    usuario.environment.events.request.fire(
        request_type="BIZ",
        name=nombre,
        response_time=0,
        response_length=0,
        response=None,
        context={},
        exception=None if exito else RuntimeError(motivo_fallo or nombre),
    )


def _formatear_diagnostico_creacion(status_code, url, rit, diagnostico):
    """
    Arma el texto legible del diagnóstico (código HTTP, URL, RIT, y
    todo lo extraído por _extraer_diagnostico_formulario), para
    imprimirlo por consola Y para incluirlo en el propio
    response.failure() de Locust -así queda visible directamente en
    la pestaña "Failures"/"Exceptions" de Locust, no solo en la
    consola-.
    """
    lineas = [
        f"[DIAGNOSTICO creacion fallida] RIT={rit} status_code={status_code} url={url}",
    ]

    if diagnostico["mensajes"]:
        for mensaje in diagnostico["mensajes"]:
            lineas.append(f"  mensaje[{mensaje['tipo']}]: {mensaje['texto']}")
    else:
        lineas.append("  mensajes del sistema: (ninguno)")

    if diagnostico["errores_formulario"]:
        for error in diagnostico["errores_formulario"]:
            lineas.append(f"  error de formulario: {error}")

    if diagnostico["requiere_confirmacion"]:
        lineas.append(
            "  requiere_confirmacion: SI (el servidor encontró "
            "advertencias de negocio y pidió 'Confirmar programación'; "
            "la audiencia NO se guardó)"
        )
        if diagnostico["advertencias"]:
            for advertencia in diagnostico["advertencias"]:
                lineas.append(f"  advertencia: {advertencia}")
    else:
        lineas.append("  requiere_confirmacion: NO")

    return "\n".join(lineas)


def _extraer_estado_por_rit(html, rit):
    """
    Ubica, dentro del HTML completo de la Agenda diaria, la fila
    (<tr>...</tr>) que contiene el RIT dado, y devuelve el texto
    mostrado en su badge de "Estado" (get_estado_display():
    "Programada" o "Eliminada", los únicos dos valores reales de
    EstadoAudiencia -ver audiencias/models.py-), o None si ese RIT no
    aparece en ninguna fila.

    Se usa DESPUÉS de "Dejar sin efecto", cuando el botón de esa fila
    ya no está presente (deja de renderizarse para audiencias que ya
    no son PROGRAMADA -ver _patron_boton_dejar_sin_efecto arriba-), por
    lo que ya no alcanza con buscar ese botón: hay que leer
    directamente el badge de Estado de la fila.

    Los lookahead negativos "(?!<tr>|</tr>)" evitan que la búsqueda
    "se escape" hacia otra fila de la tabla -sin ellos, un ".*?" no
    ligado podría cruzar el "</tr>" de una fila ajena y devolver el
    badge de OTRA audiencia distinta, si la tabla tiene varias filas
    (algo esperable en esta prueba: varios usuarios pueden coincidir
    en la misma sala/fecha)-.
    """
    patron_fila = re.compile(
        r'<tr>(?:(?!<tr>|</tr>).)*?<td>\s*'
        + re.escape(rit)
        + r'\s*</td>(?:(?!</tr>).)*?</tr>',
        re.DOTALL,
    )
    coincidencia_fila = patron_fila.search(html)
    if coincidencia_fila is None:
        return None

    coincidencia_badge = re.search(
        r'<span class="badge[^"]*">\s*([^<]+?)\s*</span>',
        coincidencia_fila.group(0),
    )
    return coincidencia_badge.group(1) if coincidencia_badge else None


class UsuarioAgendaDiaria(HttpUser):
    """
    Usuario virtual que inicia sesión y luego, al azar, consulta la
    Agenda diaria, la Agenda semanal, o registra una audiencia de
    prueba (LOADTEST).

    wait_time: simula una pausa de lectura entre una consulta y la
    siguiente (comportamiento razonable de una persona funcionaria
    revisando el sistema, no una ráfaga de solicitudes sin pausa).
    """

    wait_time = between(2, 5)

    def on_start(self):
        """
        Se ejecuta una única vez por usuario virtual, antes de que
        empiece a repetir las tareas de abajo -equivalente a que una
        persona funcionaria inicie sesión al comienzo del día-.

        Reproduce el mismo flujo que hace un navegador contra
        templates/usuarios/login.html:
          1. GET a la pantalla de login, para obtener la cookie CSRF
             que Django exige antes de aceptar el POST.
          2. POST con "username"/"password" (mismos nombres de campo
             que el <form> real) + el token CSRF obtenido.
        """
        # 1. Obtiene la cookie CSRF (Django la fija en el GET inicial
        #    a cualquier vista que renderice {% csrf_token %}).
        self.client.get(URL_LOGIN, name="Login - formulario")
        csrf_token = self.client.cookies.get("csrftoken")

        # 2. Envía las credenciales, igual que el formulario real.
        #    Se agrega el header "Referer" porque la protección CSRF
        #    de Django también lo valida en solicitudes POST.
        #
        #    catch_response=True + "with": sin esto, response.failure()
        #    lanza LocustError ("Tried to set status on a request that
        #    has not yet been made") porque Locust todavía no marcó la
        #    solicitud como "completada manualmente" -es la forma
        #    correcta de intervenir el resultado de una solicitud en
        #    vez de dejar que Locust decida solo por el status code.
        with self.client.post(
            URL_LOGIN,
            data={
                "username": USUARIO_PRUEBA,
                "password": CLAVE_PRUEBA,
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": f"{self.host}{URL_LOGIN}"},
            name="Login - envio de credenciales",
            catch_response=True,
        ) as respuesta:
            # 3. Verifica que el usuario realmente quedó autenticado:
            #    si el login fue exitoso, LOGIN_REDIRECT_URL ("/")
            #    entrega el dashboard, que solo se le muestra a un
            #    usuario con sesión iniciada e incluye el botón
            #    "Cerrar sesión" (templates/base_dashboard.html). Si
            #    las credenciales son incorrectas, Django vuelve a
            #    mostrar login.html -sin ese botón-, por lo que su
            #    ausencia es una señal confiable de que la
            #    autenticación falló.
            self.autenticado = "Cerrar sesión" in respuesta.text
            if not self.autenticado:
                respuesta.failure(
                    "No se pudo autenticar al usuario de prueba: revisar "
                    "LOCUST_USUARIO / LOCUST_CLAVE."
                )

        # -----------------------------------------------
        # Asigna, de forma determinista, única y EXCLUSIVA, la causa
        # LOADTEST-101..200 que este usuario virtual usará en
        # crear_audiencia_loadtest() -UNA SOLA VEZ por usuario, aquí en
        # on_start(), nunca en cada ciclo de la tarea-: con un ramp-up
        # ordenado, el primer usuario en iniciar sesión recibe índice 0
        # ("LOADTEST-101"), el segundo índice 1 ("LOADTEST-102"), y así
        # sucesivamente -el mapeo 1 a 1 pedido, sin que dos usuarios
        # puedan recibir la misma causa mientras haya cupo-. Si ya no
        # queda una causa exclusiva disponible (más de
        # CAUSA_LOADTEST_CANTIDAD usuarios), _rit_loadtest_para_indice
        # lanza un RuntimeError explícito en vez de reutilizar una
        # causa en silencio -este on_start() no lo atrapa a propósito,
        # así ese usuario virtual falla de forma visible en vez de
        # introducir contención artificial-.
        #
        # Junto con el RIT, se resuelve también la competencia que le
        # corresponde (ver _competencia_id_para_numero_causa): estas
        # 100 causas abarcan 3 competencias distintas (Garantía/
        # Familia/Laboral), a diferencia del pool anterior de 10
        # causas (todas de Garantía), así que ya no hay una única
        # COMPETENCIA_ID fija para todos los usuarios.
        #
        # Se asigna aunque el login haya fallado (es barato y
        # determinista); de todas formas crear_audiencia_loadtest() no
        # hará nada si self.autenticado quedó en False.
        # -----------------------------------------------
        self.indice_usuario_loadtest = _siguiente_indice_usuario()
        self.rit_loadtest = _rit_loadtest_para_indice(self.indice_usuario_loadtest)
        numero_causa = CAUSA_LOADTEST_NUMERO_INICIAL + self.indice_usuario_loadtest
        self.competencia_id_loadtest = _competencia_id_para_numero_causa(numero_causa)
        print(
            f"[locustfile] Usuario virtual índice {self.indice_usuario_loadtest} "
            f"-> causa {self.rit_loadtest} (competencia_id="
            f"{self.competencia_id_loadtest}, hasta {CICLOS_POR_USUARIO} ciclos)"
        )

        # Cuenta cuántos ciclos completos (crear -> verificar -> dejar
        # sin efecto -> verificar) ya ejecutó crear_audiencia_loadtest()
        # para este usuario virtual. Un CONTADOR controlado -no un
        # "while True"-: cada vez que Locust vuelve a elegir esa tarea
        # al azar, se ejecuta UN ciclo más y se incrementa este
        # contador; al llegar a CICLOS_POR_USUARIO, la tarea deja de
        # hacer nada en las siguientes veces que sea elegida (ver el
        # guard al inicio de crear_audiencia_loadtest), sin afectar a
        # consultar_agenda_diaria/consultar_agenda_semanal, que siguen
        # pudiendo ejecutarse con normalidad.
        self.ciclos_loadtest_completados = 0

    @task
    def consultar_agenda_diaria(self):
        """
        Mide el tiempo de respuesta y la estabilidad del servidor al
        solicitar la Agenda diaria (GET /audiencias/agenda/) bajo
        carga concurrente, ya con el usuario autenticado.

        Se realiza sin parámetros "sala"/"fecha" (equivalente a un
        primer ingreso a la pantalla, sin sala seleccionada aún), por
        lo que la vista no debería ejecutar ninguna consulta de
        audiencias -solo mide el costo base de la pantalla-.
        """
        # Si el login de on_start() falló, no tiene sentido seguir
        # consultando: la respuesta sería solo la redirección al login
        # (@login_required), no la Agenda diaria real.
        if not getattr(self, "autenticado", False):
            return

        # catch_response=True permite marcar la solicitud como
        # fallida si, pese a haber iniciado sesión en on_start(), esta
        # consulta puntual terminó devolviendo la pantalla de login
        # -por ejemplo, por expiración de sesión- en vez de la agenda.
        with self.client.get(
            URL_AGENDA_DIARIA,
            name="Agenda diaria - GET",
            catch_response=True,
        ) as respuesta:
            if "Cerrar sesión" not in respuesta.text:
                respuesta.failure(
                    "La respuesta no corresponde a un usuario "
                    "autenticado (¿la sesión expiró?)."
                )

    @task
    def consultar_agenda_semanal(self):
        """
        Mide el tiempo de respuesta y la estabilidad del servidor al
        solicitar la Agenda semanal (GET /audiencias/agenda-semanal/)
        bajo carga concurrente, ya con el usuario autenticado.

        Es una tarea independiente de consultar_agenda_diaria (Locust
        elige al azar cuál ejecutar en cada ciclo): ambas conviven sin
        reemplazarse entre sí.

        Se realiza sin parámetros "sala"/"fecha" (equivalente a un
        primer ingreso a la pantalla, sin sala seleccionada aún), por
        lo que la vista no debería ejecutar ninguna consulta de
        audiencias -solo mide el costo base de la pantalla-. Al igual
        que la Agenda diaria, es de solo lectura: no crea, modifica ni
        elimina ningún dato.
        """
        if not getattr(self, "autenticado", False):
            return

        with self.client.get(
            URL_AGENDA_SEMANAL,
            name="Agenda semanal - GET",
            catch_response=True,
        ) as respuesta:
            if "Cerrar sesión" not in respuesta.text:
                respuesta.failure(
                    "La respuesta no corresponde a un usuario "
                    "autenticado (¿la sesión expiró?)."
                )

    @task
    def crear_audiencia_loadtest(self):
        """
        "Crear audiencia - LOADTEST" (round-trip completo, repetido en
        ciclo): cada vez que Locust elige esta tarea al azar para este
        usuario virtual, ejecuta UN ciclo completo -crea una audiencia
        de prueba y luego la deja sin efecto, con sus verificaciones-,
        hasta un máximo de CICLOS_POR_USUARIO veces por usuario (5 por
        defecto). Siempre usa la MISMA causa LOADTEST que le fue
        asignada de forma determinista en on_start()
        (self.rit_loadtest): los CICLOS_POR_USUARIO ciclos de un mismo
        usuario reutilizan siempre esa única causa, nunca rotan entre
        varias -es, además, la forma en que esta prueba comprueba que
        el sistema permite volver a registrar una audiencia nueva para
        una causa cuya audiencia anterior ya quedó "Eliminada" (baja
        lógica, nunca eliminación física): nada en Causa ni en
        ServicioCreacionAudiencia impide reutilizarla-.

        No hay ningún "while True" ni bucle propio: el límite de
        CICLOS_POR_USUARIO se controla con un simple contador
        (self.ciclos_loadtest_completados, incrementado en cada
        ejecución) y la repetición en sí la produce el propio
        mecanismo de Locust -elige esta tarea al azar, la ejecuta,
        espera wait_time (self.wait(), ver User.wait() de Locust),
        vuelve a elegir una tarea-, sin necesidad de dormir
        manualmente dentro de esta función. Al llegar al límite, la
        tarea se vuelve una no-operación para el resto de la corrida
        de ese usuario: Agenda diaria y Agenda semanal siguen
        funcionando con total normalidad, ya que son tareas
        independientes.

        Es el flujo más costoso de todo el sistema (varias consultas +
        validaciones de negocio + dos escrituras por ciclo: creación y
        baja), con datos de prueba claramente identificables,
        respetando las reglas de agendamiento reales en vez de
        inventar una fecha/bloque cualquiera, y usando el mecanismo
        REAL de baja lógica de la aplicación (nunca un borrado físico
        ni una API inventada). Un ciclo que falla en cualquier paso
        aborta ÚNICAMENTE ese ciclo (con el fallo correctamente
        registrado en Locust): nunca detiene la prueba completa, ni
        impide que este mismo usuario intente su siguiente ciclo
        cuando Locust vuelva a elegir esta tarea.

        ADVERTENCIAS DE PROGRAMACIÓN (confirmación automática, con
        MÉTRICAS SEPARADAS -no son "éxitos silenciosos"-): al reutilizar
        la misma causa/sala en varios ciclos y usuarios concurrentes, es
        esperable que ValidadorAgendamiento devuelva la advertencia real
        "Ya existe una audiencia programada en la sala y horario
        seleccionados..." (conflicto de horario, ver
        ValidadorAgendamiento.validarConflicto() en
        audiencias/services.py) u otra advertencia de negocio, sin
        ningún error bloqueante. En ese caso -detectado porque el
        servidor NO confirma "registrada correctamente" pero SÍ muestra
        la tarjeta "Advertencias de programación", ver
        _extraer_diagnostico_formulario más arriba- esta tarea:
          1. NO marca esa primera solicitud como fallida (es el
             comportamiento real y esperado del sistema, no un error
             técnico), pero TAMPOCO la cuenta como creación: se registra
             en su propia fila "Audiencia - advertencia" (ver
             _registrar_resultado_categoria), nunca junto a "Audiencia -
             creación directa".
          2. Registra el diagnóstico completo de la advertencia (ver
             _registrar_advertencia_confirmacion).
          3. Reenvía EXACTAMENTE la misma solicitud, agregando
             "confirmar_advertencias": "1" -el mismo campo/valor que
             usa el botón "Confirmar programación" real, ver
             templates/audiencias/formulario.html-, hacia su propia
             fila "Audiencia - confirmación".
          4. Si esa confirmación logra registrar la audiencia, esa
             MISMA fila ("Audiencia - confirmación") queda marcada como
             éxito -es la única forma en que una audiencia que empezó
             con advertencia termina contando como creada-.
          5. Si esa confirmación tampoco logra registrar la audiencia,
             esa fila se marca como fallo (FAIL real, visible en
             Locust), con el mismo nivel de diagnóstico (RIT, ciclo,
             código HTTP, URL, mensajes, advertencias).

        Ver "MÉTRICAS" en el encabezado de este archivo para el mapeo
        completo entre cada fila de Locust y las 7 métricas pedidas
        (intentos, creaciones directas, advertencias, confirmaciones
        intentadas/exitosas/fallidas, errores reales).

        No crea ni modifica ninguna Causa (no existe esa API): busca,
        vía competencia+rit, una Causa de prueba que YA debe existir
        (LOADTEST-101..LOADTEST-200, repartidas entre las competencias
        Garantía/Familia/Laboral según el rango de cada una -ver
        _competencia_id_para_numero_causa más arriba-, ya cargadas
        mediante Causas -> Importar Causas, ver "PRECONDICIÓN
        OBLIGATORIA" al inicio de este archivo).

        Pasos de CADA ciclo, calcados del flujo real de
        templates/audiencias/formulario.html y
        templates/audiencias/agenda.html:
          1. Verifica que on_start() haya dejado al usuario
             autenticado (si el login falló, no se intenta nada).
          2. Verifica que todavía no se hayan completado
             CICLOS_POR_USUARIO ciclos para este usuario virtual -si
             ya se alcanzó el límite, esta ejecución no hace nada-.
          3. La causa LOADTEST a usar (self.rit_loadtest) ya quedó
             fija desde on_start(): no se vuelve a calcular aquí, y es
             la misma en todos los ciclos de este usuario.
          4. GET del formulario ("Nueva Audiencia"), para la cookie CSRF.
          5. POST a proponer_fechas_audiencia (competencia, rit,
             tipoAudiencia, sala, cantidadBloques), para obtener una
             fecha/bloque ya validados por GeneradorPropuestaFecha
             (mismo mecanismo que el botón "Solicitar propuestas":
             evalúa DiaAtencion, DiaNoDisponible, ReglaAgendamiento y
             disponibilidad real de bloques -no se inventa ninguna
             fecha ni bloque-). Se toma EXCLUSIVAMENTE la PRIMERA
             propuesta devuelta (ver _PATRON_PROPUESTA: re.search()
             ya devuelve solo la primera coincidencia, en el mismo
             orden cronológico en que el propio servicio las genera).
          6. POST a registrar_audiencia con el formulario completo,
             usando esa primera propuesta -mismo mecanismo que "Usar
             esta propuesta" + "Guardar audiencia"-. Tres desenlaces
             posibles:
               a) Confirma el guardado directamente (mensaje
                  "registrada correctamente" con este RIT) -> continúa
                  normalmente.
               b) Pide confirmar advertencias (ver "ADVERTENCIAS DE
                  PROGRAMACIÓN" más arriba) -> NO es un fallo; se
                  registra la advertencia y se reenvía con
                  confirmar_advertencias=1 (paso 6-bis, ver arriba). Si
                  esa confirmación tampoco confirma el guardado, AHÍ SÍ
                  se marca fallo.
               c) Error bloqueante real (causa no encontrada, campo
                  inválido, etc., sin ninguna advertencia que
                  confirmar) -> se marca fallo y NO se continúa -no
                  tiene sentido "dejar sin efecto" una audiencia que
                  nunca se creó-.
             En los casos de fallo (b sin éxito, o c) se extrae y se
             registra un diagnóstico de la respuesta real (mensajes
             del sistema, errores de formulario, advertencias -ver
             _extraer_diagnostico_formulario/
             _formatear_diagnostico_creacion más arriba en este
             archivo-), sin incluir nunca el HTML completo ni datos
             sensibles.
          7. Consulta la Agenda diaria de esa sala/fecha y extrae, del
             botón "Dejar sin efecto" de la fila de este RIT, su ID
             real (pk) vía data-audiencia-id -ese botón solo existe
             para audiencias PROGRAMADA, así que encontrarlo confirma
             a la vez el ID y que la audiencia quedó correctamente
             programada (paso 8 del pedido). Si no se encuentra, se
             marca fallo y tampoco se continúa -sin un ID real
             confirmado, no se intenta ningún "Dejar sin efecto"-.
          8. (incluido en el paso 7: la sola presencia del botón real,
             renderizado solo para PROGRAMADA, ya es la verificación
             de que la audiencia quedó correctamente programada).
          9. POST a dejar_sin_efecto_audiencia (audiencia_id real,
             motivo_seleccionado="OTRO" + motivo_otro identificable,
             csrfmiddlewaretoken) -el mismo mecanismo que usa el modal
             "Dejar sin efecto" de la interfaz real (ver
             templates/audiencias/_modal_dejar_sin_efecto.html), sin
             inventar ningún endpoint ni parámetro. Si el servidor no
             confirma la baja ("Audiencia dejada sin efecto
             correctamente."), se marca fallo.
          10. Nueva consulta a la Agenda diaria de esa sala/fecha y
              verifica, leyendo el badge de "Estado" de la fila de
              este RIT (ver _extraer_estado_por_rit), que su valor sea
              exactamente "Eliminada" -la etiqueta real de
              EstadoAudiencia.ELIMINADA, nunca un borrado físico-.

        En ningún punto de este flujo se registra el RIT para una
        limpieza posterior "silenciosa": la baja ya ocurre, real y
        verificada, dentro de esta misma tarea (pasos 9-10). Se
        conserva igual el registro en ARCHIVO_REGISTRO_LOADTEST (ver
        _registrar_audiencia_creada, llamado apenas se confirma el ID
        real en el paso 7) únicamente como red de seguridad: si el
        "Dejar sin efecto" de los pasos 9-10 llegara a fallar, ese
        registro permite ubicar después, manualmente, con
        limpiar_audiencias_loadtest(), cualquier audiencia LOADTEST
        que hubiera quedado PROGRAMADA.

        Trazabilidad: no requiere ninguna acción adicional de este
        script. Tanto la creación (ServicioCreacionAudiencia.crear())
        como la baja (ServicioBajaAudiencia.ejecutar()) ya registran
        automáticamente su propia operación en RegistroTrazabilidad
        (ServicioTrazabilidad.registrarCreacion() /
        .registrarBaja(), dentro de la misma transacción que cada
        escritura, ver audiencias/services.py) -es historial real del
        sistema, verificable después con "Ver trazabilidad" desde la
        Agenda diaria, sin que este script tenga que hacer nada
        adicional para generarlo.
        """
        if not getattr(self, "autenticado", False):
            return

        # Contador controlado (NO un "while True"): si este usuario
        # virtual ya completó CICLOS_POR_USUARIO ciclos -con éxito o
        # no, cada intento cuenta como un ciclo-, esta ejecución no
        # hace nada. Se incrementa ANTES de ejecutar el ciclo, para
        # que el límite se respete incluso si el ciclo termina
        # devolviéndose a mitad de camino por un fallo.
        if self.ciclos_loadtest_completados >= CICLOS_POR_USUARIO:
            return
        self.ciclos_loadtest_completados += 1
        numero_ciclo = self.ciclos_loadtest_completados

        competencia_id = self.competencia_id_loadtest

        if not (competencia_id and TIPO_AUDIENCIA_ID and SALA_ID):
            # Faltan los IDs de catálogo reales (ver "CONFIGURACIÓN
            # DE LA CREACIÓN DE AUDIENCIAS" más arriba): sin ellos no
            # se puede intentar nada, y no se debe adivinar ningún ID.
            with self.client.get(
                URL_NUEVA_AUDIENCIA,
                name="Nueva audiencia - creación",
                catch_response=True,
            ) as respuesta:
                respuesta.failure(
                    f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] Falta la "
                    f"competencia resuelta para este usuario, o "
                    f"LOCUST_TIPO_AUDIENCIA_ID / LOCUST_SALA_ID: no se puede "
                    f"crear la audiencia de prueba."
                )
            return

        # La causa LOADTEST -y su competencia- de este usuario virtual
        # ya quedaron fijas en on_start() (ver _rit_loadtest_para_indice/
        # _competencia_id_para_numero_causa): TODOS los ciclos de este
        # usuario reutilizan la misma causa -es intencional, ver el
        # docstring: así se comprueba que el sistema permite volver a
        # agendar sobre una causa cuya audiencia anterior ya fue dejada
        # sin efecto-.
        rit = self.rit_loadtest

        # -----------------------------------------------
        # (a) Formulario ("Nueva Audiencia"): obtiene el token CSRF
        #     vigente, igual que en on_start().
        # -----------------------------------------------
        self.client.get(URL_NUEVA_AUDIENCIA, name="Nueva audiencia - formulario")
        csrf_token = self.client.cookies.get("csrftoken")

        datos_base = {
            "competencia": competencia_id,
            "rit": rit,
            "tipoAudiencia": TIPO_AUDIENCIA_ID,
            "sala": SALA_ID,
            "cantidadBloques": CANTIDAD_BLOQUES,
            "csrfmiddlewaretoken": csrf_token,
        }

        # -----------------------------------------------
        # (b) Propuestas automáticas de fecha/bloques: mismos campos
        #     que envía "Solicitar propuestas" (no incluye fecha ni
        #     bloqueInicio todavía, es justo lo que se está pidiendo).
        # -----------------------------------------------
        fecha_propuesta = None
        bloque_propuesta = None

        with self.client.post(
            URL_PROPONER_FECHAS,
            data=datos_base,
            headers={"Referer": f"{self.host}{URL_NUEVA_AUDIENCIA}"},
            name="Nueva audiencia - propuestas",
            catch_response=True,
        ) as respuesta_propuestas:
            coincidencia = _PATRON_PROPUESTA.search(respuesta_propuestas.text)
            if coincidencia is None:
                respuesta_propuestas.failure(
                    f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] No se generó "
                    f"ninguna propuesta de fecha/bloque para RIT {rit} (¿existe "
                    f"la Causa de prueba? ¿hay días de atención configurados "
                    f"para la competencia?)."
                )
                # Sin una fecha/bloque válidos no tiene sentido seguir:
                # se corta el flujo aquí, sin intentar crear nada.
                return

            fecha_propuesta, bloque_propuesta = coincidencia.groups()

        # -----------------------------------------------
        # (c) Registrar la audiencia con la fecha/bloque ya obtenidos
        #     -mismos campos que envía "Guardar audiencia"-.
        # -----------------------------------------------
        datos_creacion = dict(
            datos_base,
            fecha=fecha_propuesta,
            bloqueInicio=bloque_propuesta,
            anotacion=(
                f"Prueba de carga Locust - {rit} - "
                f"ciclo {numero_ciclo}/{CICLOS_POR_USUARIO} - "
                f"{datetime.now().isoformat(timespec='seconds')}"
            ),
        )

        creada = False
        diagnostico = None

        # "Audiencia - intento creación": UN intento de creación, sin
        # importar en cuál de los tres desenlaces termine (directa,
        # advertencia, o error real) -esta fila por sí sola ya responde
        # la métrica 1 ("cantidad de intentos"): su cantidad total de
        # solicitudes es exactamente eso-.
        with self.client.post(
            URL_NUEVA_AUDIENCIA,
            data=datos_creacion,
            headers={"Referer": f"{self.host}{URL_NUEVA_AUDIENCIA}"},
            name="Audiencia - intento creación",
            catch_response=True,
        ) as respuesta_creacion:
            # El criterio de éxito/fallo sigue siendo EXCLUSIVAMENTE
            # este chequeo de contenido -nunca respuesta_creacion.
            # status_code por sí solo-: un HTTP 200 con advertencias
            # sin confirmar, o con errores de validación, NO se
            # convierte en éxito solo porque el servidor respondió
            # 200 (registrar_audiencia siempre responde 200 al
            # re-renderizar el formulario en esos casos, ver
            # audiencias/views.py).
            creada = (
                "registrada correctamente" in respuesta_creacion.text
                and rit in respuesta_creacion.text
            )

            if creada:
                # Creación DIRECTA: el servidor confirmó el guardado ya
                # en esta primera respuesta, sin ninguna advertencia de
                # por medio. Es la ÚNICA situación que cuenta como
                # "Audiencia - creación directa" (métrica 2) -por eso
                # NUNCA se marca así cuando hubo advertencia, aunque
                # esta terminara confirmándose más abajo-.
                respuesta_creacion.success()
                _registrar_resultado_categoria(self, "Audiencia - creación directa", exito=True)
            else:
                # -----------------------------------------------
                # DIAGNÓSTICO: qué respondió realmente el servidor.
                # Con únicamente los fragmentos relevantes (mensajes,
                # errores de formulario, advertencias/confirmación
                # pendiente), nunca el HTML completo ni ningún dato
                # sensible (ver
                # _extraer_diagnostico_formulario/_redactar_html_sensible
                # más arriba: no se registran csrfmiddlewaretoken,
                # cookies ni credenciales).
                # -----------------------------------------------
                diagnostico = _extraer_diagnostico_formulario(respuesta_creacion.text)

                if diagnostico["requiere_confirmacion"]:
                    # Es una ADVERTENCIA de negocio (no bloqueante),
                    # exactamente el comportamiento real de
                    # ServicioCreacionAudiencia cuando hay advertencias
                    # sin confirmar (ver audiencias/services.py): el
                    # servidor respondió con normalidad (200), solo
                    # pidió confirmar. El INTENTO en sí no fue un fallo
                    # técnico -se comunicó correctamente con el
                    # servidor y obtuvo una respuesta reconocida-, por
                    # eso esta solicitud se marca éxito; pero -a
                    # diferencia de antes- YA NO se cuenta como
                    # creación: se registra aparte, en su propia fila
                    # "Audiencia - advertencia" (métrica 3), como una
                    # condición de negocio, NO como un error técnico ni
                    # como una creación exitosa. La creación en sí
                    # queda pendiente de la confirmación real de más
                    # abajo (c-bis).
                    respuesta_creacion.success()
                    _registrar_advertencia_confirmacion(rit, numero_ciclo, diagnostico)
                    _registrar_resultado_categoria(self, "Audiencia - advertencia", exito=True)
                else:
                    # Error real (bloqueante): validación fallida,
                    # causa no encontrada, etc. -no hay advertencias
                    # que confirmar, no tiene sentido reenviar nada-.
                    # Este SÍ es un fallo real: se marca FAIL tanto en
                    # el intento en sí como en su propia fila "Audiencia
                    # - error real de creación" (métrica 7).
                    texto_diagnostico = _formatear_diagnostico_creacion(
                        respuesta_creacion.status_code,
                        f"{self.host}{URL_NUEVA_AUDIENCIA}",
                        f"{rit} [ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}]",
                        diagnostico,
                    )
                    print(texto_diagnostico)
                    mensaje_fallo = (
                        f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] La audiencia "
                        f"RIT {rit} no quedó registrada (el servidor no confirmó "
                        f"'...registrada correctamente.' con ese RIT, y tampoco "
                        f"pidió confirmar advertencias).\n{texto_diagnostico}"
                    )
                    respuesta_creacion.failure(mensaje_fallo)
                    _registrar_resultado_categoria(
                        self,
                        "Audiencia - error real de creación",
                        exito=False,
                        motivo_fallo=mensaje_fallo,
                    )
                    return

        # -----------------------------------------------
        # (c-bis) Confirmación de advertencias: SOLO si el primer
        # intento pidió confirmar (diagnostico["requiere_confirmacion"]
        # == True). Reproduce EXACTAMENTE la misma solicitud HTTP que
        # ya realiza el botón "Confirmar programación" de la interfaz
        # real (ver templates/audiencias/formulario.html): ese botón,
        # aunque vive fuera de <form id="form-audiencia">, usa el
        # atributo HTML form="form-audiencia" para enviar ESE MISMO
        # formulario completo (los mismos campos que datos_creacion) y
        # agrega únicamente name="confirmar_advertencias" value="1".
        # audiencias/views.py interpreta exactamente ese campo
        # (request.POST.get("confirmar_advertencias") == "1") para
        # volver a ejecutar ServicioCreacionAudiencia con
        # confirmarAdvertencias=True -no se inventa ningún campo,
        # valor ni endpoint nuevo; se reenvía a la MISMA URL
        # (registrar_audiencia)-.
        # -----------------------------------------------
        if not creada and diagnostico is not None and diagnostico["requiere_confirmacion"]:
            csrf_token = self.client.cookies.get("csrftoken") or csrf_token
            datos_confirmacion = dict(
                datos_creacion,
                confirmar_advertencias="1",
                csrfmiddlewaretoken=csrf_token,
            )

            # "Audiencia - confirmación": UN intento de confirmación
            # (métrica 4 = cantidad total de solicitudes de esta fila).
            # Su propio success()/failure() -marcado explícitamente en
            # ambas ramas de abajo, no dejado al valor por defecto de
            # Locust- separa directamente, dentro de la MISMA fila,
            # cuántas de esas confirmaciones fueron exitosas (métrica 5)
            # de cuántas fallaron (métrica 6): son, respectivamente, el
            # conteo de éxitos y de fallos que Locust ya calcula nativo
            # para cualquier fila en Statistics/CSV.
            with self.client.post(
                URL_NUEVA_AUDIENCIA,
                data=datos_confirmacion,
                headers={"Referer": f"{self.host}{URL_NUEVA_AUDIENCIA}"},
                name="Audiencia - confirmación",
                catch_response=True,
            ) as respuesta_confirmacion:
                creada = (
                    "registrada correctamente" in respuesta_confirmacion.text
                    and rit in respuesta_confirmacion.text
                )
                if creada:
                    # Confirmación EXITOSA: la audiencia terminó
                    # realmente registrada -recién ahora, no antes-.
                    # Este es el único camino en el que una audiencia
                    # que empezó con advertencia termina contando como
                    # creada: a través de esta fila ("Audiencia -
                    # confirmación" exitosa), nunca mezclada con
                    # "Audiencia - creación directa".
                    respuesta_confirmacion.success()
                else:
                    diagnostico_confirmacion = _extraer_diagnostico_formulario(
                        respuesta_confirmacion.text
                    )
                    texto_diagnostico = _formatear_diagnostico_creacion(
                        respuesta_confirmacion.status_code,
                        f"{self.host}{URL_NUEVA_AUDIENCIA}",
                        f"{rit} [ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] "
                        f"(tras confirmar_advertencias=1)",
                        diagnostico_confirmacion,
                    )
                    print(texto_diagnostico)
                    respuesta_confirmacion.failure(
                        f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] Se envió la "
                        f"confirmación de advertencias (confirmar_advertencias=1) "
                        f"para RIT {rit}, pero la audiencia igual no quedó "
                        f"registrada.\n{texto_diagnostico}"
                    )
                    return

        if not creada:
            # Guarda defensiva: los dos caminos de arriba (error
            # bloqueante, o confirmación fallida) siempre retornan
            # antes de llegar aquí. Se deja explícito para nunca
            # continuar el ciclo (verificar en agenda/"Dejar sin
            # efecto") con una audiencia de la que no hay confirmación
            # real de que exista.
            return

        # -----------------------------------------------
        # (d) Verificación real de que quedó PROGRAMADA + obtención de
        #     su ID real (pk): la audiencia debe aparecer en la Agenda
        #     diaria de esa sala/fecha, con ESTE RIT específico (no
        #     basta con el mensaje de éxito del paso anterior), y el
        #     botón "Dejar sin efecto" de esa fila -que solo existe
        #     para audiencias PROGRAMADA- debe traer su
        #     data-audiencia-id. Sin un ID real confirmado no se
        #     intenta ningún "Dejar sin efecto" a continuación.
        # -----------------------------------------------
        audiencia_id = None

        with self.client.get(
            f"{URL_AGENDA_DIARIA}?sala={SALA_ID}&fecha={fecha_propuesta}",
            name="Nueva audiencia - verificacion en agenda",
            catch_response=True,
        ) as respuesta_verificacion:
            if rit not in respuesta_verificacion.text:
                respuesta_verificacion.failure(
                    f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] La audiencia "
                    f"RIT {rit} no aparece en la Agenda diaria de la sala "
                    f"{SALA_ID} para {fecha_propuesta}."
                )
                return

            coincidencia_id = _patron_boton_dejar_sin_efecto(rit).search(
                respuesta_verificacion.text
            )
            if coincidencia_id is None:
                respuesta_verificacion.failure(
                    f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] La audiencia "
                    f"RIT {rit} aparece en la Agenda diaria, pero no se "
                    f"encontró su botón 'Dejar sin efecto' (no está "
                    f"PROGRAMADA, o no se pudo leer su ID real)."
                )
                return

            audiencia_id = coincidencia_id.group(1)

        # -----------------------------------------------
        # (e) Registra este RIT como red de seguridad, ANTES de
        #     intentar la baja: si "Dejar sin efecto" fallara más
        #     abajo, limpiar_audiencias_loadtest() igual podrá ubicar
        #     y dejar sin efecto esta audiencia más adelante. No se
        #     borra nada aquí, esto es solo un registro.
        # -----------------------------------------------
        _registrar_audiencia_creada(rit, SALA_ID, fecha_propuesta)

        # -----------------------------------------------
        # (f) "Dejar sin efecto" REAL: mismo endpoint, mismo método,
        #     mismos parámetros y el mismo CSRF que usa el modal real
        #     de la interfaz (ver
        #     templates/audiencias/_modal_dejar_sin_efecto.html) -no
        #     se inventa nada-. Se relee la cookie CSRF justo antes de
        #     este POST (en vez de reutilizar la de (a)), igual que ya
        #     hace limpiar_audiencias_loadtest() entre sus propias
        #     solicitudes.
        # -----------------------------------------------
        csrf_token = self.client.cookies.get("csrftoken") or csrf_token

        with self.client.post(
            URL_DEJAR_SIN_EFECTO,
            data={
                "audiencia_id": audiencia_id,
                "motivo_seleccionado": "OTRO",
                "motivo_otro": (
                    f"Prueba de carga Locust (round-trip) - {rit} - "
                    f"ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}"
                ),
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": f"{self.host}{URL_AGENDA_DIARIA}"},
            name="Dejar sin efecto - LOADTEST",
            catch_response=True,
        ) as respuesta_baja:
            if "Audiencia dejada sin efecto correctamente." not in respuesta_baja.text:
                respuesta_baja.failure(
                    f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] No se "
                    f"confirmó la baja de la audiencia RIT {rit} "
                    f"(id={audiencia_id}): el servidor no devolvió "
                    f"'Audiencia dejada sin efecto correctamente.'."
                )
                return

        # -----------------------------------------------
        # (g) Verificación final: nueva consulta a la Agenda diaria y
        #     confirma que el badge de "Estado" de esta fila cambió
        #     exactamente a "Eliminada" (EstadoAudiencia.ELIMINADA.label,
        #     ver audiencias/models.py) -no basta con el mensaje de
        #     éxito del paso anterior-.
        # -----------------------------------------------
        with self.client.get(
            f"{URL_AGENDA_DIARIA}?sala={SALA_ID}&fecha={fecha_propuesta}",
            name="Dejar sin efecto - verificacion en agenda",
            catch_response=True,
        ) as respuesta_verificacion_baja:
            estado_actual = _extraer_estado_por_rit(respuesta_verificacion_baja.text, rit)
            if estado_actual != "Eliminada":
                respuesta_verificacion_baja.failure(
                    f"[ciclo {numero_ciclo}/{CICLOS_POR_USUARIO}] La audiencia "
                    f"RIT {rit} (id={audiencia_id}) no quedó en estado "
                    f"'Eliminada' tras 'Dejar sin efecto' (estado leído: "
                    f"{estado_actual!r})."
                )
                return


# =====================================================
# LIMPIEZA (script separado, NO es una tarea de Locust)
# =====================================================


def limpiar_audiencias_loadtest():
    """
    Deja sin efecto (baja lógica, NUNCA elimina físicamente) cada
    audiencia que "Crear audiencia - LOADTEST" haya registrado en
    ARCHIVO_REGISTRO_LOADTEST durante una corrida anterior.

    NOTA: desde que crear_audiencia_loadtest() ya ejecuta su propio
    "Dejar sin efecto" (pasos (f)/(g) de esa tarea, ver su docstring),
    esta función pasa a ser una RED DE SEGURIDAD -no el mecanismo
    principal de limpieza-: solo hace falta ejecutarla si alguna
    audiencia quedó PROGRAMADA porque esa baja automática falló
    durante la corrida (ver ARCHIVO_REGISTRO_LOADTEST, que igual
    registra cada RIT apenas se confirma su creación, antes de
    intentar la baja).

    IMPORTANTE - por qué es un script separado y no una tarea:
    - Locust ejecuta como carga TODO lo que sea @task de un HttpUser
      definido en este archivo, en cuanto corre "locust -f
      locustfile.py". Para que la limpieza NUNCA se dispare
      automáticamente durante una prueba de carga, esta función
      deliberadamente NO es un método de UsuarioAgendaDiaria ni de
      ningún otro HttpUser: es una función Python común, que Locust
      ni siquiera sabe que existe.
    - Solo se ejecuta invocando este archivo directamente:

          python locustfile.py limpiar

      (nunca con el comando "locust"). El bloque
      "if __name__ == '__main__'" de más abajo es la única puerta de
      entrada a esta función.

    Reutiliza el mecanismo REAL de baja lógica ya existente
    (dejar_sin_efecto_audiencia, audiencias/views.py /
    ServicioBajaAudiencia, audiencias/services.py): no se inventa
    ninguna forma de "eliminar" una audiencia. Como esa vista exige
    el ID interno (pk) de la Audiencia -que este script nunca guardó,
    porque registrar_audiencia no lo expone en su respuesta-, ese ID
    se obtiene consultando la Agenda diaria real de la sala/fecha
    registradas (mismo botón "Dejar sin efecto" que ve un
    funcionario, con sus atributos data-audiencia-id/data-rit, ver
    templates/audiencias/agenda.html) y localizando ahí la fila cuyo
    RIT coincide EXACTAMENTE con el registrado.

    Doble resguardo de seguridad, en dos capas distintas:
      1) Solo se procesan los RIT que están en
         ARCHIVO_REGISTRO_LOADTEST (los que esta prueba realmente
         creó, nunca "todas las audiencias de esa sala/fecha").
      2) Antes de dejar sin efecto, se vuelve a exigir que ese RIT
         empiece con PREFIJO_RIT_LOADTEST -si el archivo de registro
         llegara a contener algo distinto por error, no se toca-.

    Requiere las mismas variables de entorno que la prueba de carga
    (LOCUST_USUARIO/LOCUST_CLAVE) más LOCUST_HOST (URL base del
    servidor, por ejemplo "http://127.0.0.1:8000"; no tiene valor por
    defecto a propósito, para no apuntar nunca a un servidor
    equivocado sin que quien ejecuta el script lo haya decidido
    explícitamente).
    """
    # Import local (no al inicio del archivo): "requests" solo hace
    # falta para este script de limpieza manual, no para la prueba de
    # carga en sí (que usa self.client, ya provisto por HttpUser). Es
    # una dependencia propia de locust (locust.clients.HttpSession
    # hereda de requests.Session), así que ya está disponible en este
    # entorno sin agregar nada al proyecto.
    import requests

    host = os.environ.get("LOCUST_HOST")
    if not host:
        print(
            "[limpieza] Falta LOCUST_HOST (ej: "
            "http://127.0.0.1:8000). No se ejecuta ninguna limpieza."
        )
        return

    if not os.path.exists(ARCHIVO_REGISTRO_LOADTEST):
        print(
            f"[limpieza] No existe {ARCHIVO_REGISTRO_LOADTEST}: no hay "
            f"ninguna audiencia LOADTEST registrada que limpiar."
        )
        return

    # -------------------------------------------------
    # Lee el registro. Cada línea es un JSON independiente (formato
    # JSONL): una audiencia por línea, tal como la fue escribiendo
    # _registrar_audiencia_creada() durante la prueba.
    # -------------------------------------------------
    registros = []
    with open(ARCHIVO_REGISTRO_LOADTEST, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            try:
                registros.append(json.loads(linea))
            except json.JSONDecodeError:
                print(f"[limpieza] Línea inválida ignorada: {linea!r}")

    # Filtro de seguridad (capa 2, ver docstring): descarta cualquier
    # registro cuyo RIT no empiece con el prefijo esperado.
    registros = [r for r in registros if r.get("rit", "").startswith(PREFIJO_RIT_LOADTEST)]

    if not registros:
        print("[limpieza] El archivo de registro no tiene audiencias LOADTEST válidas.")
        return

    print(f"[limpieza] {len(registros)} audiencia(s) LOADTEST registradas para revisar.")

    # -------------------------------------------------
    # Inicia sesión (mismo flujo GET+POST que on_start(), pero con
    # "requests" directo en vez de self.client de Locust).
    # -------------------------------------------------
    sesion = requests.Session()

    respuesta_login_formulario = sesion.get(f"{host}{URL_LOGIN}")
    respuesta_login_formulario.raise_for_status()
    csrf_token = sesion.cookies.get("csrftoken")

    respuesta_login = sesion.post(
        f"{host}{URL_LOGIN}",
        data={
            "username": USUARIO_PRUEBA,
            "password": CLAVE_PRUEBA,
            "csrfmiddlewaretoken": csrf_token,
        },
        headers={"Referer": f"{host}{URL_LOGIN}"},
    )
    respuesta_login.raise_for_status()

    if "Cerrar sesión" not in respuesta_login.text:
        print(
            "[limpieza] No se pudo autenticar con LOCUST_USUARIO/"
            "LOCUST_CLAVE. Se aborta sin tocar ninguna audiencia."
        )
        return

    # -------------------------------------------------
    # Agrupa por (sala, fecha): una sola consulta de Agenda diaria
    # sirve para localizar todas las audiencias LOADTEST de ese mismo
    # día/sala, en vez de una consulta por RIT.
    # -------------------------------------------------
    por_sala_y_fecha = {}
    for registro in registros:
        clave = (registro.get("sala_id"), registro.get("fecha"))
        por_sala_y_fecha.setdefault(clave, []).append(registro["rit"])

    total_dadas_de_baja = 0
    total_no_encontradas = 0

    for (sala_id, fecha), rits_esperados in por_sala_y_fecha.items():
        respuesta_agenda = sesion.get(
            f"{host}{URL_AGENDA_DIARIA}", params={"sala": sala_id, "fecha": fecha}
        )
        respuesta_agenda.raise_for_status()
        csrf_token = sesion.cookies.get("csrftoken") or csrf_token

        for rit in rits_esperados:
            if not rit.startswith(PREFIJO_RIT_LOADTEST):
                # Redundante con el filtro de más arriba, pero se
                # repite aquí a propósito: es la última línea de
                # defensa, justo antes de dar de baja algo.
                continue

            # Busca, en la agenda ya descargada, el botón "Dejar sin
            # efecto" cuyo data-rit coincide EXACTAMENTE con este RIT
            # (mismo orden de atributos que
            # templates/audiencias/agenda.html: data-audiencia-id
            # antes que data-rit).
            patron_boton = re.compile(
                r'data-audiencia-id="(\d+)"\s+data-rit="' + re.escape(rit) + r'"'
            )
            coincidencia = patron_boton.search(respuesta_agenda.text)

            if coincidencia is None:
                print(
                    f"[limpieza] RIT {rit}: no se encontró en la Agenda "
                    f"diaria (sala={sala_id}, fecha={fecha}) -puede que ya "
                    f"esté dada de baja, o no exista-. No se hace nada."
                )
                total_no_encontradas += 1
                continue

            audiencia_id = coincidencia.group(1)

            respuesta_baja = sesion.post(
                f"{host}{URL_DEJAR_SIN_EFECTO}",
                data={
                    "audiencia_id": audiencia_id,
                    "motivo_seleccionado": "OTRO",
                    "motivo_otro": f"Limpieza de datos de prueba de carga (Locust) - {rit}",
                    "csrfmiddlewaretoken": csrf_token,
                },
                headers={"Referer": f"{host}{URL_AGENDA_DIARIA}"},
            )
            respuesta_baja.raise_for_status()

            if "Audiencia dejada sin efecto correctamente." in respuesta_baja.text:
                print(f"[limpieza] RIT {rit} (id={audiencia_id}): dejada sin efecto.")
                total_dadas_de_baja += 1
            else:
                print(
                    f"[limpieza] RIT {rit} (id={audiencia_id}): la baja NO "
                    f"se confirmó; revisar manualmente."
                )

    print(
        f"[limpieza] Terminado: {total_dadas_de_baja} dada(s) de baja, "
        f"{total_no_encontradas} no encontrada(s)."
    )


if __name__ == "__main__":
    # Única puerta de entrada a la limpieza -ver el docstring de
    # limpiar_audiencias_loadtest() para el motivo de este diseño.
    # "locust -f locustfile.py" NUNCA pasa por aquí: solo importa
    # este módulo y busca clases HttpUser, no ejecuta este bloque.
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "limpiar":
        limpiar_audiencias_loadtest()
    else:
        print(
            "Este archivo se usa normalmente como:\n"
            "    locust -f locustfile.py\n"
            "\n"
            "Para limpiar (dejar sin efecto) las audiencias LOADTEST\n"
            "creadas durante una corrida anterior, ejecuta en cambio:\n"
            "    python locustfile.py limpiar\n"
        )
