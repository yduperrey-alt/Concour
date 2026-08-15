"""
Concours Finder — application Android (Kivy)
Recherche des jeux concours via flux RSS, les classe par score de lot,
et affiche la liste dans une interface tactile.

Fichier unique (regroupe constantes / analyse / stockage / réseau / interface)
— version consolidée pour isoler un éventuel problème lié au découpage en
plusieurs modules.
"""

# ============================== CONSTANTES ==============================

from urllib.parse import quote_plus

# --- Palette de couleurs — identité "streaming" (Netflix/Spotify) ---
# Fond quasi-noir + cartes légèrement plus claires pour un fort effet de
# profondeur, un unique accent vert émeraude, et l'or réservé aux gros lots
# uniquement (pour qu'il garde tout son impact visuel).
#
# Deux palettes (sombre/claire) : les noms COULEUR_* restent des variables de
# module normales (pas de vraies constantes en Python), réassignées une seule
# fois au démarrage par _appliquer_theme() selon la préférence utilisateur.
# Tout le reste du fichier continue de lire COULEUR_FOND, COULEUR_ACCENT...
# sans changement : c'est un thème "appliqué au démarrage", pas un
# recoloriage dynamique en direct (qui demanderait de reprendre l'instruction
# Color de chaque widget déjà construit — trop risqué à faire à l'aveugle).
PALETTE_SOMBRE = dict(
    COULEUR_FOND=(0.067, 0.067, 0.067, 1),          # #111111
    COULEUR_CARTE_A=(0.118, 0.118, 0.118, 1),       # #1E1E1E
    COULEUR_CARTE_B=(0.118, 0.118, 0.118, 1),       # même teinte : grille uniforme, pas de zébrage
    COULEUR_CARTE_BORDURE=(0.20, 0.20, 0.20, 1),    # liseré discret pour détacher les cartes du fond
    COULEUR_ACCENT=(0.298, 0.686, 0.314, 1),        # #4CAF50 — vert émeraude
    COULEUR_ACCENT_FONCE=(0.220, 0.557, 0.235, 1),  # #388E3C — variante pressée/bordure
    COULEUR_ONGLET_INACTIF=(0.16, 0.16, 0.16, 1),
    COULEUR_TEXTE=(0.96, 0.96, 0.96, 1),
    COULEUR_TEXTE_ATTENUE=(0.62, 0.62, 0.62, 1),
    # Texte affiché SUR un bouton/badge de couleur COULEUR_ACCENT. Du blanc
    # pur sur le vert émeraude ne donne qu'un contraste WCAG ~2.8:1 (sous le
    # seuil AA de 4.5:1 même en gros texte gras) ; un texte quasi noir monte
    # à ~6.8:1. Centralisé ici pour ne pas avoir à choisir au cas par cas.
    COULEUR_TEXTE_SUR_ACCENT=(0.05, 0.05, 0.05, 1),
)
PALETTE_CLAIRE = dict(
    COULEUR_FOND=(0.965, 0.965, 0.965, 1),
    COULEUR_CARTE_A=(1, 1, 1, 1),
    COULEUR_CARTE_B=(1, 1, 1, 1),
    COULEUR_CARTE_BORDURE=(0.85, 0.85, 0.85, 1),
    COULEUR_ACCENT=(0.220, 0.557, 0.235, 1),        # #388E3C — plus soutenu que sur fond sombre
    COULEUR_ACCENT_FONCE=(0.157, 0.443, 0.173, 1),
    COULEUR_ONGLET_INACTIF=(0.90, 0.90, 0.90, 1),
    COULEUR_TEXTE=(0.10, 0.10, 0.10, 1),
    COULEUR_TEXTE_ATTENUE=(0.40, 0.40, 0.40, 1),
    COULEUR_TEXTE_SUR_ACCENT=(1, 1, 1, 1),
)

COULEUR_FOND = PALETTE_SOMBRE["COULEUR_FOND"]
COULEUR_CARTE_A = PALETTE_SOMBRE["COULEUR_CARTE_A"]
COULEUR_CARTE_B = PALETTE_SOMBRE["COULEUR_CARTE_B"]
COULEUR_CARTE_BORDURE = PALETTE_SOMBRE["COULEUR_CARTE_BORDURE"]
COULEUR_ACCENT = PALETTE_SOMBRE["COULEUR_ACCENT"]
COULEUR_ACCENT_FONCE = PALETTE_SOMBRE["COULEUR_ACCENT_FONCE"]
COULEUR_ONGLET_INACTIF = PALETTE_SOMBRE["COULEUR_ONGLET_INACTIF"]
COULEUR_TEXTE = PALETTE_SOMBRE["COULEUR_TEXTE"]
COULEUR_TEXTE_ATTENUE = PALETTE_SOMBRE["COULEUR_TEXTE_ATTENUE"]
COULEUR_TEXTE_SUR_ACCENT = PALETTE_SOMBRE["COULEUR_TEXTE_SUR_ACCENT"]
COULEUR_PREMIUM = (0.831, 0.686, 0.216, 1)       # #D4AF37 — or, réservé aux gros lots
COULEUR_MOYEN = (0.149, 0.651, 0.604, 1)         # sarcelle — reste dans la famille vert/émeraude
COULEUR_BASIQUE = (0.42, 0.42, 0.42, 1)          # gris neutre
COULEUR_URGENCE = (0.86, 0.25, 0.24, 1)          # rouge alerte (deadline proche)


def _appliquer_theme(nom_theme):
    """Réassigne les variables de palette globales selon le thème choisi.
    Doit être appelé UNE SEULE FOIS, tout au début de App.build(), avant la
    création du moindre widget (chaque widget capture la couleur au moment
    de sa création, il n'y a pas de rafraîchissement dynamique)."""
    palette = PALETTE_CLAIRE if nom_theme == "clair" else PALETTE_SOMBRE
    globals().update(palette)

# Icônes en ASCII pur uniquement. Les caractères Unicode "symboles" (★ ♥ ✕ →)
# ne sont PAS inclus dans la police embarquée par Kivy sur Android : ils
# s'affichent en carré vide (tofu). L'ASCII, lui, est garanti dans absolument
# toutes les polices, sur tous les appareils, sans exception.
ICONE_FAVORI_PLEIN = "FAV"
ICONE_FAVORI_VIDE = "+"
ICONE_ETOILE = "*"
ICONE_FERMER = "X"
ICONE_FLECHE = ">"

# --- Fichiers de stockage local (dans le dossier de données de l'app) ---
FICHIER_SUPPRIMES = "concours_supprimes.json"
FICHIER_PREFERENCES = "preferences.json"
FICHIER_FAVORIS = "favoris.json"
FICHIER_HISTORIQUE = "historique.json"
FICHIER_ETAT = "etat_app.json"
FICHIER_CACHE_FLUX = "cache_flux.json"
FICHIER_CACHE_PAGES = "cache_pages.json"
FICHIER_PARAMETRES = "parametres.json"
FICHIER_JOURNAL_CRASH = "dernier_crash.log"
FICHIER_DERNIERS_RESULTATS = "derniers_resultats_ok.json"

# --- Paramètres réseau ---
TIMEOUT_RESEAU = 10                    # secondes avant abandon d'un flux injoignable
MAX_FLUX_PARALLELES = 18               # téléchargements simultanés max
JOURS_MAX_ANCIENNETE = 45              # articles plus vieux que ça = probablement terminés
DUREE_CACHE_FLUX_SECONDES = 30 * 60    # un flux réutilisé depuis le cache pendant 30 min
DUREE_CACHE_PAGES_SECONDES = 24 * 3600  # une page de détail revérifiée au plus 1 fois/jour

# --- Paramètres réglables par l'utilisateur (voir _ouvrir_parametres) ---
FREQUENCES_RAFRAICHISSEMENT = [
    ("6h", 6), ("12h", 12), ("24h", 24), ("Désactivé", 0),
]

# --- Tris disponibles pour la liste (voir bouton_tri / _filtrer_page) ---
TRIS_DISPONIBLES = [
    ("score", "Score"),
    ("date", "Échéance"),
    ("valeur", "Valeur"),
    ("alpha", "A-Z"),
]

LIBELLES_PAGES = {1: "Top lots", 2: "Bons plans", 3: "Petits lots", 4: "RS"}
PARAMETRES_PAR_DEFAUT = {
    "theme_clair": False,
    "frequence_refresh_heures": 24,
    "flux_desactives": [],
    "tri": "score",
}


# --- 1. Sources RSS ---

def _url_google_news(requete: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(requete)}&hl=fr&gl=FR&ceid=FR:fr"


def _url_groupee(marques) -> str:
    """Construit UNE SEULE requête Google Actualités couvrant plusieurs
    marques à la fois via une union OR (ex: '("Carrefour" concours) OR
    ("Lidl" concours) OR ...'), au lieu d'un flux RSS séparé par marque.

    Avant : ~80 flux Google Actualités individuels (1 par marque), chacun
    retéléchargé à chaque recherche non mise en cache.
    Après  : ~15 flux groupés par catégorie (distribution, high-tech,
    jeux vidéo...), pour la même couverture de marques.
    Effet : nettement moins d'appels réseau, donc recherche plus rapide et
    bien plus économe en data mobile et en batterie. Les groupes restent
    volontairement limités à une poignée de marques chacun pour ne pas
    dégrader la pertinence des résultats Google Actualités."""
    requete = " OR ".join(f'("{m}" concours)' for m in marques)
    return _url_google_news(requete)


