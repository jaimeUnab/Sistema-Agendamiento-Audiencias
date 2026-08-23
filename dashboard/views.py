import datetime

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# Importa el decorador que obliga al usuario a iniciar sesión.

# Fecha de hoy respetando la zona horaria configurada del proyecto
# (TIME_ZONE = America/Santiago, USE_TZ=True) -nunca
# datetime.date.today()-, mismo criterio que ya usa el resto del
# proyecto (ver por ejemplo agenda_diaria en audiencias/views.py).
from django.utils import timezone

from audiencias.models import Audiencia, EstadoAudiencia


@login_required
def inicio(request):
    """
    Vista principal del sistema.

    Muestra el Dashboard únicamente si el usuario
    ha iniciado sesión correctamente.

    Además de la estructura general, calcula las dos cifras de
    resumen que muestra la pantalla ("Audiencias del día" y
    "Audiencias de la semana"): ambas son un simple conteo de
    Audiencia en estado PROGRAMADA -el único estado real que
    representa una audiencia vigente, ver EstadoAudiencia en
    audiencias/models.py; las audiencias ELIMINADA (dadas de baja)
    quedan excluidas automáticamente porque el filtro exige
    estado=PROGRAMADA-, para la fecha de hoy y para la semana actual
    respectivamente. Al ser una consulta directa a la base de datos
    en cada ingreso a esta vista (sin caché de ningún tipo), el
    número mostrado siempre refleja el estado real y más reciente de
    las audiencias, sin necesitar ninguna actualización manual.

    No repite ninguna regla de negocio de agendamiento: es una
    lectura de solo conteo, igual de "solo lectura" que
    agenda_diaria/agenda_semanal (audiencias/views.py), de las que
    además reutiliza el mismo criterio para calcular el rango de la
    semana actual (lunes a domingo, a partir de fecha.weekday()).
    """

    hoy = timezone.localdate()

    # Semana actual: lunes (weekday()==0) a domingo, mismo cálculo
    # que ya usa agenda_semanal (audiencias/views.py), para no
    # inventar un criterio de "semana" distinto al que ya conoce el
    # resto del sistema.
    inicio_semana = hoy - datetime.timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + datetime.timedelta(days=6)

    audiencias_del_dia = Audiencia.objects.filter(
        fecha=hoy,
        estado=EstadoAudiencia.PROGRAMADA,
    ).count()

    audiencias_de_la_semana = Audiencia.objects.filter(
        fecha__range=(inicio_semana, fin_semana),
        estado=EstadoAudiencia.PROGRAMADA,
    ).count()

    return render(
        request,
        "dashboard/inicio.html",
        {
            "audiencias_del_dia": audiencias_del_dia,
            "audiencias_de_la_semana": audiencias_de_la_semana,
        },
    )