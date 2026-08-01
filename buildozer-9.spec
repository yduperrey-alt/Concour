[app]
title = Concours Finder
package.name = concoursfinder
package.domain = org.concoursfinder

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_dirs = tests
version = 1.0

# Dépendances Python nécessaires à l'app (Kivy + réseau/RSS + certificats SSL)
requirements = python3,kivy==2.3.0,feedparser,certifi,pyjnius

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

[buildozer]
log_level = 2
warn_on_root = 1