# Liste de (libellé lisible, url) au lieu d'une simple liste d'URL : le
# libellé sert à l'écran "Sources" des paramètres (activer/désactiver un flux
# individuellement — les URLs Google Actualités générées ne sont pas
# lisibles telles quelles). FLUX_RSS et FLUX_RSS_LIBELLES ci-dessous sont
# dérivés de cette même liste pour ne jamais désynchroniser les deux.
FLUX_RSS_AVEC_LIBELLES = [
    # --- Sites dédiés aux jeux-concours ---
    ("GrattWeb (France)", "https://www.grattweb.fr/rss/rss.xml"),
    ("GrattWeb (Étranger)", "https://www.grattweb.fr/rss/rss_etranger.xml"),
    ("Concours.fr", "https://www.concours.fr/feed/"),

    # NOTE : les flux de presse généraliste (PlayStation Blog, Xbox News, Steam
    # News, IGN, JeuxActu, Gameblog...) ont été retirés. Ce sont des flux
    # d'actualité pure : leurs articles parlent de sorties de jeux, tests,
    # mises à jour... et contiennent très souvent un mot-clé de lot (« PS5 »,
    # « Xbox », « Samsung »...) sans qu'il s'agisse d'un concours. Les
    # requêtes Google Actualités ciblées ci-dessous (« marque + concours »)
    # couvrent déjà les vrais concours organisés par ces mêmes marques,
    # sans le bruit des articles d'actualité générale.

    # --- Mots-clés génériques ---
    ("Actus : \"jeu concours\"", _url_google_news('"jeu concours"')),
    ("Actus : \"instant gagnant\"", _url_google_news('"instant gagnant"')),
    ("Actus : \"tirage au sort\"", _url_google_news('"tirage au sort"')),
    ("Actus : \"gagnez\"", _url_google_news("gagnez")),
    ("Actus : \"grand jeu\"", _url_google_news('"grand jeu concours"')),
    ("Actus : \"jouez et gagnez\"", _url_google_news('"jouez et gagnez"')),

    # --- Marques, regroupées par secteur (voir _url_groupee ci-dessus) ---
    ("Grande distribution", _url_groupee(["Carrefour", "E.Leclerc", "Lidl", "Auchan", "Intermarché",
                                           "Super U", "Monoprix", "Casino"])),
    ("High-tech / e-commerce", _url_groupee(["Fnac", "Darty", "Boulanger", "Cdiscount", "Amazon France"])),
    ("Divertissement / médias", _url_groupee(["Disney", "Pixar", "Marvel", "TF1", "M6", "France TV",
                                               "NRJ", "RTL", "Europe 1", "RMC"])),
    ("Jeux vidéo", _url_groupee(["PlayStation", "Xbox", "Nintendo", "Steam", "Epic Games",
                                  "Ubisoft", "EA", "Riot Games", "Blizzard", "Rockstar Games"])),
    ("Jouets", _url_groupee(["LEGO", "Mattel", "Hasbro"])),
    ("Jeux de société / loisirs créatifs", _url_groupee(["Asmodée", "Djeco", "Playmobil", "Ravensburger"])),
    ("Confiserie / boissons", _url_groupee(["Kinder", "Haribo", "Nutella", "Milka", "Coca-Cola",
                                             "Pepsi", "Red Bull", "Oreo", "LU"])),
    ("Automobile", _url_groupee(["Michelin", "Renault", "Peugeot", "Citroën", "Dacia"])),
    ("Électronique", _url_groupee(["Samsung", "LG", "Sony", "Asus", "Acer", "HP", "Dell", "Lenovo"])),
    ("Télécom / streaming", _url_groupee(["Orange", "SFR", "Free", "Bouygues Telecom", "Canal+",
                                           "Netflix", "Prime Video", "Disney+"])),
    ("Sport / beauté", _url_groupee(["Decathlon", "Intersport", "Go Sport", "Sephora",
                                      "Yves Rocher", "Nocibé", "L'Oréal"])),
    ("Restauration rapide", _url_groupee(["KFC", "McDonald's", "Burger King", "Domino's Pizza"])),
    ("Bricolage / déco", _url_groupee(["IKEA", "Leroy Merlin", "Castorama", "Brico Dépôt"])),
    ("Voyage", _url_groupee(["Air France", "SNCF", "Accor", "Pierre & Vacances"])),

    # --- Réseaux sociaux / créateurs de contenu ---
    # Instagram et TikTok n'ont pas de flux RSS publics (ce sont des posts,
    # pas des pages web indexables) : impossible de suivre un concours natif
    # directement. En revanche, Google Actualités remonte bien les articles
    # de blogs/presse qui ANNONCENT ce type de concours ("gagnez en likant
    # sur Instagram...") : c'est ce qu'on cible ici, regroupé en une requête.
    ("Concours réseaux sociaux", _url_google_news(
        '"concours instagram" OR "concours tiktok" OR "concours facebook" OR '
        '"concours twitter" OR "concours créateur" OR "concours influenceur" OR '
        '"concours youtubeur" OR (giveaway instagram concours)'
    )),

    # Deux sites spécialisés qui référencent notamment des concours créateurs /
    # réseaux sociaux. Leur flux RSS n'a pas pu être confirmé publiquement
    # depuis cet environnement (adresse déduite de la convention WordPress
    # /feed/) : si l'URL est incorrecte, le diagnostic technique l'indiquera
    # simplement (0 entrée ou erreur), sans rien casser dans l'app.
    ("Aldabro Concours", "https://aldabro-concours.com/feed/"),
    ("Jouer Gagnant Concept", "https://www.jouer-gagnant-concept.com/feed/"),
]

FLUX_RSS = [url for _libelle, url in FLUX_RSS_AVEC_LIBELLES]
FLUX_RSS_LIBELLES = dict(FLUX_RSS_AVEC_LIBELLES)

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

# Catégories considérées comme "réseaux sociaux" pour le nouvel onglet RS :
# tout concours qui demande de suivre/liker/partager sur un réseau social.
CATEGORIES_RESEAUX_SOCIAUX = {"instagram", "facebook", "tiktok", "twitter"}

# Informations purement indicatives (pas des "actions" à réaliser, donc ne
# comptent pas dans le calcul de facilité de participation ni dans les préférences).
INDICES_INFO_POSITIFS = [
    (["tirage au sort"], "Tirage au sort parmi les participants"),
    (["sans obligation d'achat", "sans achat"], "Sans obligation d'achat"),
    (["gratuit", "gratuitement"], "Participation gratuite"),
]

MOIS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
MOTS_CLE_DATE_LIMITE = [
    "jusqu'au", "jusqu au", "jusqu'à", "avant le", "se termine le",
    "clôture le", "cloture le", "date limite", "fin du concours le",
    # Formulations supplémentaires, fréquentes dans les flux mais absentes
    "expire le", "expire, le", "à gagner jusqu'au", "clôture des inscriptions le",
    "dernier délai le", "d'ici le", "jusqu'en", "se clôture le", "prend fin le",
]

# Instagram et TikTok n'ont pas de flux RSS public (voir FLUX_RSS ci-dessus) :
# impossible de les indexer automatiquement dans la recherche. À la place,
# on propose un accès rapide à la page de recherche PUBLIQUE de chaque
# réseau pour un hashtag choisi par l'utilisateur (par défaut "jeuconcours",
# mais modifiable dans l'app — voir champ_hashtag dans ui.py). Aucun
# scraping, aucune automatisation : juste un raccourci vers le moteur de
# recherche propre à chaque plateforme, avec le hashtag inséré dans l'URL.
RESEAUX_SOCIAUX_RECHERCHE = [
    ("Instagram", "https://www.instagram.com/explore/tags/{hashtag}/"),
    ("TikTok", "https://www.tiktok.com/tag/{hashtag}"),
    ("Facebook", "https://www.facebook.com/hashtag/{hashtag}"),
    ("X", "https://x.com/hashtag/{hashtag}"),
]

HASHTAG_PAR_DEFAUT = "jeuconcours"


def normaliser_hashtag(texte: str) -> str:
    """Nettoie une saisie utilisateur pour en faire un hashtag valide dans une
    URL : retire un éventuel '#' et les espaces (un hashtag n'en contient
    jamais), puis encode les caractères spéciaux/accentués. Renvoie le
    hashtag par défaut si la saisie est vide une fois nettoyée."""
    texte = (texte or "").strip().lstrip("#").replace(" ", "")
    return quote_plus(texte) if texte else HASHTAG_PAR_DEFAUT


def url_reseau_social(template: str, hashtag_saisi: str) -> str:
    """Construit l'URL de recherche finale pour un réseau donné à partir de
    son template (voir RESEAUX_SOCIAUX_RECHERCHE) et du hashtag saisi."""
    return template.format(hashtag=normaliser_hashtag(hashtag_saisi))


# =============================== ANALYSE =================================

import difflib
import html
import re
from datetime import date, datetime



def _texte_normalise(titre: str, resume: str) -> str:
    """Concatène et met en minuscule titre+résumé une seule fois par entrée.
    Toutes les fonctions d'analyse ci-dessous acceptent ce texte déjà calculé
    (paramètre `texte`) pour éviter de refaire 4 fois le même travail sur
    chaque entrée RSS (avant : 4 concaténations + 4 .lower() par entrée)."""
    return f"{titre} {resume}".lower()


def est_probablement_une_actualite(titre: str, resume: str, texte: str = None) -> bool:
    """Détecte les entrées qui ne sont pas de vrais jeux-concours."""
    texte = texte if texte is not None else _texte_normalise(titre, resume)
    return any(mot in texte for mot in MOTS_EXCLUS)


