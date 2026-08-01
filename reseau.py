"""
Couche réseau : téléchargement (parallèle + mise en cache) des flux RSS,
transformation des entrées brutes en concours scorés, et ouverture d'un
lien dans le navigateur.
"""

import socket
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import certifi
import feedparser
from kivy.utils import platform

from analyse import (
    _texte_normalise,
    contient_signal_concours,
    detecter_categories_requises,
    est_probablement_une_actualite,
    extraire_date_limite,
    extraire_valeur_estimee,
    nettoyer_html,
    nettoyer_titre_source,
    score_concours,
    deduplique_concours,
)
from constantes import (
    FLUX_RSS,
    JOURS_MAX_ANCIENNETE,
    MAX_FLUX_PARALLELES,
    TIMEOUT_RESEAU,
    DUREE_CACHE_FLUX_SECONDES,
)
from stockage import charger_cache_flux, charger_supprimes, sauvegarder_cache_flux

# Sur Android, Python n'a pas accès aux certificats CA du système : on force
# l'utilisation du magasin de certificats fourni par le paquet "certifi".
ssl._create_default_https_context = lambda *args, **kwargs: ssl.create_default_context(
    cafile=certifi.where()
)

# Sans timeout, un flux RSS injoignable (serveur en panne, réseau mobile
# capricieux...) bloque indéfiniment le thread de recherche : le bouton reste
# désactivé et le message "Recherche en cours..." ne disparaît jamais.
socket.setdefaulttimeout(TIMEOUT_RESEAU)


def _nom_source(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _est_trop_ancien(date_pub_str: str) -> bool:
    """Détecte un article publié il y a longtemps : probablement un concours
    déjà terminé depuis longtemps, même si aucune date limite explicite n'a été trouvée."""
    try:
        dt = parsedate_to_datetime(date_pub_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days > JOURS_MAX_ANCIENNETE
    except Exception:
        return False  # date illisible : on ne filtre pas par prudence


def recuperer_texte_page(url: str, timeout: int = 12, longueur_max: int = 6000):
    """Télécharge la page réelle du concours et renvoie son texte visible
    nettoyé (ou None en cas d'échec réseau/timeout)."""
    import re
    try:
        requete = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) ConcoursFinder/1.0"},
        )
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            brut = reponse.read(300_000)  # limite de sécurité
        page_html = brut.decode("utf-8", errors="ignore")
    except Exception:
        return None

    page_html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page_html)
    return nettoyer_html(page_html)[:longueur_max]


def _telecharger_flux(url: str):
    try:
        flux = feedparser.parse(
            url,
            agent="Mozilla/5.0 (Linux; Android 14; Mobile) ConcoursFinder/1.0"
        )
        return url, flux, None
    except Exception as e:
        return url, None, str(e)


def _extraire_entrees_brutes(flux):
    """Convertit un flux feedparser en simples dicts JSON-compatibles, pour
    pouvoir les mettre en cache sur disque tels quels."""
    entrees = []
    for entree in flux.entries:
        entrees.append({
            "lien": entree.get("link", ""),
            "titre": entree.get("title", "Sans titre"),
            "resume": entree.get("summary", ""),
            "date_pub": entree.get("published", "Date inconnue"),
        })
    return entrees


