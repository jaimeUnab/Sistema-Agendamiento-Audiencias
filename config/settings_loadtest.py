# =====================================================
# CONFIGURACIÓN PARA PRUEBAS DE RENDIMIENTO
# =====================================================
#
# Configuración SOLO para pruebas de carga con Locust + Waitress. NO
# reemplaza config/settings.py (el entorno normal de desarrollo, con
# DEBUG=True y runserver): lo importa completo y sobreescribe
# ÚNICAMENTE lo necesario para simular un entorno "productivo" durante
# la prueba, sin tocar ese archivo.
#
# Se activa exportando la variable de entorno DJANGO_SETTINGS_MODULE
# antes de levantar el servidor de la prueba (Waitress), en una
# consola dedicada:
#
#   $env:DJANGO_SETTINGS_MODULE = "config.settings_loadtest"
#
# manage.py y config/wsgi.py ya usan
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'):
# como setdefault() no sobreescribe una variable ya presente, definir
# esa variable ANTES de invocarlos hace que usen este archivo en su
# lugar, sin necesitar modificar ninguno de los dos.
#
# La consola normal de desarrollo (donde corre "manage.py runserver")
# nunca exporta esta variable, así que sigue usando config.settings
# (DEBUG=True) sin ningún cambio ni paso adicional.

from .settings import *  # noqa

DEBUG = False

# Con DEBUG=False, Django exige ALLOWED_HOSTS explícito: si quedara
# vacío (como en config/settings.py, pensado para runserver con
# DEBUG=True, donde Django permite localhost/127.0.0.1 implícitamente),
# TODAS las peticiones fallarían con "DisallowedHost" (400). Locust y
# cualquier verificación manual apuntarán a localhost/127.0.0.1.
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
