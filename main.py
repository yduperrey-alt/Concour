"""
Concours Finder — application Android (Kivy)
Recherche des jeux concours via flux RSS, les classe par score de lot,
et affiche la liste dans une interface tactile.
"""

import difflib
import html
import json
import os
import re
import socket
import ssl
import threading
import urllib.request
import certifi
import feedparser
from datetime import date, datetime, timezone

# Sur Android, Python n'a pas accès aux certificats CA du système : on force
# l'utilisation du magasin de certificats fourni par le paquet "certifi".
ssl._create_default_https_context = lambda *args, **kwargs: ssl.create_default_context(
    cafile=certifi.where()
)

# Sans timeout, un flux RSS injoignable (serveur en panne, réseau mobile
# capricieux...) bloque indéfiniment le thread de recherche : le bouton reste
# désactivé et le message "Recherche en cours..." ne disparaît jamais.
TIMEOUT_RESEAU = 15  # secondes
socket.setdefaulttimeout(TIMEOUT_RESEAU)

from kivy.app import App
from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivy.metrics import dp

# --- Palette de couleurs ---
COULEUR_FOND = (0.07, 0.07, 0.09, 1)
COULEUR_CARTE_A = (0.14, 0.14, 0.17, 1)
COULEUR_CARTE_B = (0.10, 0.10, 0.13, 1)
COULEUR_ACCENT = (0.30, 0.62, 0.55, 1)
COULEUR_ACCENT_FONCE = (0.22, 0.47, 0.42, 1)
COULEUR_ONGLET_INACTIF = (0.18, 0.18, 0.22, 1)
COULEUR_TEXTE = (0.93, 0.93, 0.95, 1)
COULEUR_TEXTE_ATTENUE = (0.65, 0.65, 0.70, 1)
COULEUR_PREMIUM = (0.85, 0.65, 0.13, 1)   # or
COULEUR_MOYEN = (0.30, 0.55, 0.85, 1)     # bleu
COULEUR_BASIQUE = (0.45, 0.45, 0.50, 1)   # gris

Window.clearcolor = COULEUR_FOND

FICHIER_SUPPRIMES = "concours_supprimes.json"
FICHIER_PREFERENCES = "preferences.json"

# --- 1. Sources RSS ---
FLUX_RSS = [
    "https://www.grattweb.fr/rss/rss.xml",
    "https://www.grattweb.fr/rss/rss_etranger.xml",
    "https://www.concours.fr/feed/",
    "https://news.google.com/rss/search?q=%22jeux%20concours%22%20gratuit&hl=fr&gl=FR&ceid=FR:fr",
]

TOP_N = 100

LOTS_PREMIUM = ["voiture", "voyage", "séjour", "iphone", "playstation", "ps5",
                "macbook", "croisière", "week-end", "smartphone", "console", "samsung",
                "android", "display", "pokemon", "tablette", "ipad", "drone", "moto",
                "scooter", "ordinateur portable", "pc portable", "téléviseur", "tv oled",
                "casque vr", "montre connectée", "apple watch", "airpods", "nintendo switch",
                "xbox", "home cinéma", "barre de son"]
LOTS_MOYENS = ["bon d'achat", "carte cadeau", "coffret", "place de cinéma",
               "abonnement", "cosmétique", "yu-gi-oh", "souris", "casque",
               "cuisine", "enceinte", "magic", "one-piece", "informatique",
               "robot cuiseur", "friteuse", "livre", "vélo", "trottinette",
               "jeu de société", "jeu vidéo", "figurine", "vinyle", "parfum",
               "batterie externe", "clavier", "chargeur", "sac à dos", "vêtement",
               "billet", "billets", "entrée", "entrées", "spa", "restaurant"]
LOTS_BASIQUES = ["cadeau", "cadeaux", "lot à gagner", "lots à gagner", "gain",
                  "gains", "prime", "chèque", "chèque cadeau", "argent",
                  "bon plan", "échantillon", "échantillons", "goodies", "gadget"]
MOTS_SANS_ACHAT = ["sans obligation d'achat", "sans achat", "gratuit", "gratuitement"]

# Utilisés uniquement en filet de sécurité : si aucun mot-clé de lot ne matche,
# on vérifie qu'il s'agit bien d'un concours pour éviter un score de 0 sec
# sur une entrée légitime dont le lot n'est simplement pas encore répertorié.
SIGNAUX_CONCOURS = ["concours", "tirage au sort", "gagnez", "à gagner", "jouez et gagnez", "jeu-concours"]

