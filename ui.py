"""
Interface utilisateur (Kivy) de Concours Finder : construction des écrans,
gestion des favoris/historique/préférences, affichage de la liste de
concours et de la fiche détail.
"""

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
from kivy.uix.widget import Widget
from kivy.metrics import dp

from analyse import detecter_infos_requises, etoiles_pour_score, infos_palier
from constantes import (
    CATEGORIES_PARTICIPATION,
    CATEGORIES_RESEAUX_SOCIAUX,
    COULEUR_ACCENT,
    COULEUR_CARTE_A,
    COULEUR_CARTE_BORDURE,
    COULEUR_FOND,
    COULEUR_ONGLET_INACTIF,
    COULEUR_PREMIUM,
    COULEUR_TEXTE,
    COULEUR_TEXTE_ATTENUE,
    COULEUR_URGENCE,
    ICONE_ETOILE,
    ICONE_FAVORI_PLEIN,
    ICONE_FAVORI_VIDE,
    ICONE_FERMER,
    ICONE_FLECHE,
    RESEAUX_SOCIAUX_RECHERCHE,
    HASHTAG_PAR_DEFAUT,
    url_reseau_social,
)
from reseau import _nom_source, ouvrir_lien, recuperer_concours, recuperer_texte_page
from stockage import (
    charger_etat,
    charger_favoris,
    charger_historique,
    charger_preferences,
    charger_supprimes,
    sauvegarder_etat,
    sauvegarder_favoris,
    sauvegarder_historique,
    sauvegarder_preferences,
    sauvegarder_supprimes,
)

