"""
Django settings for data_refinery_workers project.

Generated by 'django-admin startproject' using Django 1.10.6.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
import sys
from django.core.exceptions import ImproperlyConfigured
from data_refinery_common.utils import get_env_variable, get_env_variable_gracefully


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env_variable('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_env_variable('DJANGO_DEBUG') == "True"

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django_elasticsearch_dsl',
    'data_refinery_common',
    'data_refinery_workers.downloaders',
    'data_refinery_workers.processors',
    'raven.contrib.django.raven_compat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'data_refinery_workers.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'data_refinery_workers.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': get_env_variable('DATABASE_NAME'),
        'USER': get_env_variable('DATABASE_USER'),
        'PASSWORD': get_env_variable('DATABASE_PASSWORD'),
        'HOST': get_env_variable('DATABASE_HOST'),
        'PORT': get_env_variable('DATABASE_PORT'),
        'TEST': {
            # Our environment variables for test have a different
            # database name than the other envs so just use that
            # rather than letting Django munge it.
            'NAME': get_env_variable('DATABASE_NAME')
        }
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': ('django.contrib.auth.password_validation' +
                 '.UserAttributeSimilarityValidator'),
    },
    {
        'NAME': ('django.contrib.auth.password_validation.' +
                 'MinimumLengthValidator'),
    },
    {
        'NAME': ('django.contrib.auth.password_validation' +
                 '.CommonPasswordValidator'),
    },
    {
        'NAME': ('django.contrib.auth.password_validation' +
                 '.NumericPasswordValidator'),
    },
]

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'


# Setting the RAVEN_CONFIG when RAVEN_DSN isn't set will cause the
# following warning:
# /usr/local/lib/python3.6/site-packages/raven/conf/remote.py:91:
# UserWarning: Transport selection via DSN is deprecated. You should
# explicitly pass the transport class to Client() instead.
raven_dsn = get_env_variable_gracefully('RAVEN_DSN', False)
if raven_dsn:
    RAVEN_CONFIG = {
        'dsn': raven_dsn
    }
else:
    # Preven raven from logging about how it's not configured...
    import logging
    raven_logger = logging.getLogger('raven.contrib.django.client.DjangoClient')
    raven_logger.setLevel(logging.CRITICAL)

RUNNING_IN_CLOUD = get_env_variable('RUNNING_IN_CLOUD') == "True"

# Elastic Search
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': 'elasticsearch:9200'
    }
}

if 'test' in sys.argv:
    ELASTICSEARCH_INDEX_NAMES = {
            'data_refinery_common.models.documents': 'experiments_test',
        }
else:
    ELASTICSEARCH_INDEX_NAMES = {
        'data_refinery_common.models.documents': 'experiments',
    }
