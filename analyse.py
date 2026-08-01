"""
Analyse et scoring des entrées RSS : détection des vrais jeux-concours,
calcul du score de lot, extraction de date limite / valeur estimée,
déduplication...

Toutes les fonctions ici sont pures (pas d'effet de bord, pas de dépendance
Kivy) : elles se testent facilement sans lancer l'application (voir
tests/test_analyse.py).
"""

import difflib
import html
import re
from datetime import date, datetime

from constantes import (
    CATEGORIES_PARTICIPATION,
    INDICES_INFO_POSITIFS,
    LOTS_BASIQUES,
    LOTS_MOYENS,
    LOTS_PREMIUM,
    MOIS_FR,
    MOTS_CLE_DATE_LIMITE,
    MOTS_EXCLUS,
    MOTS_SANS_ACHAT,
    SIGNAUX_CONCOURS,
    COULEUR_BASIQUE,
    COULEUR_MOYEN,
    COULEUR_PREMIUM,
    ICONE_ETOILE,
)


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


def infos_palier(score: int):
    """Renvoie (libellé, couleur, icône) selon le palier de score du concours.
    Centralise la hiérarchie visuelle façon "streaming" : l'or n'est utilisé
    que pour les vrais gros lots, pour garder tout son impact."""
    if score >= 10:
        return "TOP LOT", COULEUR_PREMIUM, ICONE_ETOILE
    elif score >= 5:
        return "BON PLAN", COULEUR_MOYEN, ""
    return "PETIT LOT", COULEUR_BASIQUE, ""