def recuperer_concours(on_progress=None, forcer_actualisation=False):
    """Télécharge/traite tous les flux RSS et renvoie (resultats, diagnostic).

    Important : cette fonction NE filtre PLUS par préférence utilisateur
    ("catégories à éviter"). Ce filtrage se fait désormais uniquement à
    l'affichage (voir ConcoursFinderApp._appliquer_preferences), pour que
    décocher une préférence restaure immédiatement les concours concernés
    sans avoir besoin de relancer une recherche réseau complète."""
    resultats = []
    vus = set()
    supprimes = charger_supprimes()
    diagnostic = []
    nb_total = len(FLUX_RSS)
    nb_traites = 0
    nb_actualites_ecartees = 0
    nb_depuis_cache = 0

    cache = {} if forcer_actualisation else charger_cache_flux()
    maintenant = time.time()

    def _cache_valide(url):
        entree = cache.get(url)
        if not entree:
            return False
        return (maintenant - entree.get("horodatage", 0)) < DUREE_CACHE_FLUX_SECONDES

    def _traiter_entrees(url, entrees_brutes, statut_http, bozo, bozo_msg, depuis_cache):
        nonlocal nb_actualites_ecartees
        nb_avant = len(resultats)

        for e in entrees_brutes:
            lien = e["lien"]
            if not lien or lien in vus or lien in supprimes:
                continue
            vus.add(lien)

            titre = nettoyer_titre_source(e["titre"])
            resume = e["resume"]
            date_pub = e["date_pub"]

            if _est_trop_ancien(date_pub):
                continue  # probablement un concours terminé depuis longtemps

            # Calculé une seule fois puis réutilisé par toutes les analyses
            # ci-dessous (au lieu de reconcaténer/relowercaser 4 fois le
            # même texte) : gain notable sur une recherche qui traite
            # plusieurs milliers d'entrées au total.
            texte_analyse = _texte_normalise(titre, resume)

            if est_probablement_une_actualite(titre, resume, texte_analyse):
                nb_actualites_ecartees += 1
                continue

            if not contient_signal_concours(titre, resume, texte_analyse):
                # Aucun signal de concours explicite (« concours »,
                # « tirage au sort », « à gagner »...) : très probablement
                # une actualité classique qui cite juste un mot-clé de lot.
                nb_actualites_ecartees += 1
                continue

            score = score_concours(titre, resume, texte_analyse)
            categories_requises = detecter_categories_requises(titre, resume, texte_analyse)

            date_limite_texte, date_limite_obj = extraire_date_limite(f"{titre} {resume}")
            if date_limite_obj and date_limite_obj < date.today():
                continue  # concours déjà terminé, on ne l'affiche pas

            # Bonus de facilité : moins il y a d'actions à réaliser (Instagram,
            # formulaire, création de compte...), mieux c'est noté. Pas de malus
            # si beaucoup d'actions sont demandées : ça reste neutre.
            nb_actions = len(categories_requises)
            score += {0: 4, 1: 2}.get(nb_actions, 0)

            if date_limite_obj:
                jours_restants = (date_limite_obj - date.today()).days
                if 0 <= jours_restants <= 3:
                    score += 6  # se termine très bientôt : priorité
                elif 4 <= jours_restants <= 7:
                    score += 3

            # On ne laisse jamais le score final descendre à 0/négatif à cause
            # de ces ajustements : le concours reste visible, juste moins bien classé.
            score = max(score, 1)

            resultats.append({
                "titre": titre,
                "lien": lien,
                "date_publication": date_pub,
                "date_limite_texte": date_limite_texte,
                "date_limite_obj": date_limite_obj,
                "resume": nettoyer_html(resume),
                "valeur_estimee": extraire_valeur_estimee(f"{titre} {resume}"),
                "categories": categories_requises,
                "score": score,
                "source": url,
            })

        nb_ajoutes = len(resultats) - nb_avant
        tag = " (cache)" if depuis_cache else ""
        detail = f"{url}{tag} -> {nb_ajoutes} entrée(s), http={statut_http}"
        if bozo:
            detail += f", erreur parsing: {bozo_msg}"
        diagnostic.append(detail)

    # --- 1) Flux encore valides en cache : traitement instantané, aucun accès
    #     réseau. C'est ce qui donne l'ouverture quasi-immédiate et économise
    #     à la fois batterie et data mobile. ---
    urls_a_telecharger = []
    for url in FLUX_RSS:
        if _cache_valide(url):
            entree = cache[url]
            nb_traites += 1
            if on_progress:
                on_progress(nb_traites, nb_total, url)
            nb_depuis_cache += 1
            _traiter_entrees(
                url, entree.get("entrees", []), entree.get("statut_http", "?"),
                entree.get("bozo", False), entree.get("bozo_msg", ""), depuis_cache=True,
            )
        else:
            urls_a_telecharger.append(url)

    # --- 2) Le reste : téléchargement en parallèle, comme avant. ---
    if urls_a_telecharger:
        with ThreadPoolExecutor(max_workers=MAX_FLUX_PARALLELES) as executor:
            futures = {executor.submit(_telecharger_flux, url): url for url in urls_a_telecharger}

            for future in as_completed(futures):
                url, flux, erreur = future.result()
                nb_traites += 1
                if on_progress:
                    on_progress(nb_traites, nb_total, url)

                if erreur is not None:
                    diagnostic.append(f"{url} -> exception: {erreur}")
                    continue

                bozo = bool(getattr(flux, "bozo", 0))
                bozo_msg = str(getattr(flux, "bozo_exception", "")) if bozo else ""
                statut_http = flux.get("status", "?") if hasattr(flux, "get") else "?"
                entrees_brutes = _extraire_entrees_brutes(flux)

                cache[url] = {
                    "horodatage": maintenant,
                    "entrees": entrees_brutes,
                    "statut_http": statut_http,
                    "bozo": bozo,
                    "bozo_msg": bozo_msg,
                }
                _traiter_entrees(url, entrees_brutes, statut_http, bozo, bozo_msg, depuis_cache=False)

        sauvegarder_cache_flux(cache)

    resultats.sort(key=lambda c: c["score"], reverse=True)
    nb_avant_dedup = len(resultats)
    resultats = deduplique_concours(resultats)
    nb_doublons = nb_avant_dedup - len(resultats)
    if nb_doublons:
        diagnostic.append(f"{nb_doublons} doublon(s) fusionné(s)")
    if nb_actualites_ecartees:
        diagnostic.append(f"{nb_actualites_ecartees} actualité(s) sans rapport écartée(s)")
    if nb_depuis_cache:
        diagnostic.append(f"{nb_depuis_cache} flux servis depuis le cache (< 30 min, pas de téléchargement)")
    return resultats, diagnostic


def ouvrir_lien(url):
    """Ouvre un lien dans le navigateur (fonctionne sur Android et desktop)."""
    if platform == "android":
        try:
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            currentActivity = cast("android.app.Activity", PythonActivity.mActivity)
            currentActivity.startActivity(intent)
        except Exception as e:
            print(f"Impossible d'ouvrir le lien : {e}")
    else:
        import webbrowser
        webbrowser.open(url)
