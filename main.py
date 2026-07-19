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
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
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
TIMEOUT_RESEAU = 10  # secondes
socket.setdefaulttimeout(TIMEOUT_RESEAU)

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform
from kivy.metrics import dp

# --- Palette de couleurs — identité "streaming" (Netflix/Spotify) ---
# Fond quasi-noir + cartes légèrement plus claires pour un fort effet de
# profondeur, un unique accent vert émeraude, et l'or réservé aux gros lots
# uniquement (pour qu'il garde tout son impact visuel).
COULEUR_FOND = (0.067, 0.067, 0.067, 1)          # #111111
COULEUR_CARTE_A = (0.118, 0.118, 0.118, 1)       # #1E1E1E
COULEUR_CARTE_B = (0.118, 0.118, 0.118, 1)       # même teinte : grille uniforme, pas de zébrage
COULEUR_CARTE_BORDURE = (0.20, 0.20, 0.20, 1)    # liseré discret pour détacher les cartes du fond
COULEUR_ACCENT = (0.298, 0.686, 0.314, 1)        # #4CAF50 — vert émeraude
COULEUR_ACCENT_FONCE = (0.220, 0.557, 0.235, 1)  # #388E3C — variante pressée/bordure
COULEUR_ONGLET_INACTIF = (0.16, 0.16, 0.16, 1)
COULEUR_TEXTE = (0.96, 0.96, 0.96, 1)
COULEUR_TEXTE_ATTENUE = (0.62, 0.62, 0.62, 1)
COULEUR_PREMIUM = (0.831, 0.686, 0.216, 1)       # #D4AF37 — or, réservé aux gros lots
COULEUR_MOYEN = (0.149, 0.651, 0.604, 1)         # sarcelle — reste dans la famille vert/émeraude
COULEUR_BASIQUE = (0.42, 0.42, 0.42, 1)          # gris neutre
COULEUR_URGENCE = (0.86, 0.25, 0.24, 1)          # rouge alerte (deadline proche)

# Icônes en ASCII pur uniquement. Les caractères Unicode "symboles" (★ ♥ ✕ →)
# ne sont PAS inclus dans la police embarquée par Kivy sur Android : ils
# s'affichent en carré vide (tofu). L'ASCII, lui, est garanti dans absolument
# toutes les polices, sur tous les appareils, sans exception.
ICONE_FAVORI_PLEIN = "FAV"
ICONE_FAVORI_VIDE = "+"
ICONE_ETOILE = "*"
ICONE_FERMER = "X"
ICONE_FLECHE = ">"

Window.clearcolor = COULEUR_FOND

FICHIER_SUPPRIMES = "concours_supprimes.json"
FICHIER_PREFERENCES = "preferences.json"
FICHIER_FAVORIS = "favoris.json"
FICHIER_HISTORIQUE = "historique.json"
FICHIER_ETAT = "etat_app.json"



# --- 1. Sources RSS ---

FLUX_RSS = [
    # --- Sites dédiés aux jeux-concours ---
    "https://www.grattweb.fr/rss/rss.xml",
    "https://www.grattweb.fr/rss/rss_etranger.xml",
    "https://www.concours.fr/feed/",

    # NOTE : les flux de presse généraliste (PlayStation Blog, Xbox News, Steam
    # News, IGN, JeuxActu, Gameblog...) ont été retirés. Ce sont des flux
    # d'actualité pure : leurs articles parlent de sorties de jeux, tests,
    # mises à jour... et contiennent très souvent un mot-clé de lot (« PS5 »,
    # « Xbox », « Samsung »...) sans qu'il s'agisse d'un concours. Les
    # requêtes Google Actualités ciblées ci-dessous (« marque + concours »)
    # couvrent déjà les vrais concours organisés par ces mêmes marques,
    # sans le bruit des articles d'actualité générale.

    # --- Google Actualités (import du fichier OPML fourni) ---
    # --- Mots-clés génériques ---
    "https://news.google.com/rss/search?q=%22jeu+concours%22&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=%22instant+gagnant%22&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=%22tirage+au+sort%22&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=gagnez&hl=fr&gl=FR&ceid=FR:fr",

    # --- Grande distribution ---
    "https://news.google.com/rss/search?q=Carrefour+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=E.Leclerc+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Lidl+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Auchan+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Intermarch%C3%A9+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Super+U+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Monoprix+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Casino+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- High-tech / e-commerce ---
    "https://news.google.com/rss/search?q=Fnac+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Darty+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Boulanger+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Cdiscount+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Amazon+France+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Divertissement / médias ---
    "https://news.google.com/rss/search?q=Disney+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Pixar+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Marvel+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=TF1+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=M6+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=France+TV+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=NRJ+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=RTL+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Europe+1+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=RMC+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Jeux vidéo ---
    "https://news.google.com/rss/search?q=PlayStation+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Xbox+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Nintendo+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Steam+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Epic+Games+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Ubisoft+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=EA+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Riot+Games+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Blizzard+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Rockstar+Games+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Jouets ---
    "https://news.google.com/rss/search?q=LEGO+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Mattel+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Hasbro+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Confiserie / boissons ---
    "https://news.google.com/rss/search?q=Kinder+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Haribo+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Nutella+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Milka+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Coca-Cola+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Pepsi+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Red+Bull+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Oreo+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=LU+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Automobile ---
    "https://news.google.com/rss/search?q=Michelin+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Renault+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Peugeot+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Citro%C3%ABn+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Dacia+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Électronique / informatique ---
    "https://news.google.com/rss/search?q=Samsung+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=LG+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Sony+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Asus+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Acer+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=HP+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Dell+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Lenovo+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Télécom / streaming ---
    "https://news.google.com/rss/search?q=Orange+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=SFR+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Free+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Bouygues+Telecom+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Canal%2B+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Netflix+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Prime+Video+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Disney%2B+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Sport / beauté ---
    "https://news.google.com/rss/search?q=Decathlon+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Intersport+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Go+Sport+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Sephora+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Yves+Rocher+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Nocib%C3%A9+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=L%27Or%C3%A9al+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Restauration rapide ---
    "https://news.google.com/rss/search?q=KFC+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=McDonald%27s+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Burger+King+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Domino%27s+Pizza+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Bricolage / déco ---
    "https://news.google.com/rss/search?q=IKEA+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Leroy+Merlin+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Castorama+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Brico+D%C3%A9p%C3%B4t+concours&hl=fr&gl=FR&ceid=FR:fr",

    # --- Voyage ---
    "https://news.google.com/rss/search?q=Air+France+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=SNCF+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Accor+concours&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Pierre+%26+Vacances+concours&hl=fr&gl=FR&ceid=FR:fr",
]

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

    # Actualité jeux vidéo / high-tech générale (tests, sorties, patchs...),
    # fréquemment relayée par les flux de presse et qui contient souvent un
    # mot-clé de lot (« PS5 », « Xbox »...) sans être un jeu-concours.
    "notre test", "notre avis", "test complet", "bande-annonce", "bande annonce",
    "trailer", "date de sortie", "sortie le", "sortie mondiale", "disponible dès",
    "précommande", "précommandes", "mise à jour", "patch note", "patch notes",
    "chiffres de vente", "critique du film", "critique cinéma", "interview",
    "keynote", "conférence de presse", "résultats financiers", "cours de bourse",
    "rappel produit", "rappel de produit",
]