# En français, "concours" désigne aussi un examen/concours de recrutement
# (concours administratif, concours d'entrée...), ce qui fait remonter des
# actualités sans rapport dans le flux Google News. On les écarte, ainsi que
# l'actualité générale qui n'a rien à voir avec un jeu-concours.
MOTS_EXCLUS = [
    "concours de recrutement", "concours d'entrée", "concours administratif",
    "concours de la fonction publique", "concours externe", "concours interne",
    "concours atsem", "concours infirmier", "concours enseignant", "concours agricole",
    "fonction publique", "épreuve écrite", "épreuves écrites", "épreuve orale",
    "candidature", "candidatures", "annales du concours", "poste à pourvoir",
    "offre d'emploi", "offres d'emploi", "classe préparatoire", "prépa concours",
    "élection", "ministre", "gouvernement", "attentat", "procès", "tribunal",
    "manifestation", "grève", "condamné", "accident de la route", "incendie",
]


def est_probablement_une_actualite(titre: str, resume: str) -> bool:
    """Détecte les entrées qui ne sont pas de vrais jeux-concours."""
    texte = f"{titre} {resume}".lower()
    return any(mot in texte for mot in MOTS_EXCLUS)


def score_concours(titre: str, resume: str) -> int:
    texte = f"{titre} {resume}".lower()
    score = 0
    for mot in LOTS_PREMIUM:
        if mot in texte:
            score += 10
    for mot in LOTS_MOYENS:
        if mot in texte:
            score += 5
    for mot in LOTS_BASIQUES:
        if mot in texte:
            score += 2
    for mot in MOTS_SANS_ACHAT:
        if mot in texte:
            score += 3

    if score == 0:
        for mot in SIGNAUX_CONCOURS:
            if mot in texte:
                score = 1
                break

    return score


def nettoyer_html(texte: str) -> str:
    """Retire les balises HTML d'un résumé de flux RSS et décode les entités (&amp; etc.)."""
    if not texte:
        return ""
    texte = re.sub(r"<[^>]+>", " ", texte)
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


# Détection heuristique (mots-clés) de ce qu'il faut probablement fournir pour
# participer. On ne peut pas le savoir avec certitude sans charger la page du
# concours, mais ça donne un bon aperçu à partir du titre/résumé du flux RSS.
# Chaque catégorie a un identifiant stable, utilisé pour le scoring (moins
# d'actions = mieux noté) et pour les préférences utilisateur ("à éviter").
CATEGORIES_PARTICIPATION = [
    ("instagram", ["instagram"], "📸 Suivre / liker sur Instagram"),
    ("facebook", ["facebook"], "👍 Suivre / liker sur Facebook"),
    ("tiktok", ["tiktok"], "🎵 Suivre sur TikTok"),
    ("twitter", ["twitter", "compte x ", " sur x "], "🐦 Suivre sur X (Twitter)"),
    ("newsletter", ["newsletter"], "📩 S'inscrire à la newsletter"),
    ("email", ["e-mail", "email", "adresse mail", "adresse e-mail"], "✉️ Fournir une adresse e-mail"),
    ("nom_prenom", ["nom et prénom", "nom, prénom", "vos coordonnées", "civilité"], "📝 Fournir nom et prénom"),
    ("formulaire", ["formulaire"], "📋 Remplir un formulaire"),
    ("compte", ["créer un compte", "création de compte", "inscription sur le site"], "👤 Créer un compte"),
    ("avis", ["laisser un avis", "avis client"], "⭐ Laisser un avis"),
    ("partage", ["partager", "partage la publication", "partagez"], "🔁 Partager la publication"),
    ("abonnement", ["s'abonner", "abonnement gratuit", "abonnez-vous"], "🔔 S'abonner"),
]

# Informations purement indicatives (pas des "actions" à réaliser, donc ne
# comptent pas dans le calcul de facilité de participation ni dans les préférences).
INDICES_INFO_POSITIFS = [
    (["tirage au sort"], "🎲 Tirage au sort parmi les participants"),
    (["sans obligation d'achat", "sans achat"], "🆓 Sans obligation d'achat"),
    (["gratuit", "gratuitement"], "🆓 Participation gratuite"),
]