def contient_signal_concours(titre: str, resume: str, texte: str = None) -> bool:
    """Un mot-clé de lot (ex: 'PS5', 'Samsung') ne suffit PAS à lui seul à
    prouver qu'il s'agit d'un jeu-concours : une actualité jeux vidéo ou
    high-tech classique contient souvent ces mêmes mots. On exige donc en
    plus la présence d'un vrai signal de concours (« concours », « tirage
    au sort », « à gagner »...) avant même de calculer un score."""
    texte = texte if texte is not None else _texte_normalise(titre, resume)
    return any(mot in texte for mot in SIGNAUX_CONCOURS)


def score_concours(titre: str, resume: str, texte: str = None) -> int:
    texte = texte if texte is not None else _texte_normalise(titre, resume)
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


def detecter_categories_requises(titre: str, resume: str, texte: str = None) -> list:
    """Renvoie les identifiants des catégories d'actions requises détectées (ex: 'instagram')."""
    texte = texte if texte is not None else _texte_normalise(titre, resume)
    return [cid for cid, mots, _libelle in CATEGORIES_PARTICIPATION if any(m in texte for m in mots)]


def detecter_infos_requises(titre: str, resume: str) -> list:
    """Renvoie les libellés lisibles (actions + infos positives) pour l'affichage dans la popup."""
    texte = _texte_normalise(titre, resume)
    trouves = []
    for _cid, mots, libelle in CATEGORIES_PARTICIPATION:
        if any(m in texte for m in mots) and libelle not in trouves:
            trouves.append(libelle)
    for mots, libelle in INDICES_INFO_POSITIFS:
        if any(m in texte for m in mots) and libelle not in trouves:
            trouves.append(libelle)
    return trouves


# L'année est optionnelle dans les deux regex (ex: "jusqu'au 12/03" ou
# "jusqu'au 12 mars", sans préciser l'année, est très courant dans les flux).
_RE_DATE_NUM = re.compile(r"(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?")
_RE_DATE_LETTRES = re.compile(
    r"(\d{1,2})\s*(" + "|".join(MOIS_FR.keys()) + r")\s*(\d{4})?", re.IGNORECASE
)


def _annee_la_plus_probable(jour: int, mois: int) -> int:
    """Quand l'année n'est pas précisée dans le texte, on suppose l'année en
    cours — sauf si ça place la date plus de 120 jours dans le passé, auquel
    cas on suppose l'année suivante (ex: un article de décembre qui annonce
    "jusqu'au 15 janvier" désigne le janvier suivant, pas celui déjà passé)."""
    aujourdhui = date.today()
    annee = aujourdhui.year
    try:
        candidate = date(annee, mois, jour)
    except ValueError:
        return annee
    if (aujourdhui - candidate).days > 120:
        return annee + 1
    return annee


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
            annee_int = int(annee) if annee else _annee_la_plus_probable(int(jour), int(mois))
            if annee_int < 100:
                annee_int += 2000
            try:
                d = date(annee_int, int(mois), int(jour))
                return d.strftime("Jusqu'au %d/%m/%Y"), d
            except ValueError:
                pass

        m2 = _RE_DATE_LETTRES.search(fenetre)
        if m2:
            jour, mois_txt, annee = m2.groups()
            mois_num = MOIS_FR.get(mois_txt.lower())
            annee_int = int(annee) if annee else _annee_la_plus_probable(int(jour), mois_num)
            try:
                d = date(annee_int, mois_num, int(jour))
                return f"Jusqu'au {int(jour)} {mois_txt} {annee_int}", d
            except ValueError:
                pass
    return None, None


# Partie entière : soit un groupement de milliers explicite (1 200 / 1.200,
# exactement 3 chiffres par groupe, pour ne pas avaler des décimales), soit
# n'importe quelle suite de chiffres. Partie décimale : virgule (usage FR,
# "12,50€") OU point (parfois utilisé aussi, "12.50€") suivi de 1 ou 2
# chiffres — avant ce correctif, "12.50€" n'était compté que comme "12€"
# (le point était traité à tort comme un séparateur de milliers).
_RE_VALEUR_EUROS = re.compile(
    r"(\d{1,3}(?:[ .]\d{3})+|\d+)(?:[,.](\d{1,2}))?\s?(?:€|euros?)", re.IGNORECASE
)


def extraire_valeur_estimee(texte: str):
    """Cherche un montant en euros dans le texte (ex: "d'une valeur de 550€")
    et renvoie (texte_affichage, valeur_numerique) pour le plus élevé trouvé
    — le nombre brut sert au tri par valeur (voir ConcoursFinderApp._filtrer_page).
    Renvoie (None, None) si aucun montant plausible n'est trouvé."""
    if not texte:
        return None, None
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
        return None, None
    if meilleure_valeur == int(meilleure_valeur):
        texte_valeur = f"{int(meilleure_valeur):,}".replace(",", " ")
    else:
        texte_valeur = f"{meilleure_valeur:,.2f}".replace(",", " ")
    return f"{texte_valeur} €", meilleure_valeur


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


_RE_SUFFIXE_SITE = re.compile(r"[-–|]\s*[\w.]+\.(com|fr|net|org|be|info)\s*$", re.IGNORECASE)


def normaliser_titre(titre: str) -> str:
    """Normalise un titre pour comparaison (retire le nom de site final, la ponctuation)."""
    t = _RE_SUFFIXE_SITE.sub("", titre.lower())
    t = re.sub(r"[^\wàâäéèêëïîôöùûüç\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def deduplique_concours(resultats: list) -> list:
    """Fusionne les concours quasi-identiques relayés par plusieurs flux :
    ne garde que la première rencontrée (la liste doit déjà être triée par score
    décroissant), qui est donc la mieux notée. Le concours gardé reçoit un
    petit bonus de score par doublon fusionné (voir plus bas) : un concours
    relayé par plusieurs sources est probablement plus fiable/important
    qu'un concours isolé.

    Comparaison indexée par mots-clés au lieu d'un O(n²) sur toute la liste :
    un concours n'est comparé qu'aux concours déjà gardés qui partagent au
    moins un mot significatif (4 lettres ou plus) avec lui, via un index
    inversé mot -> indices des concours gardés. Sur une liste de plusieurs
    milliers d'entrées, ça évite l'essentiel des comparaisons difflib
    inutiles (concours qui n'ont aucun mot en commun, donc aucune chance
    d'être des doublons)."""
    gardes = []
    titres_normalises = []
    nb_flux_par_garde = []
    index_mots = {}  # mot significatif -> ensemble des indices dans `gardes`

    for c in resultats:
        nt = normaliser_titre(c["titre"])
        mots_significatifs = {m for m in nt.split() if len(m) >= 4}

        candidats = set()
        for mot in mots_significatifs:
            candidats.update(index_mots.get(mot, ()))

        idx_correspondant = next(
            (idx for idx in candidats
             if difflib.SequenceMatcher(None, nt, titres_normalises[idx]).ratio() > 0.82),
            None,
        )
        if idx_correspondant is not None:
            nb_flux_par_garde[idx_correspondant] += 1
            continue

        nouvel_idx = len(gardes)
        gardes.append(c)
        titres_normalises.append(nt)
        nb_flux_par_garde.append(1)
        for mot in mots_significatifs:
            index_mots.setdefault(mot, set()).add(nouvel_idx)

    # Bonus plafonné (+2 par doublon, max +6) pour ne jamais dominer le score
    # de base — juste un petit coup de pouce en cas d'égalité/quasi-égalité.
    for c, nb_flux in zip(gardes, nb_flux_par_garde):
        if nb_flux > 1:
            c["score"] += min(nb_flux - 1, 3) * 2

    return gardes


def infos_palier(score: int):
    """Renvoie (libellé, couleur, icône) selon le palier de score du concours.
    Centralise la hiérarchie visuelle façon "streaming" : l'or n'est utilisé
    que pour les vrais gros lots, pour garder tout son impact."""
    if score >= 10:
        return "TOP LOT", COULEUR_PREMIUM, ICONE_ETOILE
    elif score >= 5:
        return "BON PLAN", COULEUR_MOYEN, ""
    return "PETIT LOT", COULEUR_BASIQUE, ""


# Couleurs de badge assez claires pour qu'un texte blanc dessus tombe sous le
# seuil de contraste WCAG AA (4.5:1) : un texte quasi noir y est utilisé à la
# place. COULEUR_BASIQUE (gris) reste au-dessus du seuil avec du blanc.
_COULEURS_BADGE_CLAIRES = (COULEUR_PREMIUM, COULEUR_MOYEN)


def couleur_texte_badge(couleur_palier):
    return (0.07, 0.07, 0.07, 1) if couleur_palier in _COULEURS_BADGE_CLAIRES else (1, 1, 1, 1)


# =============================== STOCKAGE =================================

import json
import os

from kivy.app import App



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


# --- Cache des pages de détail déjà vérifiées (voir recuperer_texte_page) ---
# Avant, ce cache n'existait qu'en mémoire (self._cache_pages) : reperdu à
# chaque redémarrage de l'app, donc une page déjà vérifiée hier était
# retéléchargée en entier dès qu'on rouvrait sa fiche.

def charger_cache_pages():
    return _charger_json(FICHIER_CACHE_PAGES, {})


def sauvegarder_cache_pages(cache):
    _sauvegarder_json(FICHIER_CACHE_PAGES, cache, "le cache des pages de détail")


# --- Paramètres réglables par l'utilisateur (thème, fréquence, flux actifs) ---
# Séparé des préférences ("catégories à éviter") pour ne pas mélanger des
# clés de nature différente (bool par catégorie vs. réglages ponctuels).

def charger_parametres():
    parametres = dict(PARAMETRES_PAR_DEFAUT)
    parametres.update(_charger_json(FICHIER_PARAMETRES, {}))
    return parametres


def sauvegarder_parametres(parametres):
    _sauvegarder_json(FICHIER_PARAMETRES, parametres, "les paramètres")


# --- Dernier jeu de résultats obtenu avec succès (mode hors-ligne) ---
# `date_limite_obj` est un objet `date`, non sérialisable tel quel en JSON :
# converti en texte ISO à la sauvegarde, reconverti au chargement.

def sauvegarder_derniers_resultats(resultats):
    serialisables = []
    for c in resultats:
        c2 = dict(c)
        date_obj = c2.get("date_limite_obj")
        c2["date_limite_obj"] = date_obj.isoformat() if date_obj else None
        serialisables.append(c2)
    _sauvegarder_json(FICHIER_DERNIERS_RESULTATS, serialisables, "les derniers résultats")


def charger_derniers_resultats():
    resultats = []
    for c in _charger_json(FICHIER_DERNIERS_RESULTATS, []):
        c2 = dict(c)
        texte_date = c2.get("date_limite_obj")
        c2["date_limite_obj"] = date.fromisoformat(texte_date) if texte_date else None
        resultats.append(c2)
    return resultats


# ================================ RESEAU ==================================

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


_RE_IMG_HTML = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _extraire_image_url(entree):
    """Cherche une image associée à une entrée de flux RSS : miniature
    media:thumbnail, media:content, pièce jointe (enclosure), ou balise <img>
    intégrée dans le résumé HTML — dans cet ordre de préférence. Renvoie None
    si rien de plausible n'est trouvé (les flux Google Actualités n'ont
    jamais d'image, par exemple — c'est un cas normal, pas une erreur)."""
    for media in entree.get("media_thumbnail", None) or ():
        url = media.get("url")
        if url:
            return url
    for media in entree.get("media_content", None) or ():
        url = media.get("url")
        type_media = media.get("medium") or media.get("type", "")
        if url and ("image" in type_media or not type_media):
            return url
    for piece_jointe in entree.get("enclosures", None) or ():
        url = piece_jointe.get("href") or piece_jointe.get("url")
        if url and "image" in piece_jointe.get("type", ""):
            return url
    m = _RE_IMG_HTML.search(entree.get("summary", "") or "")
    return m.group(1) if m else None


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
            "image_url": _extraire_image_url(entree),
        })
    return entrees