def est_probablement_une_actualite(titre: str, resume: str) -> bool:
    """Détecte les entrées qui ne sont pas de vrais jeux-concours."""
    texte = f"{titre} {resume}".lower()
    return any(mot in texte for mot in MOTS_EXCLUS)


def contient_signal_concours(titre: str, resume: str) -> bool:
    """Un mot-clé de lot (ex: 'PS5', 'Samsung') ne suffit PAS à lui seul à
    prouver qu'il s'agit d'un jeu-concours : une actualité jeux vidéo ou
    high-tech classique contient souvent ces mêmes mots. On exige donc en
    plus la présence d'un vrai signal de concours (« concours », « tirage
    au sort », « à gagner »...) avant même de calculer un score. C'est ce
    filtre qui écarte l'essentiel des actualités qui se glissaient encore
    dans les résultats."""
    texte = f"{titre} {resume}".lower()
    return any(mot in texte for mot in SIGNAUX_CONCOURS)


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
        # On sait déjà (appelant) qu'un signal de concours est présent :
        # on donne un score plancher même si aucun lot connu n'est cité.
        score = 1

    return score


def nettoyer_html(texte: str) -> str:
    """Retire les balises HTML d'un résumé de flux RSS et décode les entités (&amp; etc.)."""
    if not texte:
        return ""
    texte = re.sub(r"<[^>]+>", " ", texte)
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


# Beaucoup de flux (EchantillonsClub, ActuGaming, Frandroid, Ouest France...)
# ajoutent le nom du site tout à la fin du titre, séparé par un tiret ou une
# barre verticale (ex: "Jeu XYZ à gagner - EchantillonsClub.com"). On le retire
# pour un affichage plus propre, sans toucher au reste du titre.
_RE_SUFFIXE_TITRE = re.compile(r"\s*[-–|]\s*([^-–|]{2,45})$")
_MOTS_INDIQUANT_UN_VRAI_TITRE = ("gratuit", "gagner", "gagnez", "lot", "concours", "offert", "€", "%")


def nettoyer_titre_source(titre: str) -> str:
    """Retire le nom du site source ajouté en fin de titre par certains flux."""
    m = _RE_SUFFIXE_TITRE.search(titre)
    if not m:
        return titre
    suffixe = m.group(1).strip()
    if len(suffixe) > 45 or any(ch.isdigit() for ch in suffixe):
        return titre  # trop long ou contient un chiffre : fait probablement partie du titre
    suffixe_lower = suffixe.lower()
    if any(mot in suffixe_lower for mot in _MOTS_INDIQUANT_UN_VRAI_TITRE):
        return titre  # semble faire partie du titre du concours, pas un nom de site
    reste = titre[: m.start()].strip()
    if len(reste) < 15:
        return titre  # trop court pour être sûr, on ne coupe pas
    return reste


# Détection heuristique (mots-clés) de ce qu'il faut probablement fournir pour
# participer. On ne peut pas le savoir avec certitude sans charger la page du
# concours, mais ça donne un bon aperçu à partir du titre/résumé du flux RSS.
# Chaque catégorie a un identifiant stable, utilisé pour le scoring (moins
# d'actions = mieux noté) et pour les préférences utilisateur ("à éviter").
CATEGORIES_PARTICIPATION = [
    ("instagram", ["instagram"], "Suivre / liker sur Instagram"),
    ("facebook", ["facebook"], "Suivre / liker sur Facebook"),
    ("tiktok", ["tiktok"], "Suivre sur TikTok"),
    ("twitter", ["twitter", "compte x ", " sur x "], "Suivre sur X (Twitter)"),
    ("newsletter", ["newsletter"], "S'inscrire à la newsletter"),
    ("email", ["e-mail", "email", "adresse mail", "adresse e-mail"], "Fournir une adresse e-mail"),
    ("nom_prenom", ["nom et prénom", "nom, prénom", "vos coordonnées", "civilité"], "Fournir nom et prénom"),
    ("formulaire", ["formulaire"], "Remplir un formulaire"),
    ("compte", ["créer un compte", "création de compte", "inscription sur le site"], "Créer un compte"),
    ("avis", ["laisser un avis", "avis client"], "Laisser un avis"),
    ("partage", ["partager", "partage la publication", "partagez"], "Partager la publication"),
    ("abonnement", ["s'abonner", "abonnement gratuit", "abonnez-vous"], "S'abonner"),
]

# Informations purement indicatives (pas des "actions" à réaliser, donc ne
# comptent pas dans le calcul de facilité de participation ni dans les préférences).
INDICES_INFO_POSITIFS = [
    (["tirage au sort"], "Tirage au sort parmi les participants"),
    (["sans obligation d'achat", "sans achat"], "Sans obligation d'achat"),
    (["gratuit", "gratuitement"], "Participation gratuite"),
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


_RE_VALEUR_EUROS = re.compile(
    r"(\d{1,3}(?:[ .]\d{3})*|\d+)(?:,(\d+))?\s?(?:€|euros?)", re.IGNORECASE
)


def extraire_valeur_estimee(texte: str):
    """Cherche un montant en euros dans le texte (ex: "d'une valeur de 550€")
    et renvoie le plus élevé trouvé, formaté pour l'affichage (ex: "550 €").
    Renvoie None si aucun montant plausible n'est trouvé."""
    if not texte:
        return None
    meilleure_valeur = None
    for m in _RE_VALEUR_EUROS.finditer(texte):
        partie_entiere = m.group(1).replace(" ", "").replace(".", "")
        try:
            valeur = float(partie_entiere)
            if m.group(2):
                valeur += float(f"0.{m.group(2)}")
        except ValueError:
            continue
        # On ignore les montants dérisoires (ex: "1€ le ticket") et les
        # montants aberrants (probablement une autre info mal détectée).
        if valeur < 5 or valeur > 500000:
            continue
        if meilleure_valeur is None or valeur > meilleure_valeur:
            meilleure_valeur = valeur
    if meilleure_valeur is None:
        return None
    if meilleure_valeur == int(meilleure_valeur):
        texte_valeur = f"{int(meilleure_valeur):,}".replace(",", " ")
    else:
        texte_valeur = f"{meilleure_valeur:,.2f}".replace(",", " ")
    return f"{texte_valeur} €"


def etoiles_pour_score(score: int) -> int:
    """Convertit le score interne en une note visuelle de 1 à 5 étoiles."""
    if score >= 16:
        return 5
    elif score >= 10:
        return 4
    elif score >= 6:
        return 3
    elif score >= 3:
        return 2
    return 1


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


def _chemin_fichier(nom_fichier):
    try:
        dossier = App.get_running_app().user_data_dir
    except Exception:
        dossier = "."
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, nom_fichier)