def detecter_categories_requises(titre: str, resume: str) -> list:
    """Renvoie les identifiants des catégories d'actions requises détectées (ex: 'instagram')."""
    texte = f"{titre} {resume}".lower()
    return [cid for cid, mots, _libelle in CATEGORIES_PARTICIPATION if any(m in texte for m in mots)]


def detecter_infos_requises(titre: str, resume: str) -> list:
    """Renvoie les libellés lisibles (actions + infos positives) pour l'affichage dans la popup."""
    texte = f"{titre} {resume}".lower()
    trouves = []
    for _cid, mots, libelle in CATEGORIES_PARTICIPATION:
        if any(m in texte for m in mots) and libelle not in trouves:
            trouves.append(libelle)
    for mots, libelle in INDICES_INFO_POSITIFS:
        if any(m in texte for m in mots) and libelle not in trouves:
            trouves.append(libelle)
    return trouves


MOIS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
MOTS_CLE_DATE_LIMITE = [
    "jusqu'au", "jusqu au", "jusqu'à", "avant le", "se termine le",
    "clôture le", "cloture le", "date limite", "fin du concours le",
]
_RE_DATE_NUM = re.compile(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})")
_RE_DATE_LETTRES = re.compile(
    r"(\d{1,2})\s*(" + "|".join(MOIS_FR.keys()) + r")\s*(\d{4})?", re.IGNORECASE
)


def extraire_date_limite(texte: str):
    """Cherche une date limite de participation dans un texte.
    Renvoie (texte_affichable, objet_date) ou (None, None) si rien trouvé."""
    if not texte:
        return None, None
    texte_lower = texte.lower()
    for mot_cle in MOTS_CLE_DATE_LIMITE:
        idx = texte_lower.find(mot_cle)
        if idx == -1:
            continue
        fenetre = texte[idx: idx + 70]

        m = _RE_DATE_NUM.search(fenetre)
        if m:
            jour, mois, annee = m.groups()
            annee = int(annee)
            if annee < 100:
                annee += 2000
            try:
                d = date(annee, int(mois), int(jour))
                return d.strftime("Jusqu'au %d/%m/%Y"), d
            except ValueError:
                pass

        m2 = _RE_DATE_LETTRES.search(fenetre)
        if m2:
            jour, mois_txt, annee = m2.groups()
            mois_num = MOIS_FR.get(mois_txt.lower())
            annee_int = int(annee) if annee else datetime.now().year
            try:
                d = date(annee_int, mois_num, int(jour))
                return f"Jusqu'au {int(jour)} {mois_txt} {annee_int}", d
            except ValueError:
                pass
    return None, None


def recuperer_texte_page(url: str, timeout: int = 12, longueur_max: int = 6000):
    """Télécharge la page réelle du concours et renvoie son texte visible
    nettoyé (ou None en cas d'échec réseau/timeout)."""
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


_RE_SUFFIXE_SITE = re.compile(r"[-–|]\s*[\w.]+\.(com|fr|net|org|be|info)\s*$", re.IGNORECASE)


def normaliser_titre(titre: str) -> str:
    """Normalise un titre pour comparaison (retire le nom de site final, la ponctuation)."""
    t = _RE_SUFFIXE_SITE.sub("", titre.lower())
    t = re.sub(r"[^\wàâäéèêëïîôöùûüç\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def deduplique_concours(resultats: list) -> list:
    """Fusionne les concours quasi-identiques relayés par plusieurs flux :
    ne garde que la première rencontrée (la liste doit déjà être triée par score
    décroissant), qui est donc la mieux notée."""
    gardes = []
    titres_normalises = []
    for c in resultats:
        nt = normaliser_titre(c["titre"])
        if any(difflib.SequenceMatcher(None, nt, existant).ratio() > 0.82 for existant in titres_normalises):
            continue
        gardes.append(c)
        titres_normalises.append(nt)
    return gardes


def chemin_fichier_supprimes():
    """Renvoie un chemin de stockage écrivable (dossier de données de l'appli)."""
    try:
        dossier = App.get_running_app().user_data_dir
    except Exception:
        dossier = "."
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, FICHIER_SUPPRIMES)


def charger_supprimes():
    chemin = chemin_fichier_supprimes()
    if not os.path.exists(chemin):
        return set()
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def sauvegarder_supprimes(liens_supprimes):
    chemin = chemin_fichier_supprimes()
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(sorted(liens_supprimes), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Impossible de sauvegarder les concours supprimés : {e}")


def chemin_fichier_preferences():
    try:
        dossier = App.get_running_app().user_data_dir
    except Exception:
        dossier = "."
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, FICHIER_PREFERENCES)


