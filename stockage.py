"""
Persistance locale : concours supprimés, préférences, favoris, historique,
état de l'app et cache des flux RSS. Tout est stocké en JSON dans le
dossier de données de l'application (user_data_dir de Kivy).
"""

import json
import os

from kivy.app import App

from constantes import (
    FICHIER_CACHE_FLUX,
    FICHIER_ETAT,
    FICHIER_FAVORIS,
    FICHIER_HISTORIQUE,
    FICHIER_PREFERENCES,
    FICHIER_SUPPRIMES,
)


def _chemin_fichier(nom_fichier):
    try:
        dossier = App.get_running_app().user_data_dir
    except Exception:
        dossier = "."
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, nom_fichier)


def _charger_json(nom_fichier, defaut):
    chemin = _chemin_fichier(nom_fichier)
    if not os.path.exists(chemin):
        return defaut
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defaut


def _sauvegarder_json(nom_fichier, donnees, description):
    chemin = _chemin_fichier(nom_fichier)
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Impossible de sauvegarder {description} : {e}")


# --- Concours définitivement supprimés par l'utilisateur ---

def charger_supprimes():
    return set(_charger_json(FICHIER_SUPPRIMES, []))


def sauvegarder_supprimes(liens_supprimes):
    _sauvegarder_json(FICHIER_SUPPRIMES, sorted(liens_supprimes), "les concours supprimés")


# --- Préférences ("catégories à éviter") ---

def charger_preferences():
    """Renvoie {id_categorie: True} pour chaque catégorie que l'utilisateur veut éviter."""
    return _charger_json(FICHIER_PREFERENCES, {})


def sauvegarder_preferences(preferences):
    _sauvegarder_json(FICHIER_PREFERENCES, preferences, "les préférences")


# --- Favoris ---

def charger_favoris():
    """Renvoie la liste des concours mis en favoris (liste de dicts, plus récents en premier)."""
    return _charger_json(FICHIER_FAVORIS, [])


def sauvegarder_favoris(favoris):
    _sauvegarder_json(FICHIER_FAVORIS, favoris, "les favoris")


# --- Historique de consultation ---

def charger_historique():
    """Renvoie la liste des concours consultés (liste de dicts, plus récents en premier)."""
    return _charger_json(FICHIER_HISTORIQUE, [])


def sauvegarder_historique(historique):
    _sauvegarder_json(FICHIER_HISTORIQUE, historique[:200], "l'historique")  # on garde les 200 derniers


# --- État global de l'app (ex: date de dernière recherche) ---

def charger_etat():
    return _charger_json(FICHIER_ETAT, {})


def sauvegarder_etat(etat):
    _sauvegarder_json(FICHIER_ETAT, etat, "l'état de l'application")


# --- Cache des flux RSS déjà téléchargés ---

def charger_cache_flux():
    return _charger_json(FICHIER_CACHE_FLUX, {})


def sauvegarder_cache_flux(cache):
    _sauvegarder_json(FICHIER_CACHE_FLUX, cache, "le cache des flux")
