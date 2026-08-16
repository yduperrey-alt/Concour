[app]
title = Concours Finder
package.name = concoursfinder
package.domain = org.concoursfinder

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = tests
version = 1.0

# Dépendances Python nécessaires à l'app (Kivy + réseau/RSS + certificats SSL)
# Version de feedparser figée à 6.0.11 (moderne) : les versions plus
# anciennes (5.x, compatibles Python 2) utilisent l'option `use_2to3` dans
# leur setup.py, que les versions récentes de setuptools ont totalement
# supprimée — ça fait planter la compilation avec l'erreur
# "use_2to3 is invalid" avant même de commencer à construire l'app.
requirements = python3,kivy==2.3.1,feedparser==6.0.11,sgmllib3k,certifi,pyjnius,filetype

orientation = portrait
fullscreen = 0

# Icône / écran de démarrage (optionnels — décommente si tu ajoutes les fichiers)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

# Permissions Android nécessaires : accès internet pour les flux RSS,
# et vérification de l'état réseau avant une recherche.
android.permissions = INTERNET, ACCESS_NETWORK_STATE

android.api = 34
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