def charger_preferences():
    """Renvoie {id_categorie: True} pour chaque catégorie que l'utilisateur veut éviter."""
    chemin = chemin_fichier_preferences()
    if not os.path.exists(chemin):
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sauvegarder_preferences(preferences):
    chemin = chemin_fichier_preferences()
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(preferences, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Impossible de sauvegarder les préférences : {e}")


def recuperer_concours(categories_evitees=frozenset()):
    resultats = []
    vus = set()
    supprimes = charger_supprimes()
    diagnostic = []

    for url in FLUX_RSS:
        try:
            flux = feedparser.parse(
                url,
                agent="Mozilla/5.0 (Linux; Android 14; Mobile) ConcoursFinder/1.0"
            )
        except Exception as e:
            diagnostic.append(f"{url} -> exception: {e}")
            continue

        nb_avant = len(resultats)
        bozo = getattr(flux, "bozo", 0)
        bozo_msg = str(getattr(flux, "bozo_exception", "")) if bozo else ""
        statut_http = flux.get("status", "?") if hasattr(flux, "get") else "?"

        for entree in flux.entries:
            lien = entree.get("link", "")
            if not lien or lien in vus or lien in supprimes:
                continue
            vus.add(lien)

            titre = entree.get("title", "Sans titre")
            resume = entree.get("summary", "")
            date_pub = entree.get("published", "Date inconnue")

            if est_probablement_une_actualite(titre, resume):
                continue

            score = score_concours(titre, resume)
            if score == 0:
                # On écarte les entrées qui ne correspondent à aucun lot
                # connu ni à un signal de concours reconnu : pas intéressant
                # à afficher, et ça évite de polluer la liste.
                continue

            categories_requises = detecter_categories_requises(titre, resume)
            if categories_evitees and set(categories_requises) & categories_evitees:
                # L'utilisateur a explicitement demandé à éviter ce type de
                # participation (ex: Instagram) : on écarte complètement l'entrée.
                continue

            # Bonus/malus de facilité : moins il y a d'actions à réaliser
            # (Instagram, formulaire, création de compte...), mieux c'est noté.
            nb_actions = len(categories_requises)
            score += {0: 4, 1: 2, 2: 0, 3: -2}.get(nb_actions, -4)

            date_limite_texte, date_limite_obj = extraire_date_limite(f"{titre} {resume}")
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
                "categories": categories_requises,
                "score": score,
                "source": url,
            })

        nb_ajoutes = len(resultats) - nb_avant
        detail = f"{url} -> {nb_ajoutes} entrée(s), http={statut_http}"
        if bozo:
            detail += f", erreur parsing: {bozo_msg}"
        diagnostic.append(detail)

    resultats.sort(key=lambda c: c["score"], reverse=True)
    nb_avant_dedup = len(resultats)
    resultats = deduplique_concours(resultats)
    nb_doublons = nb_avant_dedup - len(resultats)
    if nb_doublons:
        diagnostic.append(f"{nb_doublons} doublon(s) fusionné(s)")
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


def stylise_bouton(bouton, couleur, rayon=10):
    """Donne à un Button un fond plat arrondi coloré (au lieu du skin Kivy par défaut).
    La couleur peut être changée dynamiquement via bouton.couleur_instr.rgba = ..."""
    bouton.background_color = (0, 0, 0, 0)
    bouton.background_normal = ""
    bouton.background_down = ""

    with bouton.canvas.before:
        instr_couleur = Color(*couleur)
        instr_rect = RoundedRectangle(radius=[dp(rayon)], pos=bouton.pos, size=bouton.size)

    def _sync(inst, *_a):
        instr_rect.pos = inst.pos
        instr_rect.size = inst.size

    bouton.bind(pos=_sync, size=_sync)
    bouton.couleur_instr = instr_couleur
    return bouton


