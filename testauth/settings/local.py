"""
Test settings
"""

########################################################
# local.py settings
# Every setting in base.py can be overloaded by redefining it here.

from .base import *

PACKAGE = "aa_fleet_tool"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/
STATICFILES_DIRS = [
    f"{PACKAGE}/static",
]

# AA ships AaManifestStaticFilesStorage, which requires a built staticfiles
# manifest. Tests that render AA templates would otherwise fail with
# "Missing staticfiles manifest entry". Fall back to the plain storage in tests.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

SITE_URL = "http://localhost:8000"
CSRF_TRUSTED_ORIGINS = [SITE_URL]

# These are required for Django to function properly. Don't touch.
ROOT_URLCONF = "testauth.urls"
WSGI_APPLICATION = "testauth.wsgi.application"
SECRET_KEY = "DUMMY"

# This is where css/images will be placed for your webserver to read
STATIC_ROOT = "/var/www/testauth/static/"

# Change this to change the name of the auth site displayed
# in page titles and the site header.
SITE_NAME = "testauth"

# Change this to enable/disable debug mode, which displays
# useful error messages but can leak sensitive data.
DEBUG = False
LOGGING = None

NOTIFICATIONS_REFRESH_TIME = 30
NOTIFICATIONS_MAX_PER_USER = 50

# Use the USE_MYSQL environment variable to select the database backend (MySQL or SQLite).
if os.environ.get("USE_MYSQL", True) is True:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "temp_allianceauth",
        "USER": "root",
        "PASSWORD": "temp_password_aa_tox_tests",
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {"charset": "utf8mb4"},
    }

# Add any additional apps to this list.
INSTALLED_APPS += [
    PACKAGE,
]

# ------------------------------------------------------------------------------------ #
#
#                                  ESI Settings
#
# ------------------------------------------------------------------------------------ #
ESI_SSO_CLIENT_ID = "dummy"
ESI_SSO_CLIENT_SECRET = "dummy"
ESI_SSO_CALLBACK_URL = "http://127.0.0.1:8000"
ESI_USER_CONTACT_EMAIL = "pberbuir@googlemail.com"

# ------------------------------------------------------------------------------------ #
#
#                                E-Mail Settings
#
# ------------------------------------------------------------------------------------ #
REGISTRATION_VERIFY_EMAIL = False

#######################################
# Add any custom settings below here. #
#######################################
