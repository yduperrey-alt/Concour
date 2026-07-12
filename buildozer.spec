[app]
title = Concours Finder
package.name = concoursfinder
package.domain = org.concoursfinder

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy,feedparser==6.0.11

orientation = portrait
fullscreen = 0

# Permissions nécessaires (accès Internet pour les flux RSS)
android.permissions = INTERNET

# API Android cibles (ajuste si besoin)
android.api = 36
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