def charger_favoris():
    """Renvoie la liste des concours mis en favoris (liste de dicts, plus récents en premier)."""
    try:
        with open(_chemin_fichier(FICHIER_FAVORIS), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def sauvegarder_favoris(favoris):
    try:
        with open(_chemin_fichier(FICHIER_FAVORIS), "w", encoding="utf-8") as f:
            json.dump(favoris, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Impossible de sauvegarder les favoris : {e}")


def charger_historique():
    """Renvoie la liste des concours consultés (liste de dicts, plus récents en premier)."""
    try:
        with open(_chemin_fichier(FICHIER_HISTORIQUE), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def sauvegarder_historique(historique):
    try:
        with open(_chemin_fichier(FICHIER_HISTORIQUE), "w", encoding="utf-8") as f:
            json.dump(historique[:200], f, ensure_ascii=False, indent=2)  # on garde les 200 derniers
    except Exception as e:
        print(f"Impossible de sauvegarder l'historique : {e}")


def charger_etat():
    try:
        with open(_chemin_fichier(FICHIER_ETAT), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sauvegarder_etat(etat):
    try:
        with open(_chemin_fichier(FICHIER_ETAT), "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Impossible de sauvegarder l'état de l'application : {e}")


def _nom_source(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


MAX_FLUX_PARALLELES = 18  # plus de flux à la fois = recherche nettement plus rapide
                           # (le nombre de flux a aussi été réduit, donc pas plus agressif au global)
JOURS_MAX_ANCIENNETE = 45  # au-delà, l'article est probablement un concours déjà terminé


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


FICHIER_CACHE_FLUX = "cache_flux.json"
DUREE_CACHE_FLUX_SECONDES = 30 * 60  # un flux téléchargé il y a moins de 30 min n'est pas retéléchargé


def charger_cache_flux():
    try:
        with open(_chemin_fichier(FICHIER_CACHE_FLUX), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sauvegarder_cache_flux(cache):
    try:
        with open(_chemin_fichier(FICHIER_CACHE_FLUX), "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"Impossible de sauvegarder le cache des flux : {e}")


def recuperer_concours(categories_evitees=frozenset(), on_progress=None, forcer_actualisation=False):
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

            if est_probablement_une_actualite(titre, resume):
                nb_actualites_ecartees += 1
                continue

            if not contient_signal_concours(titre, resume):
                # Aucun signal de concours explicite (« concours »,
                # « tirage au sort », « à gagner »...) : très probablement
                # une actualité classique qui cite juste un mot-clé de lot.
                nb_actualites_ecartees += 1
                continue

            score = score_concours(titre, resume)

            categories_requises = detecter_categories_requises(titre, resume)
            if categories_evitees and set(categories_requises) & categories_evitees:
                # L'utilisateur a explicitement demandé à éviter ce type de
                # participation (ex: Instagram) : on écarte complètement l'entrée.
                continue

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


def infos_palier(score: int):
    """Renvoie (libellé, couleur, icône) selon le palier de score du concours.
    Centralise la hiérarchie visuelle façon "streaming" : l'or n'est utilisé
    que pour les vrais gros lots, pour garder tout son impact."""
    if score >= 10:
        return "TOP LOT", COULEUR_PREMIUM, ICONE_ETOILE
    elif score >= 5:
        return "BON PLAN", COULEUR_MOYEN, ""
    return "PETIT LOT", COULEUR_BASIQUE, ""


def _widget_separateur():
    """Fine ligne horizontale discrète, utilisée pour séparer les sections
    de la fiche concours (valeur, actions, échéance...)."""
    conteneur = Widget(size_hint_y=None, height=dp(13))
    with conteneur.canvas:
        Color(*COULEUR_CARTE_BORDURE)
        trait = Rectangle(pos=(conteneur.x, conteneur.y + dp(6)), size=(conteneur.width, dp(1)))

    def _sync(inst, *_a):
        trait.pos = (inst.x, inst.y + dp(6))
        trait.size = (inst.width, dp(1))

    conteneur.bind(pos=_sync, size=_sync)
    return conteneur


class ConcoursFinderApp(App):
    TAILLE_LOT = 25  # nombre de cartes affichées à la fois (perf sur les grosses listes)

    def build(self):
        self.title = "Concours Finder"
        self.supprimes = charger_supprimes()
        self.preferences = charger_preferences()
        self.favoris = charger_favoris()
        self.historique = charger_historique()
        self.etat = charger_etat()
        self.resultats_actuels = []
        self.page_actuelle = 1
        self.nb_affiches = self.TAILLE_LOT
        self._cache_pages = {}  # évite de retélécharger une page déjà vérifiée dans la session
        self._lien_details_courant = None
        self._debounce_recherche = None
        root = BoxLayout(orientation="vertical", padding=(dp(14), dp(42), dp(14), dp(12)), spacing=dp(10))

        # --- En-tête façon "streaming" : titre + accroche + accès rapides (compact) ---
        entete = BoxLayout(orientation="vertical", size_hint=(1, None), height=dp(84), spacing=dp(4))

        ligne_titre = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(28), spacing=dp(8))
        accent_titre = Widget(size_hint=(None, None), size=(dp(4), dp(24)))
        with accent_titre.canvas:
            Color(*COULEUR_ACCENT)
            accent_rect = RoundedRectangle(radius=[dp(2)], pos=accent_titre.pos, size=accent_titre.size)
        accent_titre.bind(pos=lambda inst, val: setattr(accent_rect, "pos", inst.pos))
        ligne_titre.add_widget(accent_titre)

        titre_app = Label(
            text="Concours Finder",
            font_size=dp(20),
            bold=True,
            color=COULEUR_TEXTE,
            halign="left",
            valign="middle",
        )
        titre_app.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        ligne_titre.add_widget(titre_app)
        entete.add_widget(ligne_titre)

        accroche = Label(
            text="Les meilleurs concours du moment, triés pour toi",
            font_size=dp(12),
            color=COULEUR_TEXTE_ATTENUE,
            size_hint=(1, None),
            height=dp(18),
            halign="left",
            valign="middle",
        )
        accroche.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        entete.add_widget(accroche)

        ligne_actions = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(32), spacing=dp(6))
        for texte_btn, icone_btn, callback in (
            ("Favoris", "", self._ouvrir_favoris),
            ("Historique", "", self._ouvrir_historique),
            ("Options", "", self._ouvrir_preferences),
        ):
            btn = Button(text=texte_btn, font_size=dp(11), bold=True, color=COULEUR_TEXTE,
                         size_hint=(1, 1))
            stylise_bouton(btn, COULEUR_ONGLET_INACTIF, rayon=15)
            btn.bind(on_press=callback)
            ligne_actions.add_widget(btn)
        entete.add_widget(ligne_actions)
        root.add_widget(entete)

        self.bouton_recherche = Button(
            text="Rechercher les concours",
            font_size=dp(15),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(46),
        )
        stylise_bouton(self.bouton_recherche, COULEUR_ACCENT, rayon=13)
        self.bouton_recherche.bind(on_press=self.lancer_recherche)
        root.add_widget(self.bouton_recherche)

        # --- Recherche par mot-clé (avec bouton pour effacer) ---
        ligne_recherche = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(40), spacing=dp(6))
        self.champ_recherche = TextInput(
            hint_text="Filtrer par mot-clé (ex: voyage, PS5, iPhone...)",
            multiline=False,
            size_hint=(1, 1),
            font_size=dp(13),
            background_color=COULEUR_CARTE_A,
            foreground_color=COULEUR_TEXTE,
            hint_text_color=COULEUR_TEXTE_ATTENUE,
            cursor_color=COULEUR_ACCENT,
            padding=(dp(12), dp(10)),
        )
        self.champ_recherche.bind(text=self._sur_texte_recherche)
        ligne_recherche.add_widget(self.champ_recherche)

        bouton_effacer = Button(text=ICONE_FERMER, font_size=dp(13), bold=True, color=COULEUR_TEXTE,
                                 size_hint=(None, 1), width=dp(42))
        stylise_bouton(bouton_effacer, COULEUR_ONGLET_INACTIF, rayon=12)
        bouton_effacer.bind(on_press=lambda inst: setattr(self.champ_recherche, "text", ""))
        ligne_recherche.add_widget(bouton_effacer)
        root.add_widget(ligne_recherche)

        # --- Onglets de filtrage par score, façon "pilules" (compacts) ---
        onglets = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(36), spacing=dp(6))
        self.boutons_pages = {}
        libelles_pages = {
            1: "Top lots",
            2: "Bons plans",
            3: "Petits lots",
        }
        for num_page, libelle in libelles_pages.items():
            btn = Button(text=libelle, font_size=dp(12), bold=True, color=COULEUR_TEXTE)
            stylise_bouton(btn, COULEUR_ONGLET_INACTIF, rayon=16)
            btn.bind(on_press=lambda inst, p=num_page: self._changer_page(p))
            onglets.add_widget(btn)
            self.boutons_pages[num_page] = btn
        root.add_widget(onglets)
        self._maj_style_onglets()

        self.statut = Label(
            text="Appuie sur le bouton pour lancer la recherche.",
            size_hint=(1, None),
            height=dp(20),
            font_size=dp(12),
            color=COULEUR_TEXTE_ATTENUE,
            halign="left",
            valign="middle",
        )
        self.statut.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        root.add_widget(self.statut)

        # Indicateur discret pour le "tire vers le bas pour rafraîchir"
        self.indicateur_pull = Label(
            text="", font_size=dp(11), color=COULEUR_ACCENT, bold=True,
            size_hint=(1, None), height=0, halign="center", valign="middle",
        )
        self.indicateur_pull.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        root.add_widget(self.indicateur_pull)

        self.scroll = ScrollView()
        self._pull_y_debut = None
        self._pull_declenche = False
        self.scroll.bind(
            on_touch_down=self._pull_touch_down,
            on_touch_move=self._pull_touch_move,
            on_touch_up=self._pull_touch_up,
        )
        # Espacement resserré entre les cartes pour afficher davantage de
        # concours à l'écran, tout en gardant les cartes bien détachées.
        self.liste = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=(0, dp(4)))
        self.liste.bind(minimum_height=self.liste.setter("height"))
        self.scroll.add_widget(self.liste)
        root.add_widget(self.scroll)

        # Rafraîchissement automatique : au démarrage (si la dernière recherche
        # date de plus de 24h) puis vérifié toutes les 6h tant que l'appli reste
        # ouverte. Ça ne fonctionne que si l'appli est lancée (pas de vrai
        # rafraîchissement pendant qu'elle est fermée, ça demanderait un
        # service Android natif).
        Clock.schedule_once(self._verifier_auto_refresh, 2)
        Clock.schedule_interval(self._verifier_auto_refresh, 6 * 3600)

        # --- Navigation façon "vraie page" (streaming) au lieu d'une popup pour
        # le détail d'un concours : deux écrans dans un ScreenManager. ---
        self.sm = ScreenManager(transition=SlideTransition(duration=0.22))
        ecran_liste = Screen(name="liste")
        ecran_liste.add_widget(root)
        self.sm.add_widget(ecran_liste)

        self.ecran_details = Screen(name="details")
        self.sm.add_widget(self.ecran_details)

        # Le bouton "retour" matériel Android doit ramener à la liste plutôt
        # que fermer l'application quand on est sur la page de détails.
        Window.bind(on_keyboard=self._sur_bouton_retour)

        return self.sm

    def _sur_bouton_retour(self, window, key, *args):
        if key == 27 and self.sm.current == "details":  # 27 = bouton "retour" Android
            self._retour_a_la_liste()
            return True
        return False

    def _retour_a_la_liste(self):
        self._lien_details_courant = None
        self.sm.transition.direction = "right"
        self.sm.current = "liste"

    def _sur_texte_recherche(self, instance, valeur):
        """Debounce : attend une courte pause dans la frappe avant de refiltrer,
        pour éviter de reconstruire toute la liste à chaque lettre tapée."""
        if self._debounce_recherche:
            self._debounce_recherche.cancel()
        self._debounce_recherche = Clock.schedule_once(lambda dt: self._afficher_page(), 0.3)

    def _verifier_auto_refresh(self, *_a):
        if self.bouton_recherche.disabled:
            return  # une recherche est déjà en cours
        derniere = self.etat.get("derniere_recherche")
        if derniere:
            try:
                if (datetime.now() - datetime.fromisoformat(derniere)).total_seconds() < 24 * 3600:
                    return
            except Exception:
                pass
        self.lancer_recherche(None)

    # --- Tire-vers-le-bas pour rafraîchir ---

    def _pull_touch_down(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self._pull_y_debut = touch.y
            self._pull_declenche = False
        return False

    def _pull_touch_move(self, instance, touch):
        if self._pull_y_debut is None or self.bouton_recherche.disabled:
            return False
        if self.scroll.scroll_y >= 0.98 and (touch.y - self._pull_y_debut) > dp(80):
            if not self._pull_declenche:
                self._pull_declenche = True
                self.indicateur_pull.text = "Relâche pour rafraîchir"
                self.indicateur_pull.height = dp(26)
        return False

    def _pull_touch_up(self, instance, touch):
        if self._pull_declenche:
            self.indicateur_pull.text = ""
            self.indicateur_pull.height = 0
            self.lancer_recherche(None, forcer=True)
        self._pull_y_debut = None
        self._pull_declenche = False
        return False

    def _ouvrir_preferences(self, instance):
        contenu = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))

        sous_titre = Label(
            text="Coche ce que tu ne veux plus voir apparaître :",
            font_size=dp(13), color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(24), halign="left", valign="middle",
        )
        sous_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        contenu.add_widget(sous_titre)

        scroll = ScrollView()
        grille = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        grille.bind(minimum_height=grille.setter("height"))

        cases = {}
        for cid, _mots, libelle in CATEGORIES_PARTICIPATION:
            ligne = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(10),
                               padding=(dp(10), 0, dp(10), 0))
            with ligne.canvas.before:
                Color(*COULEUR_CARTE_A)
                rect = RoundedRectangle(radius=[dp(10)], pos=ligne.pos, size=ligne.size)
            ligne.bind(pos=lambda inst, val, rect=rect: setattr(rect, "pos", inst.pos))
            ligne.bind(size=lambda inst, val, rect=rect: setattr(rect, "size", inst.size))
            case = CheckBox(active=self.preferences.get(cid, False), size_hint=(None, 1), width=dp(38),
                             color=COULEUR_ACCENT)
            lbl = Label(text=libelle, font_size=dp(14), color=COULEUR_TEXTE, halign="left", valign="middle")
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            ligne.add_widget(case)
            ligne.add_widget(lbl)
            grille.add_widget(ligne)
            cases[cid] = case
        scroll.add_widget(grille)
        contenu.add_widget(scroll)

        bouton_enregistrer = Button(text="Enregistrer", bold=True, color=(1, 1, 1, 1),
                                     size_hint_y=None, height=dp(52))
        stylise_bouton(bouton_enregistrer, COULEUR_ACCENT, rayon=14)
        contenu.add_widget(bouton_enregistrer)

        popup = Popup(
            title="Concours à éviter",
            content=contenu,
            size_hint=(0.9, 0.8),
            separator_color=COULEUR_ACCENT,
            title_color=COULEUR_TEXTE,
            background_color=COULEUR_FOND,
            title_size=dp(16),
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

    # --- Favoris ---

    def _est_favori(self, lien):
        return any(f["lien"] == lien for f in self.favoris)

    def _basculer_favori(self, c):
        """Ajoute ou retire un concours des favoris. Renvoie True si désormais favori."""
        if self._est_favori(c["lien"]):
            self.favoris = [f for f in self.favoris if f["lien"] != c["lien"]]
            sauvegarder_favoris(self.favoris)
            return False

        self.favoris.insert(0, {
            "titre": c["titre"],
            "lien": c["lien"],
            "score": c["score"],
            "date_limite_texte": c.get("date_limite_texte"),
        })
        sauvegarder_favoris(self.favoris)
        return True

    def _ouvrir_favoris(self, instance):
        popup_ref = {}

        def _ouvrir(item):
            self._ajouter_historique(item)
            ouvrir_lien(item["lien"])

        def _retirer(item):
            self.favoris = [f for f in self.favoris if f["lien"] != item["lien"]]
            sauvegarder_favoris(self.favoris)
            popup_ref["popup"].dismiss()
            self._ouvrir_favoris(None)

        popup_ref["popup"] = self._popup_liste(
            titre="Favoris",
            items=self.favoris,
            message_vide="Aucun favori pour l'instant. Ouvre un concours et appuie sur "
                          "\"Ajouter aux favoris\" pour le retrouver ici.",
            on_ouvrir=_ouvrir,
            on_retirer=_retirer,
            texte_retirer="Retirer",
        )

    # --- Historique ---

    def _ajouter_historique(self, c):
        self.historique = [h for h in self.historique if h["lien"] != c["lien"]]
        self.historique.insert(0, {
            "titre": c["titre"],
            "lien": c["lien"],
            "date_consultation": datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        sauvegarder_historique(self.historique)

    def _ouvrir_historique(self, instance):
        popup_ref = {}

        def _ouvrir(item):
            ouvrir_lien(item["lien"])

        def _retirer(item):
            self.historique = [h for h in self.historique if h["lien"] != item["lien"]]
            sauvegarder_historique(self.historique)
            popup_ref["popup"].dismiss()
            self._ouvrir_historique(None)

        items = [
            {**h, "sous_texte": f"Consulté le {h.get('date_consultation', '?')}"}
            for h in self.historique
        ]
        popup_ref["popup"] = self._popup_liste(
            titre="Historique",
            items=items,
            message_vide="Aucun concours consulté pour l'instant.",
            on_ouvrir=_ouvrir,
            on_retirer=_retirer,
            texte_retirer="Effacer",
        )

    # --- Popup générique pour afficher une liste (favoris / historique) ---

    def _popup_liste(self, titre, items, message_vide, on_ouvrir, on_retirer, texte_retirer):
        contenu = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))

        if not items:
            lbl = Label(
                text=message_vide, font_size=dp(14), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(80), halign="left", valign="top",
            )
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(lbl)
        else:
            scroll = ScrollView()
            grille = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
            grille.bind(minimum_height=grille.setter("height"))

            for item in items:
                carte = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None,
                                   padding=(dp(14), dp(14), dp(14), dp(14)))
                with carte.canvas.before:
                    Color(*COULEUR_CARTE_A)
                    rect = RoundedRectangle(radius=[dp(14)], pos=carte.pos, size=carte.size)
                    Color(*COULEUR_CARTE_BORDURE)
                    bordure = Line(rounded_rectangle=(carte.x, carte.y, carte.width, carte.height, dp(14)), width=dp(1))
                carte.bind(pos=lambda inst, val: setattr(rect, "pos", inst.pos))
                carte.bind(size=lambda inst, val: setattr(rect, "size", inst.size))

                def _sync_bordure(inst, *_a, bordure=bordure):
                    bordure.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, dp(14))
                carte.bind(pos=_sync_bordure, size=_sync_bordure)

                titre_lbl = Label(
                    text=item["titre"], font_size=dp(15), bold=True, color=COULEUR_TEXTE,
                    size_hint_y=None, halign="left", valign="top",
                )
                titre_lbl.bind(width=lambda inst, w, tl=titre_lbl: setattr(tl, "text_size", (w, None)))

                boutons_item = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
                b_ouvrir = Button(text=f"Ouvrir {ICONE_FLECHE}", font_size=dp(12), bold=True, color=(1, 1, 1, 1))
                stylise_bouton(b_ouvrir, COULEUR_ACCENT, rayon=12)
                b_ouvrir.bind(on_press=lambda inst, it=item: on_ouvrir(it))
                b_retirer = Button(text=texte_retirer, font_size=dp(12), bold=True, color=COULEUR_TEXTE)
                stylise_bouton(b_retirer, COULEUR_ONGLET_INACTIF, rayon=12)
                b_retirer.bind(on_press=lambda inst, it=item: on_retirer(it))
                boutons_item.add_widget(b_ouvrir)
                boutons_item.add_widget(b_retirer)

                def _maj_hauteur(inst, ts, carte=carte, boutons_item=boutons_item):
                    carte.height = ts[1] + boutons_item.height + dp(8) + dp(28)
                titre_lbl.bind(texture_size=_maj_hauteur)

                sous_texte = item.get("sous_texte")
                carte.add_widget(titre_lbl)
                if sous_texte:
                    sous_lbl = Label(
                        text=sous_texte, font_size=dp(11), color=COULEUR_TEXTE_ATTENUE,
                        size_hint_y=None, height=dp(18), halign="left", valign="middle",
                    )
                    sous_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
                    carte.add_widget(sous_lbl)
                carte.add_widget(boutons_item)

                grille.add_widget(carte)

            scroll.add_widget(grille)
            contenu.add_widget(scroll)

        bouton_fermer = Button(text="Fermer", bold=True, color=COULEUR_TEXTE, size_hint_y=None, height=dp(50))
        stylise_bouton(bouton_fermer, COULEUR_ONGLET_INACTIF, rayon=14)
        contenu.add_widget(bouton_fermer)

        popup = Popup(
            title=titre, content=contenu, size_hint=(0.92, 0.85),
            separator_color=COULEUR_ACCENT, title_color=COULEUR_TEXTE,
            background_color=COULEUR_FOND, title_size=dp(16),
        )
        bouton_fermer.bind(on_press=lambda inst: popup.dismiss())
        popup.open()
        return popup

    def _maj_style_onglets(self):
        for num_page, btn in self.boutons_pages.items():
            actif = num_page == self.page_actuelle
            btn.couleur_instr.rgba = COULEUR_ACCENT if actif else COULEUR_ONGLET_INACTIF

    def _changer_page(self, num_page):
        self.page_actuelle = num_page
        self._maj_style_onglets()
        self._afficher_page()

    def lancer_recherche(self, instance, forcer=False):
        self.bouton_recherche.disabled = True
        self.statut.text = "Recherche en cours..."
        self.liste.clear_widgets()
        threading.Thread(target=self._recherche_thread, args=(forcer,), daemon=True).start()

    def _recherche_thread(self, forcer=False):
        categories_evitees = {cid for cid, evite in self.preferences.items() if evite}
        try:
            resultats, diagnostic = recuperer_concours(
                categories_evitees,
                on_progress=lambda i, total, url: self._maj_progression(i, total, url),
                forcer_actualisation=forcer,
            )
        except Exception as e:
            self._afficher_erreur(str(e))
            return
        self._afficher_resultats(resultats, diagnostic)

    @mainthread
    def _maj_progression(self, i, total, url):
        self.statut.text = f"Vérification de {_nom_source(url)}... ({i}/{total})"

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

        self.etat["derniere_recherche"] = datetime.now().isoformat()
        sauvegarder_etat(self.etat)

        self.statut.text = (
            f"{len(resultats)} concours trouvés — "
            f"maj le {datetime.now(timezone.utc):%d/%m/%Y %H:%M}"
        )

        if not resultats and diagnostic:
            self.liste.clear_widgets()
            lbl_msg = Label(
                text="Aucun concours trouvé. Vérifie ta connexion et réessaie, "
                     "ou consulte le détail technique ci-dessous.",
                size_hint_y=None, height=dp(50), font_size=dp(14),
                color=COULEUR_TEXTE_ATTENUE, halign="left", valign="middle",
            )
            lbl_msg.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.liste.add_widget(lbl_msg)

            bouton_reessayer = Button(
                text="Réessayer", bold=True, color=(1, 1, 1, 1),
                size_hint_y=None, height=dp(48),
            )
            stylise_bouton(bouton_reessayer, COULEUR_ACCENT, rayon=12)
            bouton_reessayer.bind(on_press=self.lancer_recherche)
            self.liste.add_widget(bouton_reessayer)

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
            page = [c for c in resultats if c["score"] >= 10]
        elif num_page == 2:
            page = [c for c in resultats if 5 <= c["score"] <= 9]
        else:
            page = [c for c in resultats if c["score"] < 5]

        mot_cle = self.champ_recherche.text.strip().lower() if hasattr(self, "champ_recherche") else ""
        if mot_cle:
            page = [c for c in page if mot_cle in c["titre"].lower() or mot_cle in c.get("resume", "").lower()]
        return page

    def _afficher_page(self, reinitialiser=True):
        if reinitialiser:
            self.nb_affiches = self.TAILLE_LOT

        self.liste.clear_widgets()
        mot_cle = self.champ_recherche.text.strip() if hasattr(self, "champ_recherche") else ""
        page_complete = self._filtrer_page(self.resultats_actuels, self.page_actuelle)
        page = page_complete[: self.nb_affiches]

        libelles = {1: "Top lots", 2: "Bons plans", 3: "Petits lots"}
        self.statut.text = (
            f"{len(self.resultats_actuels)} concours au total — "
            f"{len(page_complete)} correspondent ({libelles[self.page_actuelle]})"
        )

        if not page_complete:
            message = (
                "Aucun concours trouvé pour l'instant. Lance une recherche !"
                if not self.resultats_actuels
                else "Aucun concours ne correspond à ce filtre."
            )
            lbl_vide = Label(
                text=message, font_size=dp(14), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(60), halign="center", valign="middle",
            )
            lbl_vide.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.liste.add_widget(lbl_vide)

            if self.resultats_actuels and mot_cle:
                bouton_reset = Button(
                    text="Effacer le mot-clé", bold=True, color=(1, 1, 1, 1),
                    size_hint_y=None, height=dp(44),
                )
                stylise_bouton(bouton_reset, COULEUR_ONGLET_INACTIF, rayon=12)
                bouton_reset.bind(on_press=lambda inst: setattr(self.champ_recherche, "text", ""))
                self.liste.add_widget(bouton_reset)
            return

        for i, c in enumerate(page, 1):
            self._ajouter_ligne_concours(i, c)

        reste = len(page_complete) - len(page)
        if reste > 0:
            bouton_plus = Button(
                text=f"Afficher plus ({reste} restant(s))",
                font_size=dp(14), bold=True, color=(1, 1, 1, 1),
                size_hint_y=None, height=dp(48),
            )
            stylise_bouton(bouton_plus, COULEUR_ONGLET_INACTIF, rayon=12)
            bouton_plus.bind(on_press=lambda inst: self._afficher_plus())
            self.liste.add_widget(bouton_plus)

    def _afficher_plus(self):
        self.nb_affiches += self.TAILLE_LOT
        self._afficher_page(reinitialiser=False)

    def _ajouter_ligne_concours(self, i, c):
        libelle_palier, couleur_palier, icone_palier = infos_palier(c["score"])

        ligne = BoxLayout(orientation="horizontal", size_hint_y=None, spacing=dp(10),
                           padding=(dp(0), dp(0), dp(12), dp(0)))

        # Grande carte uniforme (façon "streaming") : fond identique pour toutes
        # les cartes, un fin liseré pour les détacher du fond, et une bande
        # verticale colorée à gauche qui indique le palier au premier coup d'œil.
        with ligne.canvas.before:
            Color(*COULEUR_CARTE_A)
            rect = RoundedRectangle(radius=[dp(16)], pos=ligne.pos, size=ligne.size)
            Color(*COULEUR_CARTE_BORDURE)
            bordure = Line(rounded_rectangle=(ligne.x, ligne.y, ligne.width, ligne.height, dp(16)), width=dp(1))
            Color(*couleur_palier)
            accent = RoundedRectangle(radius=[dp(3)], pos=ligne.pos, size=(dp(4), ligne.height))

        def _sync_fond(inst, *_a):
            rect.pos = inst.pos
            rect.size = inst.size
            bordure.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, dp(16))
            accent.pos = (inst.x + dp(6), inst.y + dp(6))
            accent.size = (dp(4), max(inst.height - dp(12), 0))

        ligne.bind(pos=_sync_fond, size=_sync_fond)

        # --- Contenu principal (badges + titre), à gauche, prend toute la place restante ---
        contenu = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None,
                             padding=(dp(12), dp(10), 0, dp(10)))

        ligne_badge = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))

        texte_badge = f"{icone_palier} {libelle_palier}" if icone_palier else libelle_palier
        badge = Label(
            text=texte_badge,
            font_size=dp(10),
            bold=True,
            color=(0.07, 0.07, 0.07, 1) if couleur_palier == COULEUR_PREMIUM else (1, 1, 1, 1),
            size_hint=(None, None),
            height=dp(20),
            halign="center",
            valign="middle",
        )
        badge.texture_update()
        badge.width = badge.texture_size[0] + dp(18)
        badge.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        with badge.canvas.before:
            Color(*couleur_palier)
            badge_rect = RoundedRectangle(radius=[dp(10)], pos=badge.pos, size=badge.size)
        badge.bind(pos=lambda inst, val: setattr(badge_rect, "pos", inst.pos))
        badge.bind(size=lambda inst, val: setattr(badge_rect, "size", inst.size))
        ligne_badge.add_widget(badge)

        score_lbl = Label(
            text=f"{c['score']} pts", font_size=dp(10), color=COULEUR_TEXTE_ATTENUE,
            size_hint=(None, 1), width=dp(42), halign="left", valign="middle",
        )
        score_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        ligne_badge.add_widget(score_lbl)

        date_obj = c.get("date_limite_obj")
        if date_obj:
            jours_restants = (date_obj - date.today()).days
            if 0 <= jours_restants <= 5:
                texte_urgence = "Dernier jour" if jours_restants == 0 else f"J-{jours_restants}"
                urgence = Label(
                    text=texte_urgence,
                    font_size=dp(9),
                    bold=True,
                    color=(1, 1, 1, 1),
                    size_hint=(None, None),
                    size=(dp(64), dp(20)),
                    halign="center",
                    valign="middle",
                )
                urgence.bind(size=lambda inst, val: setattr(inst, "text_size", val))
                with urgence.canvas.before:
                    Color(*COULEUR_URGENCE)
                    urgence_rect = RoundedRectangle(radius=[dp(10)], pos=urgence.pos, size=urgence.size)
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
            bold=True,
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            color=COULEUR_TEXTE,
        )

        def _update_text_size(instance, width, item=item):
            item.text_size = (width - dp(6), None)

        def _update_hauteurs(instance, texture_size, ligne=ligne, contenu=contenu, item=item):
            item.height = texture_size[1]
            contenu.height = texture_size[1] + dp(20) + dp(4) + dp(20)
            ligne.height = contenu.height

        item.bind(width=_update_text_size)
        item.bind(texture_size=_update_hauteurs)
        item.bind(on_press=lambda inst, c=c: self._afficher_details(c))
        contenu.add_widget(item)
        ligne.add_widget(contenu)

        # --- Actions secondaires, regroupées à droite (favori en icône, puis suppression) ---
        actions = BoxLayout(orientation="vertical", size_hint=(None, 1), width=dp(40), spacing=dp(6),
                             padding=(0, dp(10), 0, dp(10)))

        est_favori = self._est_favori(c["lien"])
        bouton_fav = Button(
            text=ICONE_FAVORI_PLEIN if est_favori else ICONE_FAVORI_VIDE,
            font_size=dp(10), bold=True, color=(1, 1, 1, 1),
            size_hint=(None, None), size=(dp(32), dp(32)),
        )
        stylise_bouton(bouton_fav, COULEUR_ACCENT if est_favori else COULEUR_ONGLET_INACTIF, rayon=16)

        def _on_press_fav(inst, c=c, bouton_fav=bouton_fav):
            nouvel_etat = self._basculer_favori(c)
            bouton_fav.text = ICONE_FAVORI_PLEIN if nouvel_etat else ICONE_FAVORI_VIDE
            bouton_fav.couleur_instr.rgba = COULEUR_ACCENT if nouvel_etat else COULEUR_ONGLET_INACTIF

        bouton_fav.bind(on_press=_on_press_fav)
        actions.add_widget(bouton_fav)

        case = CheckBox(size_hint=(None, None), size=(dp(28), dp(28)), color=COULEUR_TEXTE)
        case.bind(active=lambda inst, valeur, lien=c["lien"], ligne=ligne:
                  self._supprimer_concours(lien, ligne) if valeur else None)
        actions.add_widget(case)
        ligne.add_widget(actions)

        self.liste.add_widget(ligne)

    def _afficher_details(self, c):
        """Construit une vraie page plein écran (pas une popup) pour le détail
        d'un concours : titre, étoiles, valeur estimée, actions requises,
        échéance, puis le lien vers le concours. Vérifie aussi la vraie page
        du concours en tâche de fond pour affiner les infos affichées."""
        self._lien_details_courant = c["lien"]
        self.ecran_details.clear_widgets()

        page = BoxLayout(orientation="vertical", padding=(dp(16), dp(42), dp(16), dp(14)), spacing=dp(10))

        # --- Barre du haut : retour + favori ---
        barre_haut = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(40), spacing=dp(8))
        bouton_retour = Button(text="< Retour", font_size=dp(13), bold=True, color=COULEUR_TEXTE,
                                size_hint=(None, 1), width=dp(90))
        stylise_bouton(bouton_retour, COULEUR_ONGLET_INACTIF, rayon=14)
        bouton_retour.bind(on_press=lambda inst: self._retour_a_la_liste())
        barre_haut.add_widget(bouton_retour)
        barre_haut.add_widget(BoxLayout())  # pousse le favori à droite

        est_favori = self._est_favori(c["lien"])
        bouton_favori = Button(
            text=f"{ICONE_FAVORI_PLEIN} favori" if est_favori else f"{ICONE_FAVORI_VIDE} favori",
            font_size=dp(12), bold=True, color=(1, 1, 1, 1),
            size_hint=(None, 1), width=dp(90),
        )
        stylise_bouton(bouton_favori, COULEUR_ACCENT if est_favori else COULEUR_ONGLET_INACTIF, rayon=14)

        def _on_press_favori(inst):
            nouvel_etat = self._basculer_favori(c)
            bouton_favori.text = f"{ICONE_FAVORI_PLEIN} favori" if nouvel_etat else f"{ICONE_FAVORI_VIDE} favori"
            bouton_favori.couleur_instr.rgba = COULEUR_ACCENT if nouvel_etat else COULEUR_ONGLET_INACTIF

        bouton_favori.bind(on_press=_on_press_favori)
        barre_haut.add_widget(bouton_favori)
        page.add_widget(barre_haut)

        # --- Contenu déroulant ---
        scroll = ScrollView()
        contenu = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, padding=(0, dp(8), 0, dp(8)))
        contenu.bind(minimum_height=contenu.setter("height"))

        libelle_palier, couleur_palier, icone_palier = infos_palier(c["score"])
        texte_badge = f"{icone_palier} {libelle_palier}" if icone_palier else libelle_palier
        badge = Label(
            text=texte_badge, font_size=dp(12), bold=True,
            color=(0.07, 0.07, 0.07, 1) if couleur_palier == COULEUR_PREMIUM else (1, 1, 1, 1),
            size_hint=(None, None), height=dp(26), halign="center", valign="middle",
        )
        badge.texture_update()
        badge.width = badge.texture_size[0] + dp(22)
        badge.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        with badge.canvas.before:
            Color(*couleur_palier)
            badge_rect = RoundedRectangle(radius=[dp(13)], pos=badge.pos, size=badge.size)
        badge.bind(pos=lambda inst, val: setattr(badge_rect, "pos", inst.pos))
        badge.bind(size=lambda inst, val: setattr(badge_rect, "size", inst.size))
        ligne_badge = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6), padding=(0, dp(4), 0, 0))
        ligne_badge.add_widget(badge)
        ligne_badge.add_widget(BoxLayout())
        contenu.add_widget(ligne_badge)

        titre_lbl = Label(
            text=c["titre"], font_size=dp(24), bold=True, color=COULEUR_TEXTE,
            size_hint_y=None, halign="left", valign="top",
        )
        titre_lbl.bind(width=lambda inst, w: setattr(titre_lbl, "text_size", (w, None)))
        titre_lbl.bind(texture_size=lambda inst, ts: setattr(titre_lbl, "height", ts[1]))
        contenu.add_widget(titre_lbl)

        # --- Étoiles ---
        nb_etoiles = etoiles_pour_score(c["score"])
        ligne_etoiles = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(3), padding=(0, dp(6), 0, dp(4)))
        for i in range(5):
            etoile = Label(
                text=ICONE_ETOILE, font_size=dp(20), bold=True,
                color=COULEUR_PREMIUM if i < nb_etoiles else COULEUR_ONGLET_INACTIF,
                size_hint=(None, 1), width=dp(20),
            )
            ligne_etoiles.add_widget(etoile)
        ligne_etoiles.add_widget(BoxLayout())
        contenu.add_widget(ligne_etoiles)

        def _ajouter_section(titre_section, widget_valeur):
            contenu.add_widget(_widget_separateur())
            lbl_titre = Label(
                text=titre_section, font_size=dp(12), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(18), halign="left", valign="middle",
            )
            lbl_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(lbl_titre)
            contenu.add_widget(widget_valeur)

        # --- Valeur estimée (si détectée) ---
        if c.get("valeur_estimee"):
            lbl_valeur = Label(
                text=c["valeur_estimee"], font_size=dp(22), bold=True, color=COULEUR_PREMIUM,
                size_hint_y=None, height=dp(30), halign="left", valign="middle",
            )
            lbl_valeur.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            _ajouter_section("VALEUR ESTIMÉE", lbl_valeur)

        # --- Actions requises pour participer ---
        bloc_actions = BoxLayout(orientation="vertical", spacing=dp(3), size_hint_y=None)
        bloc_actions.bind(minimum_height=bloc_actions.setter("height"))
        infos_affichees = set()

        def _ajouter_info(libelle):
            if libelle in infos_affichees:
                return
            infos_affichees.add(libelle)
            lbl = Label(
                text=f"- {libelle}", font_size=dp(15), color=COULEUR_TEXTE,
                size_hint_y=None, height=dp(26), halign="left", valign="middle",
            )
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            bloc_actions.add_widget(lbl)

        infos_initiales = detecter_infos_requises(c["titre"], c.get("resume", ""))
        if infos_initiales:
            for libelle in infos_initiales:
                _ajouter_info(libelle)
        else:
            _ajouter_info("Aucune action connue pour l'instant")
        _ajouter_section("ACTIONS", bloc_actions)

        # --- Échéance ---
        if c.get("date_limite_obj"):
            jours_restants = (c["date_limite_obj"] - date.today()).days
            if jours_restants <= 0:
                texte_echeance = "Aujourd'hui"
            elif jours_restants == 1:
                texte_echeance = "Demain"
            else:
                texte_echeance = f"{jours_restants} jours"
            lbl_echeance = Label(
                text=texte_echeance, font_size=dp(20), bold=True,
                color=COULEUR_URGENCE if jours_restants <= 5 else COULEUR_TEXTE,
                size_hint_y=None, height=dp(28), halign="left", valign="middle",
            )
            lbl_echeance.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            _ajouter_section("EXPIRE DANS", lbl_echeance)
        elif c.get("date_limite_texte"):
            lbl_echeance = Label(
                text=c["date_limite_texte"], font_size=dp(15), bold=True, color=COULEUR_URGENCE,
                size_hint_y=None, height=dp(22), halign="left", valign="middle",
            )
            lbl_echeance.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            _ajouter_section("ÉCHÉANCE", lbl_echeance)

        contenu.add_widget(_widget_separateur())

        statut_verif = Label(
            text="Vérification des informations sur la page du concours...",
            font_size=dp(12), color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(34), halign="left", valign="top",
        )
        statut_verif.bind(width=lambda inst, w: setattr(statut_verif, "text_size", (w, None)))
        contenu.add_widget(statut_verif)

        if c.get("resume"):
            lbl_resume_titre = Label(
                text="RÉSUMÉ", font_size=dp(12), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(18), halign="left", valign="middle",
            )
            lbl_resume_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(lbl_resume_titre)
            lbl_resume = Label(
                text=c["resume"], font_size=dp(13), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, halign="left", valign="top",
            )
            lbl_resume.bind(width=lambda inst, w: setattr(lbl_resume, "text_size", (w, None)))
            lbl_resume.bind(texture_size=lambda inst, ts: setattr(lbl_resume, "height", ts[1]))
            contenu.add_widget(lbl_resume)

        scroll.add_widget(contenu)
        page.add_widget(scroll)

        # --- Bouton d'action principal, fixe en bas de page ---
        bouton_ouvrir = Button(text=f"Voir le concours {ICONE_FLECHE}", font_size=dp(15), bold=True,
                                color=(1, 1, 1, 1), size_hint=(1, None), height=dp(52))
        stylise_bouton(bouton_ouvrir, COULEUR_ACCENT, rayon=15)

        def _ouvrir(inst):
            self._ajouter_historique(c)
            ouvrir_lien(c["lien"])

        bouton_ouvrir.bind(on_press=_ouvrir)
        page.add_widget(bouton_ouvrir)

        self.ecran_details.add_widget(page)
        self.sm.transition.direction = "left"
        self.sm.current = "details"

        # Vérification en tâche de fond : on va chercher la vraie page du concours
        # pour affiner les infos (plus fiable qu'un simple résumé RSS tronqué).
        # Si on a déjà quitté cette fiche quand la réponse arrive, on ignore.
        threading.Thread(
            target=self._verifier_page_concours,
            args=(c, statut_verif, _ajouter_info),
            daemon=True,
        ).start()

    def _verifier_page_concours(self, c, statut_verif, ajouter_info):
        lien = c["lien"]
        if lien in self._cache_pages:
            texte_page = self._cache_pages[lien]
        else:
            texte_page = recuperer_texte_page(lien)
            if texte_page is not None:
                self._cache_pages[lien] = texte_page

        if texte_page is None:
            self._maj_verification(c["lien"], statut_verif, None, echec=True)
            return
        nouvelles_infos = detecter_infos_requises(c["titre"], texte_page)
        self._maj_verification(c["lien"], statut_verif, nouvelles_infos, echec=False, ajouter_info=ajouter_info)

    @mainthread
    def _maj_verification(self, lien, statut_verif, nouvelles_infos, echec, ajouter_info=None):
        if getattr(self, "_lien_details_courant", None) != lien:
            return  # on a déjà quitté cette fiche, inutile de toucher aux widgets

        if echec:
            statut_verif.text = "Page injoignable pour vérification — utilise le bouton ci-dessous."
            statut_verif.color = (0.85, 0.55, 0.25, 1)
            return

        statut_verif.text = "Informations vérifiées sur la page du concours"
        statut_verif.color = (0.35, 0.70, 0.45, 1)
        for libelle in nouvelles_infos:
            ajouter_info(libelle)

    def _supprimer_concours(self, lien, ligne):
        """Coché = suppression définitive du concours de la liste et du stockage."""
        self.supprimes.add(lien)
        sauvegarder_supprimes(self.supprimes)
        self.resultats_actuels = [c for c in self.resultats_actuels if c["lien"] != lien]
        self.liste.remove_widget(ligne)


if __name__ == "__main__":
    ConcoursFinderApp().run()
