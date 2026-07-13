"""
Concours Finder — application Android (Kivy)
Recherche des jeux concours via flux RSS, les classe par score de lot,
et affiche la liste dans une interface tactile.
"""

import json
import os
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

from kivy.app import App
from kivy.clock import mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivy.metrics import dp

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
                "macbook", "croisière", "week-end", "smartphone", "console"]
LOTS_MOYENS = ["bon d'achat", "carte cadeau", "livre", "coffret", "place de cinéma",
               "abonnement", "cosmétique", "pokemon", "yu-gi-oh", "souris", "casque",
               "cuisine", "enceinte"]
MOTS_SANS_ACHAT = ["sans obligation d'achat", "gratuit"]


def score_concours(titre: str, resume: str) -> int:
    texte = f"{titre} {resume}".lower()
    score = 0
    for mot in LOTS_PREMIUM:
        if mot in texte:
            score += 10
    for mot in LOTS_MOYENS:
        if mot in texte:
            score += 5
    for mot in MOTS_SANS_ACHAT:
        if mot in texte:
            score += 3
    return score


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

            resultats.append({
                "titre": titre,
                "lien": lien,
                "date_publication": date_pub,
                "score": score_concours(titre, resume),
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


class ConcoursFinderApp(App):
    def build(self):
        self.title = "Concours Finder"
        self.supprimes = charger_supprimes()
        root = BoxLayout(orientation="vertical", padding=(dp(10), dp(45), dp(10), dp(10)), spacing=10)

        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=50, spacing=10)
        self.bouton_recherche = Button(text="Rechercher les concours")
        self.bouton_recherche.bind(on_press=self.lancer_recherche)
        header.add_widget(self.bouton_recherche)
        root.add_widget(header)

        self.statut = Label(text="Appuie sur le bouton pour lancer la recherche.",
                             size_hint=(1, None), height=30)
        root.add_widget(self.statut)

        self.scroll = ScrollView()
        self.liste = GridLayout(cols=1, spacing=8, size_hint_y=None, padding=(0, 5))
        self.liste.bind(minimum_height=self.liste.setter("height"))
        self.scroll.add_widget(self.liste)
        root.add_widget(self.scroll)

        return root

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

        for i, c in enumerate(resultats[:TOP_N], 1):
            self._ajouter_ligne_concours(i, c)
        self.bouton_recherche.disabled = False

    def _ajouter_ligne_concours(self, i, c):
        ligne = BoxLayout(orientation="horizontal", size_hint_y=None, height=70, spacing=8)

        case = CheckBox(size_hint=(None, None), size=(40, 40))
        case.bind(active=lambda inst, valeur, lien=c["lien"], ligne=ligne:
                  self._supprimer_concours(lien, ligne) if valeur else None)
        case_wrap = BoxLayout(size_hint=(None, 1), width=50)
        case_wrap.add_widget(case)
        ligne.add_widget(case_wrap)

        item = Button(
            text=f"[{c['score']} pts] {i}. {c['titre']}",
            halign="left",
            valign="middle",
            text_size=(None, None),
        )
        item.bind(size=lambda inst, val: setattr(item, "text_size", (item.width, None)))
        item.bind(on_press=lambda inst, lien=c["lien"]: ouvrir_lien(lien))
        ligne.add_widget(item)

        self.liste.add_widget(ligne)

    def _supprimer_concours(self, lien, ligne):
        """Coché = suppression définitive du concours de la liste et du stockage."""
        self.supprimes.add(lien)
        sauvegarder_supprimes(self.supprimes)
        self.liste.remove_widget(ligne)


if __name__ == "__main__":
    ConcoursFinderApp().run()
