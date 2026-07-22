from django.shortcuts import render
# Importa la función render para mostrar una plantilla HTML.


def inicio(request):
    """
    Vista principal del sistema.
    Muestra la pantalla de Inicio (Dashboard).
    """

    return render(request, "dashboard/inicio.html")