Window.clearcolor = COULEUR_FOND


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
        self.title = "Concours Finder"
        self.supprimes = charger_supprimes()
        self.preferences = charger_preferences()
        self.favoris = charger_favoris()
        self.historique = charger_historique()
        self.etat = charger_etat()
        # _resultats_bruts : dernier résultat de recherche réseau, JAMAIS modifié
        # par un changement de préférences. resultats_actuels : vue filtrée
        # dérivée de _resultats_bruts, recalculée à chaque changement de
        # préférences (voir _appliquer_preferences) — ce qui rend le filtrage
        # par préférence entièrement réversible sans relancer de recherche.
        self._resultats_bruts = []
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
            4: "RS",
        }
        for num_page, libelle in libelles_pages.items():
            btn = Button(text=libelle, font_size=dp(11), bold=True, color=COULEUR_TEXTE)
            stylise_bouton(btn, COULEUR_ONGLET_INACTIF, rayon=16)
            btn.bind(on_press=lambda inst, p=num_page: self._changer_page(p))
            onglets.add_widget(btn)
            self.boutons_pages[num_page] = btn
        root.add_widget(onglets)

        # --- Recherche manuelle sur les réseaux sociaux, visible uniquement
        # sur l'onglet "RS" (Instagram/TikTok n'ont pas de flux RSS public,
        # donc pas d'indexation automatique possible — voir RESEAUX_SOCIAUX_RECHERCHE). ---
        self.bloc_reseaux = BoxLayout(orientation="vertical", size_hint=(1, None), height=0, spacing=dp(4))
        self.bloc_reseaux.opacity = 0
        lbl_reseaux = Label(
            text="Chercher un hashtag sur :",
            font_size=dp(10), color=COULEUR_TEXTE_ATTENUE,
            size_hint=(1, None), height=dp(14), halign="left", valign="middle",
        )
        lbl_reseaux.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.bloc_reseaux.add_widget(lbl_reseaux)

        # Champ modifiable : "jeuconcours" par défaut, mais l'utilisateur
        # peut taper n'importe quel autre mot-clé (ex: "iphone", "voyage"...)
        # avant d'appuyer sur un des boutons ci-dessous.
        ligne_hashtag = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(36), spacing=dp(4))
        lbl_diese = Label(
            text="#", font_size=dp(15), bold=True, color=COULEUR_TEXTE_ATTENUE,
            size_hint=(None, 1), width=dp(14),
        )
        ligne_hashtag.add_widget(lbl_diese)
        self.champ_hashtag = TextInput(
            text=HASHTAG_PAR_DEFAUT,
            multiline=False,
            size_hint=(1, 1),
            font_size=dp(13),
            background_color=COULEUR_CARTE_A,
            foreground_color=COULEUR_TEXTE,
            hint_text_color=COULEUR_TEXTE_ATTENUE,
            cursor_color=COULEUR_ACCENT,
            padding=(dp(10), dp(8)),
        )
        ligne_hashtag.add_widget(self.champ_hashtag)
        self.bloc_reseaux.add_widget(ligne_hashtag)

        ligne_reseaux_boutons = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(32), spacing=dp(6))
        for nom_reseau, url_template in RESEAUX_SOCIAUX_RECHERCHE:
            btn_reseau = Button(text=nom_reseau, font_size=dp(11), bold=True, color=COULEUR_TEXTE, size_hint=(1, 1))
            stylise_bouton(btn_reseau, COULEUR_ONGLET_INACTIF, rayon=14)
            btn_reseau.bind(
                on_press=lambda inst, tpl=url_template:
                    ouvrir_lien(url_reseau_social(tpl, self.champ_hashtag.text))
            )
            ligne_reseaux_boutons.add_widget(btn_reseau)
        self.bloc_reseaux.add_widget(ligne_reseaux_boutons)
        root.add_widget(self.bloc_reseaux)

        self._maj_style_onglets()
        self._maj_visibilite_reseaux_sociaux()

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
            self._appliquer_preferences()
            popup.dismiss()

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

    def _maj_visibilite_reseaux_sociaux(self):
        """Le bloc de recherche manuelle Instagram/TikTok/Facebook/X n'a de
        sens que sur l'onglet "RS" : masqué (hauteur 0) sur les autres."""
        visible = self.page_actuelle == 4
        self.bloc_reseaux.height = dp(90) if visible else 0
        self.bloc_reseaux.opacity = 1 if visible else 0

    def _changer_page(self, num_page):
        self.page_actuelle = num_page
        self._maj_style_onglets()
        self._maj_visibilite_reseaux_sociaux()
        self._afficher_page()

    def lancer_recherche(self, instance, forcer=False):
        self.bouton_recherche.disabled = True
        self.statut.text = "Recherche en cours..."
        self.liste.clear_widgets()
        threading.Thread(target=self._recherche_thread, args=(forcer,), daemon=True).start()

    def _recherche_thread(self, forcer=False):
        try:
            resultats, diagnostic = recuperer_concours(
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
        self.dernier_diagnostic = diagnostic

        self.etat["derniere_recherche"] = datetime.now().isoformat()
        sauvegarder_etat(self.etat)

        self.statut.text = (
            f"{len(resultats)} concours trouvés — "
            f"maj le {datetime.now(timezone.utc):%d/%m/%Y %H:%M}"
        )

        if not resultats and diagnostic:
            self._resultats_bruts = []
            self.resultats_actuels = []
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
                lbl_diag = Label(
                    text=ligne_diag,
                    size_hint_y=None,
                    height=dp(40),
                    font_size=dp(11),
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
        return page

    def _afficher_page(self, reinitialiser=True):
        if reinitialiser:
            self.nb_affiches = self.TAILLE_LOT

        self.liste.clear_widgets()
        mot_cle = self.champ_recherche.text.strip() if hasattr(self, "champ_recherche") else ""
        page_complete = self._filtrer_page(self.resultats_actuels, self.page_actuelle)
        page = page_complete[: self.nb_affiches]

        libelles = {1: "Top lots", 2: "Bons plans", 3: "Petits lots", 4: "RS"}
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

        page = BoxLayout(orientation="vertical", padding=(dp(16), dp(42), dp(16), dp(40)), spacing=dp(10))

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
        self._resultats_bruts = [c for c in self._resultats_bruts if c["lien"] != lien]
        self.resultats_actuels = [c for c in self.resultats_actuels if c["lien"] != lien]
        self.liste.remove_widget(ligne)
