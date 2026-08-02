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