def recuperer_concours(on_progress=None, forcer_actualisation=False, flux_desactives=None):
    """Télécharge/traite tous les flux RSS et renvoie (resultats, diagnostic).

    Important : cette fonction NE filtre PLUS par préférence utilisateur
    ("catégories à éviter"). Ce filtrage se fait désormais uniquement à
    l'affichage (voir ConcoursFinderApp._appliquer_preferences), pour que
    décocher une préférence restaure immédiatement les concours concernés
    sans avoir besoin de relancer une recherche réseau complète.

    `flux_desactives` : ensemble d'URLs de FLUX_RSS à ignorer complètement
    (réglage "Sources" des paramètres — voir _ouvrir_parametres)."""
    flux_actifs = [url for url in FLUX_RSS if url not in (flux_desactives or ())]
    resultats = []
    vus = set()
    supprimes = charger_supprimes()
    diagnostic = []
    nb_total = len(flux_actifs)
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

            valeur_estimee_texte, valeur_estimee_nombre = extraire_valeur_estimee(f"{titre} {resume}")

            resultats.append({
                "titre": titre,
                "lien": lien,
                "date_publication": date_pub,
                "date_limite_texte": date_limite_texte,
                "date_limite_obj": date_limite_obj,
                "resume": nettoyer_html(resume),
                "valeur_estimee": valeur_estimee_texte,
                "valeur_estimee_nombre": valeur_estimee_nombre,
                "categories": categories_requises,
                "score": score,
                "source": url,
                "image_url": e.get("image_url"),
            })

        nb_ajoutes = len(resultats) - nb_avant
        tag = " (cache)" if depuis_cache else ""
        nom_flux = FLUX_RSS_LIBELLES.get(url, url)
        detail = f"{nom_flux}{tag} -> {nb_ajoutes} entrée(s), http={statut_http}"
        if bozo:
            detail += f", erreur parsing: {bozo_msg}"
        diagnostic.append(detail)

    # --- 1) Flux encore valides en cache : traitement instantané, aucun accès
    #     réseau. C'est ce qui donne l'ouverture quasi-immédiate et économise
    #     à la fois batterie et data mobile. ---
    urls_a_telecharger = []
    for url in flux_actifs:
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
    # Redondant après un tri déjà décroissant, SAUF que deduplique_concours
    # peut relever le score de certains concours (bonus multi-flux) : sans ce
    # second tri, l'ordre affiché pourrait rester légèrement désynchronisé
    # du score final pour ces concours-là.
    resultats.sort(key=lambda c: c["score"], reverse=True)
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


def partager_concours(titre: str, lien: str):
    """Partage un concours via le sélecteur natif Android (Intent.ACTION_SEND,
    même mécanisme que "Partager" dans n'importe quelle app Android : SMS,
    e-mail, WhatsApp...). Sur desktop, pas de sélecteur de partage système
    équivalent : on copie le texte dans le presse-papiers à la place."""
    texte = f"{titre} — {lien}"
    if platform == "android":
        try:
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(Intent.ACTION_SEND)
            intent.setType("text/plain")
            intent.putExtra(Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(texte)))
            chooser = Intent.createChooser(intent, cast("java.lang.CharSequence", String("Partager le concours")))
            currentActivity = cast("android.app.Activity", PythonActivity.mActivity)
            currentActivity.startActivity(chooser)
        except Exception as e:
            print(f"Impossible de partager : {e}")
    else:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(texte)


# ================================== UI =====================================

import threading
from datetime import date, datetime, timezone

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
from kivy.uix.progressbar import ProgressBar
from kivy.uix.widget import Widget
from kivy.uix.image import AsyncImage
from kivy.metrics import dp, sp

