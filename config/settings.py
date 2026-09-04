from pathlib import Path

# =============================================================================
# RUTA BASE DEL PROYECTO
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================

# Clave secreta utilizada por Django.
# No debe compartirse en un entorno de producción.
SECRET_KEY = 'django-insecure-fa6*h*wqrsn!vu#^$q0h(=#4bi+prqi^hf@r!qk_4#d-$j^-_!'

# Activa el modo de desarrollo.
DEBUG = True

# Equipos autorizados para acceder al sistema.
ALLOWED_HOSTS = []


# =============================================================================
# APLICACIONES INSTALADAS
# =============================================================================

INSTALLED_APPS = [

    # Aplicaciones propias de Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Aplicaciones del proyecto
    'dashboard',
    'usuarios',
    'bloques',
    'competencias',
    'tipos_audiencia',
    'salas',
    'reglas_agendamiento',
    'dias_no_disponibles',
    'causas',
    'audiencias',

]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [

    # Seguridad del sitio
    'django.middleware.security.SecurityMiddleware',

    # Manejo de sesiones
    'django.contrib.sessions.middleware.SessionMiddleware',

    # Funciones comunes de Django
    'django.middleware.common.CommonMiddleware',

    # Protección CSRF
    'django.middleware.csrf.CsrfViewMiddleware',

    # Autenticación de usuarios
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # Sistema de mensajes
    'django.contrib.messages.middleware.MessageMiddleware',

    # Protección contra Clickjacking
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Registro de accesos denegados (403) en RegistroAcceso.
    # Ver usuarios/middleware.py.
    'usuarios.middleware.RegistroAccesoMiddleware',

]


# =============================================================================
# CONFIGURACIÓN DE URLS
# =============================================================================

ROOT_URLCONF = 'config.urls'


# =============================================================================
# PLANTILLAS
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Carpeta donde se almacenan las plantillas generales.
        'DIRS': [BASE_DIR / 'templates'],

        # Permite buscar plantillas dentro de cada aplicación.
        'APP_DIRS': True,

        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# =============================================================================
# WSGI
# =============================================================================

WSGI_APPLICATION = 'config.wsgi.application'


# =============================================================================
# BASE DE DATOS
# =============================================================================

# USER='postgres' es el superusuario de PostgreSQL: apropiado para
# desarrollo local, pero no para un despliegue institucional. Un
# superusuario ignora cualquier privilegio GRANT/REVOKE (por diseño
# de PostgreSQL), así que ninguna restricción de permisos a nivel de
# base de datos tendría efecto contra esta conexión -es, de hecho,
# la razón por la que la protección de RegistroTrazabilidad/
# RegistroAcceso contra UPDATE/DELETE se implementó como un trigger
# (audiencias/migrations/0005_bloquear_modificacion_registrotrazabilidad.py,
# usuarios/migrations/0004_bloquear_modificacion_registroacceso.py) y
# no como un REVOKE-. El despliegue institucional debe crear y usar
# un rol de aplicación sin SUPERUSER, con únicamente los privilegios
# que Django necesita sobre la base "agendamiento".
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'agendamiento',
        'USER': 'postgres',
        'PASSWORD': 'admin25',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# =============================================================================
# VALIDACIÓN DE CONTRASEÑAS
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# =============================================================================
# INTERNACIONALIZACIÓN
# =============================================================================

LANGUAGE_CODE = 'es-cl'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True


# =============================================================================
# ARCHIVOS ESTÁTICOS
# =============================================================================

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# =============================================================================
# TIPO DE CLAVE PRIMARIA
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =====================================================
# MODELO DE USUARIO PERSONALIZADO
# =====================================================

# Indica a Django que utilizará el modelo Usuario
# definido en la aplicación usuarios.

AUTH_USER_MODEL = "usuarios.Usuario"

# =====================================================
# CONFIGURACIÓN DE AUTENTICACIÓN
# =====================================================

# Página donde se solicita el inicio de sesión
LOGIN_URL = "/usuarios/login/"

# Página a la que se redirige después de iniciar sesión
LOGIN_REDIRECT_URL = "/"

# Página a la que se redirige después de cerrar sesión
LOGOUT_REDIRECT_URL = "/usuarios/login/"

# =====================================================
# CIERRE DE SESIÓN POR INACTIVIDAD
# =====================================================

# Tiempo de vida de la sesión, en segundos, contado desde su
# último guardado. Con SESSION_SAVE_EVERY_REQUEST=True (más
# abajo), Django reescribe la sesión -y por lo tanto recalcula
# esta expiración desde "ahora"- en cada request donde se
# accede a request.session, lo que en la práctica ocurre en
# cualquier vista protegida (@login_required/LoginRequiredMixin
# ya evalúan request.user, que internamente lee la sesión). El
# efecto es una ventana deslizante: 15 minutos sin ninguna
# request autenticada expiran la sesión; cualquier actividad
# dentro de esos 15 minutos la renueva.
SESSION_COOKIE_AGE = 900

# Sin esto, Django solo reescribe la sesión cuando su contenido
# cambia (por ejemplo, al iniciar sesión), y SESSION_COOKIE_AGE
# se contaría desde ese único momento, no desde la última
# actividad. Con True, la expiración se recalcula en cada
# request, logrando el comportamiento por inactividad pedido.
SESSION_SAVE_EVERY_REQUEST = True

# Al expirar, Django trata la sesión como inexistente en la
# siguiente request (sin ninguna vista ni middleware adicional):
# request.user pasa a AnonymousUser, y @login_required/
# LoginRequiredMixin redirigen a LOGIN_URL igual que con
# cualquier usuario no autenticado.

# =====================================================
# MENSAJES DEL SISTEMA
# =====================================================

# Django usa el tag "error" para el nivel ERROR, pero
# Bootstrap no define la clase "alert-error" (usa
# "alert-danger"). Se remapea para que las alertas del
# template siempre coincidan con una clase Bootstrap real.
from django.contrib.messages import constants as message_constants

MESSAGE_TAGS = {
    message_constants.ERROR: "danger",
}