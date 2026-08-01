"""
Constantes de Concours Finder : palette de couleurs, icônes, noms de
fichiers de stockage, liste des flux RSS et listes de mots-clés utilisées
pour le scoring et la détection.

Ce module ne dépend d'aucun package Kivy : il peut être importé (et testé)
sans que Kivy soit installé.
"""

from urllib.parse import quote_plus

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

# --- Fichiers de stockage local (dans le dossier de données de l'app) ---
FICHIER_SUPPRIMES = "concours_supprimes.json"
FICHIER_PREFERENCES = "preferences.json"
FICHIER_FAVORIS = "favoris.json"
FICHIER_HISTORIQUE = "historique.json"
FICHIER_ETAT = "etat_app.json"
FICHIER_CACHE_FLUX = "cache_flux.json"

# --- Paramètres réseau ---
TIMEOUT_RESEAU = 10                    # secondes avant abandon d'un flux injoignable
MAX_FLUX_PARALLELES = 18               # téléchargements simultanés max
JOURS_MAX_ANCIENNETE = 45              # articles plus vieux que ça = probablement terminés
DUREE_CACHE_FLUX_SECONDES = 30 * 60    # un flux réutilisé depuis le cache pendant 30 min


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

    # --- Mots-clés génériques ---
    _url_google_news('"jeu concours"'),
    _url_google_news('"instant gagnant"'),
    _url_google_news('"tirage au sort"'),
    _url_google_news("gagnez"),

    # --- Marques, regroupées par secteur (voir _url_groupee ci-dessus) ---
    _url_groupee(["Carrefour", "E.Leclerc", "Lidl", "Auchan", "Intermarché",
                  "Super U", "Monoprix", "Casino"]),                              # grande distribution
    _url_groupee(["Fnac", "Darty", "Boulanger", "Cdiscount", "Amazon France"]),    # high-tech / e-commerce
    _url_groupee(["Disney", "Pixar", "Marvel", "TF1", "M6", "France TV",
                  "NRJ", "RTL", "Europe 1", "RMC"]),                              # divertissement / médias
    _url_groupee(["PlayStation", "Xbox", "Nintendo", "Steam", "Epic Games",
                  "Ubisoft", "EA", "Riot Games", "Blizzard", "Rockstar Games"]),  # jeux vidéo
    _url_groupee(["LEGO", "Mattel", "Hasbro"]),                                   # jouets
    _url_groupee(["Kinder", "Haribo", "Nutella", "Milka", "Coca-Cola",
                  "Pepsi", "Red Bull", "Oreo", "LU"]),                            # confiserie / boissons
    _url_groupee(["Michelin", "Renault", "Peugeot", "Citroën", "Dacia"]),         # automobile
    _url_groupee(["Samsung", "LG", "Sony", "Asus", "Acer", "HP", "Dell", "Lenovo"]),  # électronique
    _url_groupee(["Orange", "SFR", "Free", "Bouygues Telecom", "Canal+",
                  "Netflix", "Prime Video", "Disney+"]),                          # télécom / streaming
    _url_groupee(["Decathlon", "Intersport", "Go Sport", "Sephora",
                  "Yves Rocher", "Nocibé", "L'Oréal"]),                           # sport / beauté
    _url_groupee(["KFC", "McDonald's", "Burger King", "Domino's Pizza"]),         # restauration rapide
    _url_groupee(["IKEA", "Leroy Merlin", "Castorama", "Brico Dépôt"]),           # bricolage / déco
    _url_groupee(["Air France", "SNCF", "Accor", "Pierre & Vacances"]),           # voyage

    # --- Réseaux sociaux / créateurs de contenu ---
    # Instagram et TikTok n'ont pas de flux RSS publics (ce sont des posts,
    # pas des pages web indexables) : impossible de suivre un concours natif
    # directement. En revanche, Google Actualités remonte bien les articles
    # de blogs/presse qui ANNONCENT ce type de concours ("gagnez en likant
    # sur Instagram...") : c'est ce qu'on cible ici, regroupé en une requête.
    _url_google_news(
        '"concours instagram" OR "concours tiktok" OR "concours facebook" OR '
        '"concours twitter" OR "concours créateur" OR "concours influenceur" OR '
        '"concours youtubeur" OR (giveaway instagram concours)'
    ),

    # Deux sites spécialisés qui référencent notamment des concours créateurs /
    # réseaux sociaux. Leur flux RSS n'a pas pu être confirmé publiquement
    # depuis cet environnement (adresse déduite de la convention WordPress
    # /feed/) : si l'URL est incorrecte, le diagnostic technique l'indiquera
    # simplement (0 entrée ou erreur), sans rien casser dans l'app.
    "https://aldabro-concours.com/feed/",
    "https://www.jouer-gagnant-concept.com/feed/",
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