class ConcoursFinderApp(App):
    def build(self):
        self.title = "Concours Finder"
        self.supprimes = charger_supprimes()
        self.preferences = charger_preferences()
        self.resultats_actuels = []
        self.page_actuelle = 1
        root = BoxLayout(orientation="vertical", padding=(dp(14), dp(45), dp(14), dp(14)), spacing=dp(12))

        # --- En-tête ---
        entete = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(46), spacing=dp(8))
        titre_app = Label(
            text="🎁 Concours Finder",
            font_size=dp(24),
            bold=True,
            color=COULEUR_TEXTE,
            halign="left",
            valign="middle",
        )
        titre_app.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        entete.add_widget(titre_app)

        bouton_reglages = Button(text="⚙️", font_size=dp(18), bold=True, color=(1, 1, 1, 1),
                                  size_hint=(None, None), size=(dp(44), dp(44)))
        stylise_bouton(bouton_reglages, COULEUR_ONGLET_INACTIF, rayon=14)
        bouton_reglages.bind(on_press=self._ouvrir_preferences)
        entete.add_widget(bouton_reglages)
        root.add_widget(entete)

        self.bouton_recherche = Button(
            text="🔍  Rechercher les concours",
            font_size=dp(16),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(52),
        )
        stylise_bouton(self.bouton_recherche, COULEUR_ACCENT, rayon=14)
        self.bouton_recherche.bind(on_press=self.lancer_recherche)
        root.add_widget(self.bouton_recherche)

        # --- Onglets de filtrage par score, façon "pilules" ---
        onglets = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(42), spacing=dp(8))
        self.boutons_pages = {}
        libelles_pages = {
            1: "🏆 Top lots",
            2: "🎯 Bons plans",
            3: "🎁 Petits lots",
        }
        for num_page, libelle in libelles_pages.items():
            btn = Button(text=libelle, font_size=dp(13), bold=True, color=(1, 1, 1, 1))
            stylise_bouton(btn, COULEUR_ONGLET_INACTIF, rayon=18)
            btn.bind(on_press=lambda inst, p=num_page: self._changer_page(p))
            onglets.add_widget(btn)
            self.boutons_pages[num_page] = btn
        root.add_widget(onglets)
        self._maj_style_onglets()

        self.statut = Label(
            text="Appuie sur le bouton pour lancer la recherche.",
            size_hint=(1, None),
            height=dp(26),
            font_size=dp(13),
            color=COULEUR_TEXTE_ATTENUE,
            halign="left",
            valign="middle",
        )
        self.statut.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        root.add_widget(self.statut)

        self.scroll = ScrollView()
        self.liste = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=(0, dp(4)))
        self.liste.bind(minimum_height=self.liste.setter("height"))
        self.scroll.add_widget(self.liste)
        root.add_widget(self.scroll)

        return root

    def _ouvrir_preferences(self, instance):
        contenu = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(14))

        sous_titre = Label(
            text="Coche ce que tu ne veux plus voir apparaître :",
            font_size=dp(13), color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(24), halign="left", valign="middle",
        )
        sous_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        contenu.add_widget(sous_titre)

        scroll = ScrollView()
        grille = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        grille.bind(minimum_height=grille.setter("height"))

        cases = {}
        for cid, _mots, libelle in CATEGORIES_PARTICIPATION:
            ligne = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
            case = CheckBox(active=self.preferences.get(cid, False), size_hint=(None, 1), width=dp(38),
                             color=COULEUR_TEXTE)
            lbl = Label(text=libelle, font_size=dp(14), color=COULEUR_TEXTE, halign="left", valign="middle")
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            ligne.add_widget(case)
            ligne.add_widget(lbl)
            grille.add_widget(ligne)
            cases[cid] = case
        scroll.add_widget(grille)
        contenu.add_widget(scroll)

        bouton_enregistrer = Button(text="Enregistrer", bold=True, color=(1, 1, 1, 1),
                                     size_hint_y=None, height=dp(48))
        stylise_bouton(bouton_enregistrer, COULEUR_ACCENT, rayon=12)
        contenu.add_widget(bouton_enregistrer)

        popup = Popup(
            title="Concours à éviter",
            content=contenu,
            size_hint=(0.9, 0.8),
            separator_color=COULEUR_ACCENT,
            title_color=COULEUR_TEXTE,
            background_color=COULEUR_FOND,
            title_size=dp(15),
        )

        def _enregistrer(inst):
            for cid, case in cases.items():
                self.preferences[cid] = case.active
            sauvegarder_preferences(self.preferences)
            self._reappliquer_preferences()
            popup.dismiss()

        bouton_enregistrer.bind(on_press=_enregistrer)
        popup.open()

    def _reappliquer_preferences(self):
        """Filtre immédiatement les résultats déjà chargés selon les nouvelles
        préférences, sans avoir à relancer une recherche réseau complète."""
        categories_evitees = {cid for cid, evite in self.preferences.items() if evite}
        if not categories_evitees or not self.resultats_actuels:
            return
        self.resultats_actuels = [
            c for c in self.resultats_actuels
            if not (set(c.get("categories", [])) & categories_evitees)
        ]
        self._afficher_page()

    def _maj_style_onglets(self):
        for num_page, btn in self.boutons_pages.items():
            actif = num_page == self.page_actuelle
            btn.couleur_instr.rgba = COULEUR_ACCENT if actif else COULEUR_ONGLET_INACTIF

    def _changer_page(self, num_page):
        self.page_actuelle = num_page
        self._maj_style_onglets()
        self._afficher_page()

    def lancer_recherche(self, instance):
        self.bouton_recherche.disabled = True
        self.statut.text = "Recherche en cours..."
        self.liste.clear_widgets()
        threading.Thread(target=self._recherche_thread, daemon=True).start()

    def _recherche_thread(self):
        categories_evitees = {cid for cid, evite in self.preferences.items() if evite}
        try:
            resultats, diagnostic = recuperer_concours(categories_evitees)
        except Exception as e:
            self._afficher_erreur(str(e))
            return
        self._afficher_resultats(resultats, diagnostic)

    @mainthread
    def _afficher_erreur(self, message):
        self.statut.text = f"Erreur : {message}"
        self.bouton_recherche.disabled = False

    @mainthread
    def _afficher_resultats(self, resultats, diagnostic=None):
        # Sécurité supplémentaire : filtre les concours déjà supprimés
        resultats = [c for c in resultats if c["lien"] not in self.supprimes]
        self.resultats_actuels = resultats
        self.dernier_diagnostic = diagnostic

        self.statut.text = (
            f"{len(resultats)} concours trouvés — "
            f"maj le {datetime.now(timezone.utc):%d/%m/%Y %H:%M}"
        )

        if not resultats and diagnostic:
            self.liste.clear_widgets()
            for ligne_diag in diagnostic:
                self.liste.add_widget(Label(
                    text=ligne_diag,
                    size_hint_y=None,
                    height=90,
                    halign="left",
                    valign="top",
                    text_size=(self.liste.width or 300, None),
                    color=(1, 0.5, 0.5, 1),
                ))
            self.bouton_recherche.disabled = False
            return

        self._afficher_page()
        self.bouton_recherche.disabled = False

    def _filtrer_page(self, resultats, num_page):
        if num_page == 1:
            return [c for c in resultats if c["score"] >= 10]
        if num_page == 2:
            return [c for c in resultats if 5 <= c["score"] <= 9]
        return [c for c in resultats if c["score"] < 5]

    def _afficher_page(self):
        self.liste.clear_widgets()
        page = self._filtrer_page(self.resultats_actuels, self.page_actuelle)

        libelles = {1: "🏆 Top lots", 2: "🎯 Bons plans", 3: "🎁 Petits lots"}
        self.statut.text = (
            f"{len(self.resultats_actuels)} concours au total — "
            f"{len(page)} sur cette page ({libelles[self.page_actuelle]})"
        )

        for i, c in enumerate(page, 1):
            self._ajouter_ligne_concours(i, c)

    def _ajouter_ligne_concours(self, i, c):
        ligne = BoxLayout(orientation="horizontal", size_hint_y=None, spacing=dp(10),
                           padding=(dp(10), dp(10), dp(10), dp(10)))

        # Alternance de couleur de fond (carte arrondie) pour distinguer les lignes
        with ligne.canvas.before:
            couleur_fond = COULEUR_CARTE_A if i % 2 == 0 else COULEUR_CARTE_B
            Color(*couleur_fond)
            rect = RoundedRectangle(radius=[dp(12)], pos=ligne.pos, size=ligne.size)
        ligne.bind(pos=lambda inst, val: setattr(rect, "pos", inst.pos))
        ligne.bind(size=lambda inst, val: setattr(rect, "size", inst.size))

        case = CheckBox(size_hint=(None, 1), width=dp(40), color=COULEUR_TEXTE)
        case.bind(active=lambda inst, valeur, lien=c["lien"], ligne=ligne:
                  self._supprimer_concours(lien, ligne) if valeur else None)
        ligne.add_widget(case)

        # Contenu vertical : badge de score + titre
        contenu = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)

        score = c["score"]
        if score >= 10:
            couleur_score, libelle_score = COULEUR_PREMIUM, "🏆"
        elif score >= 5:
            couleur_score, libelle_score = COULEUR_MOYEN, "🎯"
        else:
            couleur_score, libelle_score = COULEUR_BASIQUE, "🎁"

        badge = Label(
            text=f"{libelle_score} {score} pts",
            font_size=dp(12),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(72), dp(22)),
            halign="center",
            valign="middle",
        )
        badge.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        with badge.canvas.before:
            Color(*couleur_score)
            badge_rect = RoundedRectangle(radius=[dp(11)], pos=badge.pos, size=badge.size)
        badge.bind(pos=lambda inst, val: setattr(badge_rect, "pos", inst.pos))
        badge.bind(size=lambda inst, val: setattr(badge_rect, "size", inst.size))
        ligne_badge = BoxLayout(size_hint_y=None, height=dp(24))
        ligne_badge.add_widget(badge)

        date_obj = c.get("date_limite_obj")
        if date_obj:
            jours_restants = (date_obj - date.today()).days
            if 0 <= jours_restants <= 5:
                ligne_badge.add_widget(BoxLayout(size_hint=(None, 1), width=dp(6)))
                texte_urgence = "⏰ Dernier jour" if jours_restants == 0 else f"⏰ J-{jours_restants}"
                urgence = Label(
                    text=texte_urgence,
                    font_size=dp(11),
                    bold=True,
                    color=(1, 1, 1, 1),
                    size_hint=(None, None),
                    size=(dp(86), dp(22)),
                    halign="center",
                    valign="middle",
                )
                urgence.bind(size=lambda inst, val: setattr(inst, "text_size", val))
                with urgence.canvas.before:
                    Color(0.80, 0.25, 0.25, 1)
                    urgence_rect = RoundedRectangle(radius=[dp(11)], pos=urgence.pos, size=urgence.size)
                urgence.bind(pos=lambda inst, val: setattr(urgence_rect, "pos", inst.pos))
                urgence.bind(size=lambda inst, val: setattr(urgence_rect, "size", inst.size))
                ligne_badge.add_widget(urgence)

        ligne_badge.add_widget(BoxLayout())  # pousse les badges à gauche
        contenu.add_widget(ligne_badge)

        item = Button(
            text=c["titre"],
            halign="left",
            valign="top",
            size_hint_y=None,
            font_size=dp(15),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            color=COULEUR_TEXTE,
        )

        def _update_text_size(instance, width, item=item):
            item.text_size = (width - dp(6), None)

        def _update_hauteurs(instance, texture_size, ligne=ligne, contenu=contenu, item=item):
            item.height = texture_size[1]
            contenu.height = texture_size[1] + dp(24)
            ligne.height = texture_size[1] + dp(24) + dp(20)

        item.bind(width=_update_text_size)
        item.bind(texture_size=_update_hauteurs)
        item.bind(on_press=lambda inst, c=c: self._afficher_details(c))
        contenu.add_widget(item)
        ligne.add_widget(contenu)

        self.liste.add_widget(ligne)

    def _afficher_details(self, c):
        """Popup listant les conditions probables de participation, avec un lien vers le concours.
        Affiche d'abord ce qu'on peut déduire du résumé RSS, puis vérifie la vraie
        page du concours en tâche de fond pour affiner (ou confirmer) les infos."""
        contenu = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))

        label_date = Label(
            text=f"⏰ {c['date_limite_texte']}" if c.get("date_limite_texte") else "",
            font_size=dp(13), bold=True, color=(0.90, 0.45, 0.35, 1),
            size_hint_y=None, height=dp(22) if c.get("date_limite_texte") else 0,
            halign="left", valign="middle",
        )
        label_date.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        contenu.add_widget(label_date)

        statut_verif = Label(
            text="🔄 Vérification des informations sur la page du concours...",
            font_size=dp(12), color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(20), halign="left", valign="middle",
        )
        statut_verif.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        contenu.add_widget(statut_verif)

        sous_titre = Label(
            text="Ce qu'il faudra probablement fournir :",
            font_size=dp(13), bold=True, color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(24), halign="left", valign="middle",
        )
        sous_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        contenu.add_widget(sous_titre)

        bloc_infos = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        bloc_infos.bind(minimum_height=bloc_infos.setter("height"))
        contenu.add_widget(bloc_infos)

        infos_affichees = set()

        def _ajouter_info(libelle):
            if libelle in infos_affichees:
                return
            infos_affichees.add(libelle)
            lbl = Label(
                text=libelle, font_size=dp(14), color=COULEUR_TEXTE,
                size_hint_y=None, height=dp(26), halign="left", valign="middle",
            )
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            bloc_infos.add_widget(lbl)

        for libelle in detecter_infos_requises(c["titre"], c.get("resume", "")):
            _ajouter_info(libelle)

        resume_texte = c.get("resume", "")
        if resume_texte:
            separateur = Label(
                text="Résumé :", font_size=dp(13), bold=True, color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(22), halign="left", valign="middle",
            )
            separateur.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(separateur)

            scroll_resume = ScrollView(size_hint=(1, 1))
            resume_lbl = Label(
                text=resume_texte, font_size=dp(13), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, halign="left", valign="top",
            )
            resume_lbl.bind(width=lambda inst, w: setattr(resume_lbl, "text_size", (w, None)))
            resume_lbl.bind(texture_size=lambda inst, ts: setattr(resume_lbl, "height", ts[1]))
            scroll_resume.add_widget(resume_lbl)
            contenu.add_widget(scroll_resume)

        boutons = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        bouton_ouvrir = Button(text="🔗 Voir la page du concours", bold=True, color=(1, 1, 1, 1))
        stylise_bouton(bouton_ouvrir, COULEUR_ACCENT, rayon=12)
        bouton_fermer = Button(text="Fermer", bold=True, color=(1, 1, 1, 1))
        stylise_bouton(bouton_fermer, COULEUR_ONGLET_INACTIF, rayon=12)
        boutons.add_widget(bouton_ouvrir)
        boutons.add_widget(bouton_fermer)
        contenu.add_widget(boutons)

        popup = Popup(
            title=c["titre"],
            content=contenu,
            size_hint=(0.92, 0.85),
            separator_color=COULEUR_ACCENT,
            title_color=COULEUR_TEXTE,
            background_color=COULEUR_FOND,
            title_size=dp(15),
        )
        bouton_ouvrir.bind(on_press=lambda inst: ouvrir_lien(c["lien"]))
        bouton_fermer.bind(on_press=lambda inst: popup.dismiss())
        popup.open()

        # Vérification en tâche de fond : on va chercher la vraie page du concours
        # pour affiner les infos (plus fiable qu'un simple résumé RSS tronqué).
        threading.Thread(
            target=self._verifier_page_concours,
            args=(c, statut_verif, label_date, _ajouter_info),
            daemon=True,
        ).start()

    def _verifier_page_concours(self, c, statut_verif, label_date, ajouter_info):
        texte_page = recuperer_texte_page(c["lien"])
        if texte_page is None:
            self._maj_verification(statut_verif, label_date, None, None, echec=True)
            return
        nouvelles_infos = detecter_infos_requises(c["titre"], texte_page)
        date_texte, _date_obj = extraire_date_limite(f"{c.get('resume', '')} {texte_page}")
        self._maj_verification(statut_verif, label_date, nouvelles_infos, date_texte, echec=False,
                                ajouter_info=ajouter_info)

    @mainthread
    def _maj_verification(self, statut_verif, label_date, nouvelles_infos, date_texte, echec, ajouter_info=None):
        if echec:
            statut_verif.text = "⚠️ Page injoignable pour vérification — utilise le lien ci-dessous."
            statut_verif.color = (0.85, 0.55, 0.25, 1)
            return

        statut_verif.text = "✅ Informations vérifiées sur la page du concours"
        statut_verif.color = (0.35, 0.70, 0.45, 1)
        for libelle in nouvelles_infos:
            ajouter_info(libelle)
        if date_texte and not label_date.text:
            label_date.text = f"⏰ {date_texte}"
            label_date.height = dp(22)

    def _supprimer_concours(self, lien, ligne):
        """Coché = suppression définitive du concours de la liste et du stockage."""
        self.supprimes.add(lien)
        sauvegarder_supprimes(self.supprimes)
        self.resultats_actuels = [c for c in self.resultats_actuels if c["lien"] != lien]
        self.liste.remove_widget(ligne)


if __name__ == "__main__":
    ConcoursFinderApp().run()
