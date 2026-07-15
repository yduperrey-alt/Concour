"""
Concours Finder — application Android (Kivy)
Recherche des jeux concours via flux RSS, les classe par score de lot,
et affiche la liste dans une interface tactile.
"""

import html
import json
import os
import re
import socket
import ssl
import threading
import certifi
import feedparser
from datetime import datetime, timezone

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
INDICES_PARTICIPATION = [
    (["instagram"], "📸 Suivre / liker sur Instagram"),
    (["facebook"], "👍 Suivre / liker sur Facebook"),
    (["tiktok"], "🎵 Suivre sur TikTok"),
    (["twitter", "compte x ", " sur x "], "🐦 Suivre sur X (Twitter)"),
    (["newsletter"], "📩 S'inscrire à la newsletter"),
    (["e-mail", "email", "adresse mail", "adresse e-mail"], "✉️ Fournir une adresse e-mail"),
    (["nom et prénom", "nom, prénom", "vos coordonnées", "civilité"], "📝 Fournir nom et prénom"),
    (["formulaire"], "📋 Remplir un formulaire"),
    (["créer un compte", "création de compte", "inscription sur le site"], "👤 Créer un compte"),
    (["laisser un avis", "avis client"], "⭐ Laisser un avis"),
    (["partager", "partage la publication", "partagez"], "🔁 Partager la publication"),
    (["s'abonner", "abonnement gratuit", "abonnez-vous"], "🔔 S'abonner"),
    (["tirage au sort"], "🎲 Tirage au sort parmi les participants"),
    (["sans obligation d'achat", "sans achat"], "🆓 Sans obligation d'achat"),
    (["gratuit", "gratuitement"], "🆓 Participation gratuite"),
]


def detecter_infos_requises(titre: str, resume: str) -> list:
    texte = f"{titre} {resume}".lower()
    trouves = []
    for mots, libelle in INDICES_PARTICIPATION:
        if any(m in texte for m in mots) and libelle not in trouves:
            trouves.append(libelle)
    return trouves


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


def recuperer_concours():
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

            resultats.append({
                "titre": titre,
                "lien": lien,
                "date_publication": date_pub,
                "resume": nettoyer_html(resume),
                "score": score,
                "source": url,
            })

        nb_ajoutes = len(resultats) - nb_avant
        detail = f"{url} -> {nb_ajoutes} entrée(s), http={statut_http}"
        if bozo:
            detail += f", erreur parsing: {bozo_msg}"
        diagnostic.append(detail)

    resultats.sort(key=lambda c: c["score"], reverse=True)
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
        self.resultats_actuels = []
        self.page_actuelle = 1
        root = BoxLayout(orientation="vertical", padding=(dp(14), dp(45), dp(14), dp(14)), spacing=dp(12))

        # --- En-tête ---
        entete = BoxLayout(orientation="vertical", size_hint=(1, None), height=dp(46), spacing=dp(2))
        titre_app = Label(
            text="🎁 Concours Finder",
            font_size=dp(24),
            bold=True,
            color=COULEUR_TEXTE,
            size_hint=(1, None),
            height=dp(32),
            halign="left",
            valign="middle",
        )
        titre_app.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        entete.add_widget(titre_app)
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
        try:
            resultats, diagnostic = recuperer_concours()
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
        ligne_badge.add_widget(BoxLayout())  # pousse le badge à gauche
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
        """Popup listant les conditions probables de participation, avec un lien vers le concours."""
        contenu = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))

        infos = detecter_infos_requises(c["titre"], c.get("resume", ""))
        if infos:
            sous_titre = Label(
                text="Ce qu'il faudra probablement fournir :",
                font_size=dp(13), bold=True, color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(24), halign="left", valign="middle",
            )
            sous_titre.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(sous_titre)

            bloc_infos = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
            bloc_infos.bind(minimum_height=bloc_infos.setter("height"))
            for libelle in infos:
                lbl = Label(
                    text=libelle, font_size=dp(14), color=COULEUR_TEXTE,
                    size_hint_y=None, height=dp(26), halign="left", valign="middle",
                )
                lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
                bloc_infos.add_widget(lbl)
            contenu.add_widget(bloc_infos)
        else:
            lbl = Label(
                text="Les conditions ne sont pas précisées dans le résumé : "
                     "consulte la page du concours pour les connaître.",
                font_size=dp(13), color=COULEUR_TEXTE_ATTENUE,
                size_hint_y=None, height=dp(50), halign="left", valign="top",
            )
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            contenu.add_widget(lbl)

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

    def _supprimer_concours(self, lien, ligne):
        """Coché = suppression définitive du concours de la liste et du stockage."""
        self.supprimes.add(lien)
        sauvegarder_supprimes(self.supprimes)
        self.resultats_actuels = [c for c in self.resultats_actuels if c["lien"] != lien]
        self.liste.remove_widget(ligne)


if __name__ == "__main__":
    ConcoursFinderApp().run()
