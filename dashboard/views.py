from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# Importa el decorador que obliga al usuario a iniciar sesión.


@login_required
def inicio(request):
    """
    Vista principal del sistema.

    Muestra el Dashboard únicamente si el usuario
    ha iniciado sesión correctamente.
    """

    return render(request, "dashboard/inicio.html")