# Window.clearcolor est fixé dans App.build(), APRÈS _appliquer_theme() —
# pas ici au niveau module — pour refléter la préférence de thème choisie
# par l'utilisateur (chargée depuis parametres.json).


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
        self.parametres = charger_parametres()
        # Doit être appelé avant TOUT widget/instruction Color : réassigne les
        # variables de palette globales lues par le reste de build().
        _appliquer_theme("clair" if self.parametres.get("theme_clair") else "sombre")
        Window.clearcolor = COULEUR_FOND

        self.title = "Concours Finder"
        self.supprimes = charger_supprimes()
        self.preferences = charger_preferences()
        self.favoris = charger_favoris()
        self.historique = charger_historique()
        self.etat = charger_etat()
        self._donnees_perimees = False
        # _resultats_bruts : dernier résultat de recherche réseau, JAMAIS modifié
        # par un changement de préférences. resultats_actuels : vue filtrée
        # dérivée de _resultats_bruts, recalculée à chaque changement de
        # préférences (voir _appliquer_preferences) — ce qui rend le filtrage
        # par préférence entièrement réversible sans relancer de recherche.
        self._resultats_bruts = []
        self.resultats_actuels = []
        self.page_actuelle = 1
        self.nb_affiches = self.TAILLE_LOT
        # Persisté sur disque (voir charger_cache_pages) : une page de détail déjà
        # vérifiée reste en cache DUREE_CACHE_PAGES_SECONDES, même entre deux
        # lancements de l'app, au lieu d'être reperdue à chaque redémarrage.
        self._cache_pages = charger_cache_pages()
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
            font_size=sp(20),
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
            font_size=sp(12),
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
            ("Paramètres", "", self._ouvrir_parametres),
        ):
            btn = Button(text=texte_btn, font_size=sp(11), bold=True, color=COULEUR_TEXTE,
                         size_hint=(1, 1))
            stylise_bouton(btn, COULEUR_ONGLET_INACTIF, rayon=15)
            btn.bind(on_press=callback)
            ligne_actions.add_widget(btn)
        entete.add_widget(ligne_actions)
        root.add_widget(entete)

        self.bouton_recherche = Button(
            text="Rechercher les concours",
            font_size=sp(15),
            bold=True,
            color=COULEUR_TEXTE_SUR_ACCENT,
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
            font_size=sp(13),
            background_color=COULEUR_CARTE_A,
            foreground_color=COULEUR_TEXTE,
            hint_text_color=COULEUR_TEXTE_ATTENUE,
            cursor_color=COULEUR_ACCENT,
            padding=(dp(12), dp(10)),
        )
        self.champ_recherche.bind(text=self._sur_texte_recherche)
        ligne_recherche.add_widget(self.champ_recherche)

        bouton_effacer = Button(text=ICONE_FERMER, font_size=sp(13), bold=True, color=COULEUR_TEXTE,
                                 size_hint=(None, 1), width=dp(42))
        stylise_bouton(bouton_effacer, COULEUR_ONGLET_INACTIF, rayon=12)
        bouton_effacer.bind(on_press=lambda inst: setattr(self.champ_recherche, "text", ""))
        ligne_recherche.add_widget(bouton_effacer)

        # Tri manuel (score / échéance / valeur / alphabétique) : un tap fait
        # défiler les options plutôt qu'un sélecteur séparé, pour rester compact.
        libelle_tri_actuel = dict(TRIS_DISPONIBLES).get(self.parametres.get("tri", "score"), "Score")
        self.bouton_tri = Button(text=f"Tri: {libelle_tri_actuel}", font_size=sp(11), bold=True,
                                  color=COULEUR_TEXTE, size_hint=(None, 1), width=dp(100))
        stylise_bouton(self.bouton_tri, COULEUR_ONGLET_INACTIF, rayon=12)
        self.bouton_tri.bind(on_press=self._cycler_tri)
        ligne_recherche.add_widget(self.bouton_tri)
        root.add_widget(ligne_recherche)

        # --- Onglets de filtrage par score, façon "pilules" (compacts) ---
        onglets = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(36), spacing=dp(6))
        self.boutons_pages = {}
        for num_page, libelle in LIBELLES_PAGES.items():
            btn = Button(text=libelle, font_size=sp(10), bold=True, color=COULEUR_TEXTE,
                         halign="center", valign="middle", shorten=True, shorten_from="right")
            # Sans cette contrainte, un texte allongé (badge de compte ajouté
            # par _maj_badges_onglets, ex: "Bons plans (12)") déborde
            # visuellement au-delà des limites réelles du bouton : le texte
            # semble plus large que la zone cliquable, qui elle ne bouge pas
            # (elle suit toujours pos/size du widget, pas la taille du texte).
            btn.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            stylise_bouton(btn, COULEUR_ONGLET_INACTIF, rayon=16)
            btn.bind(on_press=lambda inst, p=num_page: self._changer_page(p))
            onglets.add_widget(btn)
            self.boutons_pages[num_page] = btn
        root.add_widget(onglets)

        # --- Recherche manuelle sur les réseaux sociaux, visible uniquement
        # sur l'onglet "RS" (Instagram/TikTok n'ont pas de flux RSS public,
        # donc pas d'indexation automatique possible — voir RESEAUX_SOCIAUX_RECHERCHE).
        # Les réseaux eux-mêmes s'affichent en colonne dans la liste principale
        # (voir _ajouter_ligne_reseau_social) ; ce bloc ne contient que le champ
        # hashtag partagé par tous. `disabled` est indispensable en plus de
        # `opacity` : dans Kivy, opacity=0 rend un widget invisible mais ne
        # bloque PAS le toucher, donc le champ restait cliquable/actif "dans le
        # vide" sur les autres onglets sans ce réglage. ---
        self.bloc_reseaux = BoxLayout(orientation="vertical", size_hint=(1, None), height=0, spacing=dp(4))
        self.bloc_reseaux.opacity = 0
        self.bloc_reseaux.disabled = True
        lbl_reseaux = Label(
            text="Chercher un hashtag sur :",
            font_size=sp(10), color=COULEUR_TEXTE_ATTENUE,
            size_hint=(1, None), height=dp(14), halign="left", valign="middle",
        )
        lbl_reseaux.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.bloc_reseaux.add_widget(lbl_reseaux)

        # Champ modifiable : "jeuconcours" par défaut, mais l'utilisateur
        # peut taper n'importe quel autre mot-clé (ex: "iphone", "voyage"...)
        # avant d'appuyer sur un des boutons ci-dessous.
        ligne_hashtag = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(36), spacing=dp(4))
        lbl_diese = Label(
            text="#", font_size=sp(15), bold=True, color=COULEUR_TEXTE_ATTENUE,
            size_hint=(None, 1), width=dp(14),
        )
        ligne_hashtag.add_widget(lbl_diese)
        self.champ_hashtag = TextInput(
            text=HASHTAG_PAR_DEFAUT,
            multiline=False,
            size_hint=(1, 1),
            font_size=sp(13),
            background_color=COULEUR_CARTE_A,
            foreground_color=COULEUR_TEXTE,
            hint_text_color=COULEUR_TEXTE_ATTENUE,
            cursor_color=COULEUR_ACCENT,
            padding=(dp(10), dp(8)),
        )
        ligne_hashtag.add_widget(self.champ_hashtag)
        self.bloc_reseaux.add_widget(ligne_hashtag)
        root.add_widget(self.bloc_reseaux)

        self._maj_style_onglets()
        self._maj_visibilite_reseaux_sociaux()

        self.statut = Label(
            text="Appuie sur le bouton pour lancer la recherche.",
            size_hint=(1, None),
            height=dp(20),
            font_size=sp(12),
            color=COULEUR_TEXTE_ATTENUE,
            halign="left",
            valign="middle",
        )
        self.statut.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        root.add_widget(self.statut)

        # Barre de progression réelle pendant la recherche (masquée le reste
        # du temps, hauteur 0) — remplace l'ancien "x/y flux vérifiés" texte
        # seul, qui ne donnait aucun repère visuel de l'avancement.
        self.barre_progression = ProgressBar(max=1, value=0, size_hint=(1, None), height=0)
        root.add_widget(self.barre_progression)

        # Indicateur discret pour le "tire vers le bas pour rafraîchir"
        self.indicateur_pull = Label(
            text="", font_size=sp(11), color=COULEUR_ACCENT, bold=True,
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

    def _cycler_tri(self, instance):
        """Un tap fait passer au tri suivant dans TRIS_DISPONIBLES (boucle)."""
        ids = [tid for tid, _libelle in TRIS_DISPONIBLES]
        actuel = self.parametres.get("tri", "score")
        suivant = ids[(ids.index(actuel) + 1) % len(ids)] if actuel in ids else ids[0]
        self.parametres["tri"] = suivant
        sauvegarder_parametres(self.parametres)
        self.bouton_tri.text = f"Tri: {dict(TRIS_DISPONIBLES)[suivant]}"
        self._afficher_page()

    def _verifier_auto_refresh(self, *_a):
        frequence_heures = self.parametres.get("frequence_refresh_heures", 24)
        if frequence_heures <= 0:
            return  # rafraîchissement auto désactivé dans les paramètres
        if self.bouton_recherche.disabled:
            return  # une recherche est déjà en cours
        derniere = self.etat.get("derniere_recherche")
        if derniere:
            try:
                if (datetime.now() - datetime.fromisoformat(derniere)).total_seconds() < frequence_heures * 3600:
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
            font_size=sp(13), color=COULEUR_TEXTE_ATTENUE,
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
            lbl = Label(text=libelle, font_size=sp(14), color=COULEUR_TEXTE, halign="left", valign="middle")
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            ligne.add_widget(case)
            ligne.add_widget(lbl)
            grille.add_widget(ligne)
            cases[cid] = case
        scroll.add_widget(grille)
        contenu.add_widget(scroll)

        bouton_enregistrer = Button(text="Enregistrer", bold=True, color=COULEUR_TEXTE_SUR_ACCENT,
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
            self._appliquer_preferences()
            popup.dismiss()

        bouton_enregistrer.bind(on_press=_enregistrer)
        popup.open()

    def _ouvrir_parametres(self, instance):
        """Popup "Paramètres" : thème, fréquence de rafraîchissement auto et
        sources RSS actives — distinct de "Options" (catégories à éviter)
        pour ne pas mélanger des réglages de nature différente."""
        contenu = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
        scroll = ScrollView()
        grille = BoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None)
        grille.bind(minimum_height=grille.setter("height"))

        def _ligne_carte():
            ligne = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(10),
                               padding=(dp(10), 0, dp(10), 0))
            with ligne.canvas.before:
                Color(*COULEUR_CARTE_A)
                rect = RoundedRectangle(radius=[dp(10)], pos=ligne.pos, size=ligne.size)
            ligne.bind(pos=lambda inst, val, rect=rect: setattr(rect, "pos", inst.pos))
            ligne.bind(size=lambda inst, val, rect=rect: setattr(rect, "size", inst.size))
            return ligne

        def _titre_section(texte):
            lbl = Label(text=texte, font_size=sp(12), bold=True, color=COULEUR_TEXTE_ATTENUE,
                        size_hint_y=None, height=dp(20), halign="left", valign="middle")
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            return lbl

        # --- Thème (appliqué au prochain lancement, voir _appliquer_theme) ---
        grille.add_widget(_titre_section("APPARENCE"))
        ligne_theme = _ligne_carte()
        case_theme = CheckBox(active=self.parametres.get("theme_clair", False),
                               size_hint=(None, 1), width=dp(38), color=COULEUR_ACCENT)
        lbl_theme = Label(text="Thème clair (redémarrage nécessaire)", font_size=sp(13),
                           color=COULEUR_TEXTE, halign="left", valign="middle")
        lbl_theme.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        ligne_theme.add_widget(case_theme)
        ligne_theme.add_widget(lbl_theme)
        grille.add_widget(ligne_theme)

        # --- Fréquence de rafraîchissement automatique ---
        grille.add_widget(_titre_section("RAFRAÎCHISSEMENT AUTOMATIQUE"))
        ligne_frequence = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(6))
        boutons_frequence = {}
        etat_frequence = {"valeur": self.parametres.get("frequence_refresh_heures", 24)}

        def _choisir_frequence(heures):
            etat_frequence["valeur"] = heures
            for h, btn_f in boutons_frequence.items():
                actif = h == heures
                btn_f.couleur_instr.rgba = COULEUR_ACCENT if actif else COULEUR_ONGLET_INACTIF
                btn_f.color = COULEUR_TEXTE_SUR_ACCENT if actif else COULEUR_TEXTE

        for libelle, heures in FREQUENCES_RAFRAICHISSEMENT:
            btn_f = Button(text=libelle, font_size=sp(12), bold=True, size_hint=(1, 1))
            stylise_bouton(btn_f, COULEUR_ONGLET_INACTIF, rayon=14)
            btn_f.bind(on_press=lambda inst, h=heures: _choisir_frequence(h))
            ligne_frequence.add_widget(btn_f)
            boutons_frequence[heures] = btn_f
        grille.add_widget(ligne_frequence)
        _choisir_frequence(etat_frequence["valeur"])

        # --- Sources RSS actives ---
        grille.add_widget(_titre_section("SOURCES RSS ACTIVES"))
        flux_desactives_actuels = set(self.parametres.get("flux_desactives", []))
        cases_flux = {}
        for libelle, url in FLUX_RSS_AVEC_LIBELLES:
            ligne_flux = _ligne_carte()
            case_flux = CheckBox(active=url not in flux_desactives_actuels,
                                  size_hint=(None, 1), width=dp(38), color=COULEUR_ACCENT)
            lbl_flux = Label(text=libelle, font_size=sp(13), color=COULEUR_TEXTE,
                              halign="left", valign="middle")
            lbl_flux.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            ligne_flux.add_widget(case_flux)
            ligne_flux.add_widget(lbl_flux)
            grille.add_widget(ligne_flux)
            cases_flux[url] = case_flux

        scroll.add_widget(grille)
        contenu.add_widget(scroll)

        bouton_enregistrer = Button(text="Enregistrer", bold=True, color=COULEUR_TEXTE_SUR_ACCENT,
                                     size_hint_y=None, height=dp(52))
        stylise_bouton(bouton_enregistrer, COULEUR_ACCENT, rayon=14)
        contenu.add_widget(bouton_enregistrer)

        popup = Popup(
            title="Paramètres",
            content=contenu,
            size_hint=(0.92, 0.9),
            separator_color=COULEUR_ACCENT,
            title_color=COULEUR_TEXTE,
            background_color=COULEUR_FOND,
            title_size=dp(16),
        )

        def _enregistrer(inst):
            theme_avant = self.parametres.get("theme_clair", False)
            self.parametres["theme_clair"] = case_theme.active
            self.parametres["frequence_refresh_heures"] = etat_frequence["valeur"]
            self.parametres["flux_desactives"] = [url for url, case in cases_flux.items() if not case.active]
            sauvegarder_parametres(self.parametres)
            popup.dismiss()
            if case_theme.active != theme_avant:
                self.statut.text = "Thème enregistré — redémarre l'app pour l'appliquer."

        bouton_enregistrer.bind(on_press=_enregistrer)
        popup.open()

    def _appliquer_preferences(self):
        """Recalcule la liste affichée à partir de la liste BRUTE (jamais
        modifiée) et des préférences actuelles. Contrairement à l'ancienne
        version qui supprimait définitivement les concours de
        self.resultats_actuels, cette opération est entièrement réversible :
        décocher une préférence restaure immédiatement les concours
        concernés, sans avoir besoin de relancer une recherche réseau."""
        categories_evitees = {cid for cid, evite in self.preferences.items() if evite}
        if categories_evitees:
            self.resultats_actuels = [
                c for c in self._resultats_bruts
                if not (set(c.get("categories", [])) & categories_evitees)
            ]
        else:
            self.resultats_actuels = list(self._resultats_bruts)
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
                text=message_vide, font_size=sp(14), color=COULEUR_TEXTE_ATTENUE,
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
                carte.bind(pos=lambda inst, val, rect=rect: setattr(rect, "pos", inst.pos))
                carte.bind(size=lambda inst, val, rect=rect: setattr(rect, "size", inst.size))

                def _sync_bordure(inst, *_a, bordure=bordure):
                    bordure.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, dp(14))
                carte.bind(pos=_sync_bordure, size=_sync_bordure)

                titre_lbl = Label(
                    text=item["titre"], font_size=sp(15), bold=True, color=COULEUR_TEXTE,
                    size_hint_y=None, halign="left", valign="top",
                )
                titre_lbl.bind(width=lambda inst, w, tl=titre_lbl: setattr(tl, "text_size", (w, None)))

                boutons_item = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
                b_ouvrir = Button(text=f"Ouvrir {ICONE_FLECHE}", font_size=sp(12), bold=True, color=COULEUR_TEXTE_SUR_ACCENT)
                stylise_bouton(b_ouvrir, COULEUR_ACCENT, rayon=12)
                b_ouvrir.bind(on_press=lambda inst, it=item: on_ouvrir(it))
                b_retirer = Button(text=texte_retirer, font_size=sp(12), bold=True, color=COULEUR_TEXTE)
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
                        text=sous_texte, font_size=sp(11), color=COULEUR_TEXTE_ATTENUE,
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
            btn.color = COULEUR_TEXTE_SUR_ACCENT if actif else COULEUR_TEXTE

    def _maj_badges_onglets(self):
        """Affiche le nombre de résultats de chaque onglet dans son libellé
        (ex: "Top lots (12)"), recalculé à chaque changement de résultats,
        de préférences ou de mot-clé filtré."""
        if not hasattr(self, "boutons_pages"):
            return
        for num_page, btn in self.boutons_pages.items():
            nb = len(self._filtrer_page(self.resultats_actuels, num_page))
            libelle_base = LIBELLES_PAGES[num_page]
            btn.text = f"{libelle_base} ({nb})"

    def _maj_visibilite_reseaux_sociaux(self):
        """Le champ hashtag n'a de sens que sur l'onglet "RS" : masqué
        (hauteur 0, invisible et désactivé) sur les autres."""
        visible = self.page_actuelle == 4
        self.bloc_reseaux.height = dp(54) if visible else 0
        self.bloc_reseaux.opacity = 1 if visible else 0
        self.bloc_reseaux.disabled = not visible

    def _changer_page(self, num_page):
        self.page_actuelle = num_page
        self._maj_style_onglets()
        self._maj_visibilite_reseaux_sociaux()
        self._afficher_page()

    def lancer_recherche(self, instance, forcer=False):
        self.bouton_recherche.disabled = True
        self.statut.text = "Recherche en cours..."
        self.barre_progression.max = 1
        self.barre_progression.value = 0
        self.barre_progression.height = dp(6)
        self.liste.clear_widgets()
        threading.Thread(target=self._recherche_thread, args=(forcer,), daemon=True).start()

    def _recherche_thread(self, forcer=False):
        try:
            resultats, diagnostic = recuperer_concours(
                on_progress=lambda i, total, url: self._maj_progression(i, total, url),
                forcer_actualisation=forcer,
                flux_desactives=self.parametres.get("flux_desactives", []),
            )
        except Exception as e:
            self._afficher_erreur(str(e))
            return
        self._afficher_resultats(resultats, diagnostic)

    @mainthread
    def _maj_progression(self, i, total, url):
        self.statut.text = f"Vérification de {_nom_source(url)}... ({i}/{total})"
        self.barre_progression.max = max(total, 1)
        self.barre_progression.value = i

    @mainthread
    def _afficher_erreur(self, message):
        self.statut.text = f"Erreur : {message}"
        self.bouton_recherche.disabled = False
        self.barre_progression.height = 0

    @mainthread
    def _afficher_resultats(self, resultats, diagnostic=None):
        self.barre_progression.height = 0  # recherche terminée, quel qu'en soit le résultat

        # Sécurité supplémentaire : filtre les concours déjà supprimés
        resultats = [c for c in resultats if c["lien"] not in self.supprimes]
        self.dernier_diagnostic = diagnostic

        self.etat["derniere_recherche"] = datetime.now().isoformat()
        sauvegarder_etat(self.etat)

        self.statut.text = (
            f"{len(resultats)} concours trouvés — "
            f"maj le {datetime.now(timezone.utc):%d/%m/%Y %H:%M}"
        )

        if not resultats and diagnostic:
            # Mode hors-ligne : plutôt qu'une liste vide, on retombe sur le
            # dernier jeu de résultats obtenu avec succès (persisté sur
            # disque, survit aux redémarrages), avec un bandeau d'avertissement
            # bien visible — mieux qu'un écran vide en cas de réseau capricieux.
            derniers_resultats = charger_derniers_resultats()
            if derniers_resultats:
                self._resultats_bruts = derniers_resultats
                self._donnees_perimees = True
                self._appliquer_preferences()
                self.bouton_recherche.disabled = False
                return

            self._resultats_bruts = []
            self.resultats_actuels = []
            self._donnees_perimees = False
            self.liste.clear_widgets()
            lbl_msg = Label(
                text="Aucun concours trouvé. Vérifie ta connexion et réessaie, "
                     "ou consulte le détail technique ci-dessous.",
                size_hint_y=None, height=dp(50), font_size=sp(14),
                color=COULEUR_TEXTE_ATTENUE, halign="left", valign="middle",
            )
            lbl_msg.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.liste.add_widget(lbl_msg)

            bouton_reessayer = Button(
                text="Réessayer", bold=True, color=COULEUR_TEXTE_SUR_ACCENT,
                size_hint_y=None, height=dp(48),
            )
            stylise_bouton(bouton_reessayer, COULEUR_ACCENT, rayon=12)
            bouton_reessayer.bind(on_press=self.lancer_recherche)
            self.liste.add_widget(bouton_reessayer)

            for ligne_diag in diagnostic:
                lbl_diag = Label(
                    text=ligne_diag,
                    size_hint_y=None,
                    height=dp(40),
                    font_size=sp(11),
                    halign="left",
                    valign="top",
                    color=(1, 0.5, 0.5, 1),
                )
                # Largeur/hauteur liées dynamiquement au widget (au lieu d'une
                # taille en pixels bruts et d'une largeur figée) : le texte
                # reste lisible quelle que soit la densité de l'écran.
                lbl_diag.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
                lbl_diag.bind(texture_size=lambda inst, ts: setattr(inst, "height", max(ts[1], dp(20))))
                self.liste.add_widget(lbl_diag)
            self.bouton_recherche.disabled = False
            return

        # La liste brute n'est jamais filtrée par préférence ici : c'est
        # _appliquer_preferences qui dérive resultats_actuels à partir
        # d'elle, ce qui rend le filtrage réversible (voir plus haut).
        self._resultats_bruts = resultats
        self._donnees_perimees = False
        sauvegarder_derniers_resultats(resultats)
        self._appliquer_preferences()
        self.bouton_recherche.disabled = False

    def _filtrer_page(self, resultats, num_page):
        if num_page == 1:
            page = [c for c in resultats if c["score"] >= 10]
        elif num_page == 2:
            page = [c for c in resultats if 5 <= c["score"] <= 9]
        elif num_page == 3:
            page = [c for c in resultats if c["score"] < 5]
        else:  # num_page == 4 : onglet "RS" — concours à faire sur les réseaux sociaux
            page = [c for c in resultats if set(c.get("categories", [])) & CATEGORIES_RESEAUX_SOCIAUX]

        mot_cle = self.champ_recherche.text.strip().lower() if hasattr(self, "champ_recherche") else ""
        if mot_cle:
            page = [c for c in page if mot_cle in c["titre"].lower() or mot_cle in c.get("resume", "").lower()]

        # Le tri "score" n'a rien à faire : `resultats` est déjà trié par score
        # décroissant en amont (voir recuperer_concours). Les autres tris sont
        # appliqués ici, sur la page déjà filtrée (moins d'éléments à trier).
        tri = self.parametres.get("tri", "score") if hasattr(self, "parametres") else "score"
        if tri == "date":
            # Sans échéance connue = en dernier (date lointaine arbitraire),
            # plutôt que planter ou les mélanger au hasard.
            page = sorted(page, key=lambda c: c.get("date_limite_obj") or date.max)
        elif tri == "valeur":
            page = sorted(page, key=lambda c: c.get("valeur_estimee_nombre") or 0, reverse=True)
        elif tri == "alpha":
            page = sorted(page, key=lambda c: c["titre"].lower())

        return page

    def _afficher_page(self, reinitialiser=True):
        if reinitialiser:
            self.nb_affiches = self.TAILLE_LOT

        self._maj_badges_onglets()
        self.liste.clear_widgets()

        if getattr(self, "_donnees_perimees", False):
            lbl_perime = Label(
                text="ATTENTION : recherche impossible (réseau ?) — affichage des derniers "
                     "résultats connus, potentiellement anciens.",
                font_size=sp(11), bold=True, color=COULEUR_URGENCE,
                size_hint_y=None, height=dp(36), halign="left", valign="middle",
            )
            lbl_perime.bind(width=lambda inst, w: setattr(lbl_perime, "text_size", (w, None)))
            lbl_perime.bind(texture_size=lambda inst, ts: setattr(lbl_perime, "height", max(ts[1], dp(20))))
            self.liste.add_widget(lbl_perime)

        if self.page_actuelle == 4:
            for nom_reseau, url_template in RESEAUX_SOCIAUX_RECHERCHE:
                self._ajouter_ligne_reseau_social(nom_reseau, url_template)

        mot_cle = self.champ_recherche.text.strip() if hasattr(self, "champ_recherche") else ""
        page_complete = self._filtrer_page(self.resultats_actuels, self.page_actuelle)
        page = page_complete[: self.nb_affiches]

        self.statut.text = (
            f"{len(self.resultats_actuels)} concours au total — "
            f"{len(page_complete)} correspondent ({LIBELLES_PAGES[self.page_actuelle]})"
        )

        if not page_complete:
            message = (
                "Aucun concours trouvé pour l'instant. Lance une recherche !"
                if not self.resultats_actuels
                else "Aucun concours ne correspond à ce filtre."
            )
            lbl_vide = Label(
                text=message, font_size=sp(14), color=COULEUR_TEXTE_ATTENUE,
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
                font_size=sp(14), bold=True, color=(1, 1, 1, 1),
                size_hint_y=None, height=dp(48),
            )
            stylise_bouton(bouton_plus, COULEUR_ONGLET_INACTIF, rayon=12)
            bouton_plus.bind(on_press=lambda inst: self._afficher_plus())
            self.liste.add_widget(bouton_plus)

    def _afficher_plus(self):
        self.nb_affiches += self.TAILLE_LOT
        self._afficher_page(reinitialiser=False)

    def _ajouter_ligne_reseau_social(self, nom_reseau, url_template):
        """Une carte par réseau social (Instagram/TikTok/Facebook/X), affichée
        en colonne en haut de l'onglet "RS" — même style de carte que les
        concours, pour rester cohérent avec les autres onglets."""
        ligne = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54), spacing=dp(10),
                           padding=(dp(0), dp(0), dp(12), dp(0)))

        with ligne.canvas.before:
            Color(*COULEUR_CARTE_A)
            rect = RoundedRectangle(radius=[dp(16)], pos=ligne.pos, size=ligne.size)
            Color(*COULEUR_CARTE_BORDURE)
            bordure = Line(rounded_rectangle=(ligne.x, ligne.y, ligne.width, ligne.height, dp(16)), width=dp(1))

        def _sync_fond(inst, *_a):
            rect.pos = inst.pos
            rect.size = inst.size
            bordure.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, dp(16))

        ligne.bind(pos=_sync_fond, size=_sync_fond)

        item = Button(
            text=f"Chercher sur {nom_reseau} {ICONE_FLECHE}",
            halign="left",
            valign="middle",
            font_size=sp(15),
            bold=True,
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            color=COULEUR_TEXTE,
            padding=(dp(14), 0),
        )
        item.bind(size=lambda inst, val: setattr(item, "text_size", val))
        item.bind(on_press=lambda inst, tpl=url_template:
                   ouvrir_lien(url_reseau_social(tpl, self.champ_hashtag.text)))
        ligne.add_widget(item)

        self.liste.add_widget(ligne)

    def _ajouter_ligne_concours(self, i, c):
        libelle_palier, couleur_palier, icone_palier = infos_palier(c["score"])

        ligne = BoxLayout(orientation="horizontal", size_hint_y=None, spacing=dp(10),
                           padding=(dp(10), dp(10), dp(12), dp(10)))

        with ligne.canvas.before:
            Color(*COULEUR_CARTE_A)
            rect = RoundedRectangle(radius=[dp(16)], pos=ligne.pos, size=ligne.size)
            Color(*COULEUR_CARTE_BORDURE)
            bordure = Line(rounded_rectangle=(ligne.x, ligne.y, ligne.width, ligne.height, dp(16)), width=dp(1))

        def _sync_fond(inst, *_a):
            rect.pos = inst.pos
            rect.size = inst.size
            bordure.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, dp(16))

        ligne.bind(pos=_sync_fond, size=_sync_fond)

        # --- Vignette : image réelle du flux si disponible (rare pour Google
        # Actualités, plus fréquent sur GrattWeb/Concours.fr), sinon pastille
        # colorée par palier avec une étoile en filet de sécurité visuel. ---
        TAILLE_VIGNETTE = dp(64)
        if c.get("image_url"):
            vignette = AsyncImage(
                source=c["image_url"], size_hint=(None, None), size=(TAILLE_VIGNETTE, TAILLE_VIGNETTE),
                allow_stretch=True, keep_ratio=False,
            )
        else:
            vignette = BoxLayout(size_hint=(None, None), size=(TAILLE_VIGNETTE, TAILLE_VIGNETTE))
            with vignette.canvas.before:
                Color(*couleur_palier)
                vignette_rect = RoundedRectangle(radius=[dp(12)], pos=vignette.pos, size=vignette.size)
            vignette.bind(pos=lambda inst, val, r=vignette_rect: setattr(r, "pos", inst.pos))
            vignette.bind(size=lambda inst, val, r=vignette_rect: setattr(r, "size", inst.size))
            glyphe = Label(text=ICONE_ETOILE, font_size=sp(22), bold=True,
                           color=couleur_texte_badge(couleur_palier))
            vignette.add_widget(glyphe)
        ligne.add_widget(vignette)

        # --- Contenu principal (badge + titre + méta), prend toute la place restante ---
        contenu = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)

        ligne_badge = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))

        texte_badge = f"{icone_palier} {libelle_palier} - {c['score']} pts" if icone_palier else f"{libelle_palier} - {c['score']} pts"
        badge = Label(
            text=texte_badge,
            font_size=sp(10),
            bold=True,
            color=couleur_texte_badge(couleur_palier),
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

        date_obj = c.get("date_limite_obj")
        if date_obj:
            jours_restants = (date_obj - date.today()).days
            if 0 <= jours_restants <= 5:
                texte_urgence = "Dernier jour" if jours_restants == 0 else f"J-{jours_restants}"
                urgence = Label(
                    text=texte_urgence,
                    font_size=sp(9),
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
            font_size=sp(15),
            bold=True,
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            color=COULEUR_TEXTE,
        )

        # --- Méta : échéance textuelle sous le titre, façon mockup ---
        meta_texte = c.get("date_limite_texte") or ""
        meta = Label(
            text=meta_texte, font_size=sp(11), color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(16) if meta_texte else 0,
            halign="left", valign="middle",
        )
        meta.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        def _update_text_size(instance, width, item=item):
            item.text_size = (width - dp(6), None)

        def _update_hauteurs(instance, texture_size, ligne=ligne, contenu=contenu, item=item, meta=meta):
            item.height = texture_size[1]
            hauteur_contenu = texture_size[1] + dp(20) + dp(4) + meta.height + (dp(4) if meta_texte else 0)
            contenu.height = hauteur_contenu
            ligne.height = max(hauteur_contenu, TAILLE_VIGNETTE) + dp(20)

        item.bind(width=_update_text_size)
        item.bind(texture_size=_update_hauteurs)
        item.bind(on_press=lambda inst, c=c: self._afficher_details(c))
        contenu.add_widget(item)
        if meta_texte:
            contenu.add_widget(meta)
        ligne.add_widget(contenu)

        # --- Actions secondaires, regroupées à droite (favori en icône, puis suppression) ---
        actions = BoxLayout(orientation="vertical", size_hint=(None, 1), width=dp(48), spacing=dp(6))

        est_favori = self._est_favori(c["lien"])
        bouton_fav = Button(
            text=ICONE_FAVORI_PLEIN if est_favori else ICONE_FAVORI_VIDE,
            font_size=sp(10), bold=True,
            color=COULEUR_TEXTE_SUR_ACCENT if est_favori else COULEUR_TEXTE,
            size_hint=(None, None), size=(dp(40), dp(40)),
        )
        stylise_bouton(bouton_fav, COULEUR_ACCENT if est_favori else COULEUR_ONGLET_INACTIF, rayon=16)

        def _on_press_fav(inst, c=c, bouton_fav=bouton_fav):
            nouvel_etat = self._basculer_favori(c)
            bouton_fav.text = ICONE_FAVORI_PLEIN if nouvel_etat else ICONE_FAVORI_VIDE
            bouton_fav.couleur_instr.rgba = COULEUR_ACCENT if nouvel_etat else COULEUR_ONGLET_INACTIF
            bouton_fav.color = COULEUR_TEXTE_SUR_ACCENT if nouvel_etat else COULEUR_TEXTE

        bouton_fav.bind(on_press=_on_press_fav)
        actions.add_widget(bouton_fav)

        # Zone tactile élargie à dp(44) (minimum recommandé Android/WCAG pour une
        # cible tactile fiable) au lieu des dp(28) d'origine, trop petits.
        case = CheckBox(size_hint=(None, None), size=(dp(44), dp(44)), color=COULEUR_TEXTE)
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

        page = BoxLayout(orientation="vertical", padding=(dp(16), dp(42), dp(16), dp(40)), spacing=dp(10))

        # --- Barre du haut : retour + favori ---
        barre_haut = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(40), spacing=dp(8))
        bouton_retour = Button(text="< Retour", font_size=sp(13), bold=True, color=COULEUR_TEXTE,
                                size_hint=(None, 1), width=dp(90))
        stylise_bouton(bouton_retour, COULEUR_ONGLET_INACTIF, rayon=14)
        bouton_retour.bind(on_press=lambda inst: self._retour_a_la_liste())
        barre_haut.add_widget(bouton_retour)
        barre_haut.add_widget(BoxLayout())  # pousse le favori à droite

        est_favori = self._est_favori(c["lien"])
        bouton_favori = Button(
            text=f"{ICONE_FAVORI_PLEIN} favori" if est_favori else f"{ICONE_FAVORI_VIDE} favori",
            font_size=sp(12), bold=True,
            color=COULEUR_TEXTE_SUR_ACCENT if est_favori else COULEUR_TEXTE,
            size_hint=(None, 1), width=dp(90),
        )
        stylise_bouton(bouton_favori, COULEUR_ACCENT if est_favori else COULEUR_ONGLET_INACTIF, rayon=14)

        def _on_press_favori(inst):
            nouvel_etat = self._basculer_favori(c)
            bouton_favori.text = f"{ICONE_FAVORI_PLEIN} favori" if nouvel_etat else f"{ICONE_FAVORI_VIDE} favori"
            bouton_favori.couleur_instr.rgba = COULEUR_ACCENT if nouvel_etat else COULEUR_ONGLET_INACTIF
            bouton_favori.color = COULEUR_TEXTE_SUR_ACCENT if nouvel_etat else COULEUR_TEXTE

        bouton_favori.bind(on_press=_on_press_favori)
        barre_haut.add_widget(bouton_favori)

        bouton_partager = Button(text="Partager", font_size=sp(12), bold=True, color=COULEUR_TEXTE,
                                  size_hint=(None, 1), width=dp(84))
        stylise_bouton(bouton_partager, COULEUR_ONGLET_INACTIF, rayon=14)
        bouton_partager.bind(on_press=lambda inst, c=c: partager_concours(c["titre"], c["lien"]))
        barre_haut.add_widget(bouton_partager)
        page.add_widget(barre_haut)

        # --- Image hero (si le flux en fournit une) ---
        if c.get("image_url"):
            hero = AsyncImage(
                source=c["image_url"], size_hint=(1, None), height=dp(180),
                allow_stretch=True, keep_ratio=False,
            )
            page.add_widget(hero)

        # --- Contenu déroulant ---
        scroll = ScrollView()
        contenu = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, padding=(0, dp(8), 0, dp(8)))
        contenu.bind(minimum_height=contenu.setter("height"))

        libelle_palier, couleur_palier, icone_palier = infos_palier(c["score"])
        texte_badge = f"{icone_palier} {libelle_palier}" if icone_palier else libelle_palier
        badge = Label(
            text=texte_badge, font_size=sp(12), bold=True,
            color=couleur_texte_badge(couleur_palier),
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
            text=c["titre"], font_size=sp(24), bold=True, color=COULEUR_TEXTE,
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
                text=ICONE_ETOILE, font_size=sp(20), bold=True,
                color=COULEUR_PREMIUM if i < nb_etoiles else COULEUR_ONGLET_INACTIF,
                size_hint=(None, 1), width=dp(20),
            )
            ligne_etoiles.add_widget(etoile)
        ligne_etoiles.add_widget(BoxLayout())
        contenu.add_widget(ligne_etoiles)

        def _ajouter_section(titre_section, widget_valeur):
            contenu.add_widget(_widget_separateur())
            lbl_titre = Label(
                text=titre_section, font_size=sp(12), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(18), halign="left", valign="middle",
            )
            lbl_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(lbl_titre)
            contenu.add_widget(widget_valeur)

        # --- Valeur estimée (si détectée) ---
        if c.get("valeur_estimee"):
            lbl_valeur = Label(
                text=c["valeur_estimee"], font_size=sp(22), bold=True, color=COULEUR_PREMIUM,
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
                text=f"- {libelle}", font_size=sp(15), color=COULEUR_TEXTE,
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
                text=texte_echeance, font_size=sp(20), bold=True,
                color=COULEUR_URGENCE if jours_restants <= 5 else COULEUR_TEXTE,
                size_hint_y=None, height=dp(28), halign="left", valign="middle",
            )
            lbl_echeance.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            _ajouter_section("EXPIRE DANS", lbl_echeance)
        elif c.get("date_limite_texte"):
            lbl_echeance = Label(
                text=c["date_limite_texte"], font_size=sp(15), bold=True, color=COULEUR_URGENCE,
                size_hint_y=None, height=dp(22), halign="left", valign="middle",
            )
            lbl_echeance.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            _ajouter_section("ÉCHÉANCE", lbl_echeance)

        contenu.add_widget(_widget_separateur())

        statut_verif = Label(
            text="Vérification des informations sur la page du concours...",
            font_size=sp(12), color=COULEUR_TEXTE_ATTENUE,
            size_hint_y=None, height=dp(34), halign="left", valign="top",
        )
        statut_verif.bind(width=lambda inst, w: setattr(statut_verif, "text_size", (w, None)))
        contenu.add_widget(statut_verif)

        if c.get("resume"):
            lbl_resume_titre = Label(
                text="RÉSUMÉ", font_size=sp(12), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(18), halign="left", valign="middle",
            )
            lbl_resume_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(lbl_resume_titre)
            lbl_resume = Label(
                text=c["resume"], font_size=sp(13), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, halign="left", valign="top",
            )
            lbl_resume.bind(width=lambda inst, w: setattr(lbl_resume, "text_size", (w, None)))
            lbl_resume.bind(texture_size=lambda inst, ts: setattr(lbl_resume, "height", ts[1]))
            contenu.add_widget(lbl_resume)

        scroll.add_widget(contenu)
        page.add_widget(scroll)

        # --- Bouton d'action principal, fixe en bas de page ---
        bouton_ouvrir = Button(text=f"Voir le concours {ICONE_FLECHE}", font_size=sp(15), bold=True,
                                color=COULEUR_TEXTE_SUR_ACCENT, size_hint=(1, None), height=dp(52))
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
        entree = self._cache_pages.get(lien)
        cache_valide = entree and (time.time() - entree.get("horodatage", 0)) < DUREE_CACHE_PAGES_SECONDES

        if cache_valide:
            texte_page = entree["texte"]
        else:
            texte_page = recuperer_texte_page(lien)
            if texte_page is not None:
                self._cache_pages[lien] = {"texte": texte_page, "horodatage": time.time()}
                sauvegarder_cache_pages(self._cache_pages)

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
        self._resultats_bruts = [c for c in self._resultats_bruts if c["lien"] != lien]
        self.resultats_actuels = [c for c in self.resultats_actuels if c["lien"] != lien]
        self.liste.remove_widget(ligne)


# =============================== LANCEMENT =================================

if __name__ == "__main__":
    import traceback

    try:
        ConcoursFinderApp().run()
    except Exception:
        # Ne couvre QUE les erreurs survenant après l'import réussi de tous les
        # modules (Kivy, feedparser, certifi...) — un échec d'import plante
        # Python avant même d'atteindre ce bloc, donc ce cas-là reste à
        # diagnostiquer via adb logcat. Utile pour les bugs runtime (KeyError,
        # AttributeError dans le code UI...) qui, eux, surviennent après le
        # lancement et ne laissaient auparavant aucune trace récupérable sans
        # câble/adb.
        trace = traceback.format_exc()
        print(trace)
        try:
            chemin = _chemin_fichier(FICHIER_JOURNAL_CRASH)
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()}\n\n{trace}")
        except Exception:
            pass
        raise
