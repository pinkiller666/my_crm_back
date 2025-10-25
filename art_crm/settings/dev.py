from .base import *

SECRET_KEY = 'django-insecure-$k+0r(w4fbsbgot#+^#^boxzq-r#23+vmj$%d*mj8b25xyn^^j'

DEBUG = True
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

CSRF_TRUSTED_ORIGINS = ["http://10.244.22.48:5173"]

CORS_ALLOW_ALL_ORIGINS = True

INSTALLED_APPS += ['devtools']
