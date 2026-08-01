"""
Tests unitaires du module `analyse` (scoring, détection, extraction de
dates/valeurs). Ces fonctions sont pures : aucune dépendance à Kivy n'est
nécessaire pour les exécuter.

Lancer avec :  python -m unittest discover -s tests -v
"""

import sys
import unittest
from datetime import date
from pathlib import Path

# Permet de lancer les tests directement (python tests/test_analyse.py)
# sans avoir à installer le projet comme package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyse import (
    deduplique_concours,
    detecter_categories_requises,
    detecter_infos_requises,
    est_probablement_une_actualite,
    etoiles_pour_score,
    extraire_date_limite,
    extraire_valeur_estimee,
    infos_palier,
    nettoyer_html,
    nettoyer_titre_source,
    normaliser_titre,
    score_concours,
)


class TestScoreConcours(unittest.TestCase):
    def test_lot_premium_note_plus_que_lot_basique(self):
        score_voiture = score_concours("Gagnez une voiture", "concours")
        score_cadeau = score_concours("Gagnez un cadeau", "concours")
        self.assertGreater(score_voiture, score_cadeau)

    def test_plusieurs_lots_cumulent_le_score(self):
        score_seul = score_concours("Gagnez un iPhone", "")
        score_double = score_concours("Gagnez un iPhone et une PS5", "")
        self.assertGreater(score_double, score_seul)

    def test_aucun_lot_connu_renvoie_score_plancher(self):
        # Aucun mot-clé de LOTS_* dans le texte : score plancher de 1, jamais 0.
        self.assertEqual(score_concours("Grand concours mystère", "à gagner"), 1)

    def test_sans_obligation_achat_donne_un_bonus(self):
        score_normal = score_concours("Gagnez un cadeau", "")
        score_sans_achat = score_concours("Gagnez un cadeau", "sans obligation d'achat")
        self.assertGreater(score_sans_achat, score_normal)


class TestDetectionActualite(unittest.TestCase):
    def test_concours_de_recrutement_est_ecarte(self):
        self.assertTrue(est_probablement_une_actualite(
            "Résultats du concours de recrutement", "candidature ouverte"
        ))

    def test_vrai_jeu_concours_nest_pas_ecarte(self):
        self.assertFalse(est_probablement_une_actualite(
            "Grand jeu concours pour gagner un séjour", "tirage au sort le 1er juin"
        ))


class TestDetectionCategories(unittest.TestCase):
    def test_detecte_instagram(self):
        categories = detecter_categories_requises(
            "Jeu concours", "Rendez-vous sur Instagram pour participer"
        )
        self.assertIn("instagram", categories)

    def test_aucune_categorie_si_rien_ne_matche(self):
        categories = detecter_categories_requises("Jeu concours", "Tentez votre chance")
        self.assertEqual(categories, [])

    def test_detecter_infos_requises_inclut_infos_positives(self):
        infos = detecter_infos_requises("Concours gratuit", "sans obligation d'achat, tirage au sort")
        self.assertIn("Sans obligation d'achat", infos)
        self.assertIn("Tirage au sort parmi les participants", infos)


class TestExtractionDateLimite(unittest.TestCase):
    def test_date_numerique(self):
        texte_affiche, d = extraire_date_limite("Jouez jusqu'au 25/12/2026 pour participer")
        self.assertEqual(d, date(2026, 12, 25))
        self.assertIn("25/12/2026", texte_affiche)

    def test_date_en_lettres(self):
        texte_affiche, d = extraire_date_limite("Offre valable jusqu'au 3 janvier 2027")
        self.assertEqual(d, date(2027, 1, 3))

    def test_annee_sur_deux_chiffres(self):
        _texte, d = extraire_date_limite("Jusqu'au 01/02/26")
        self.assertEqual(d, date(2026, 2, 1))

    def test_aucune_date_renvoie_none(self):
        texte_affiche, d = extraire_date_limite("Participez sans limite de temps")
        self.assertIsNone(texte_affiche)
        self.assertIsNone(d)

    def test_date_invalide_ignoree(self):
        # 32 n'est pas un jour valide : ne doit pas planter, doit renvoyer None
        texte_affiche, d = extraire_date_limite("Jusqu'au 32/13/2026")
        self.assertIsNone(d)


class TestExtractionValeur(unittest.TestCase):
    def test_valeur_simple(self):
        self.assertEqual(extraire_valeur_estimee("d'une valeur de 550€"), "550 €")

    def test_valeur_avec_separateur_milliers(self):
        self.assertEqual(extraire_valeur_estimee("un lot de 1 200 euros"), "1 200 €")

    def test_garde_la_plus_grosse_valeur(self):
        self.assertEqual(extraire_valeur_estimee("2€ le ticket, lot d'une valeur de 800€"), "800 €")

    def test_montant_derisoire_ignore(self):
        self.assertIsNone(extraire_valeur_estimee("ticket à 1€"))

    def test_aucun_montant(self):
        self.assertIsNone(extraire_valeur_estimee("Gagnez un superbe cadeau"))


class TestEtoilesPourScore(unittest.TestCase):
    def test_paliers(self):
        self.assertEqual(etoiles_pour_score(0), 1)
        self.assertEqual(etoiles_pour_score(3), 2)
        self.assertEqual(etoiles_pour_score(6), 3)
        self.assertEqual(etoiles_pour_score(10), 4)
        self.assertEqual(etoiles_pour_score(20), 5)


class TestInfosPalier(unittest.TestCase):
    def test_top_lot_a_partir_de_10(self):
        libelle, _couleur, _icone = infos_palier(10)
        self.assertEqual(libelle, "TOP LOT")

    def test_petit_lot_sous_5(self):
        libelle, _couleur, _icone = infos_palier(2)
        self.assertEqual(libelle, "PETIT LOT")


class TestNettoyageTexte(unittest.TestCase):
    def test_nettoyer_html_retire_balises_et_entites(self):
        self.assertEqual(nettoyer_html("<p>Gagnez &amp; profitez</p>"), "Gagnez & profitez")

    def test_nettoyer_titre_source_retire_suffixe_site(self):
        titre = nettoyer_titre_source("Un lot exceptionnel à gagner - EchantillonsClub.com")
        self.assertNotIn("EchantillonsClub", titre)

    def test_nettoyer_titre_source_garde_titre_si_suffixe_fait_partie_du_titre(self):
        titre = "Grand jeu concours - gagnez un iPhone 16"
        self.assertEqual(nettoyer_titre_source(titre), titre)

    def test_normaliser_titre_retire_ponctuation(self):
        self.assertEqual(normaliser_titre("Gagnez un iPhone !"), "gagnez un iphone")


class TestDeduplication(unittest.TestCase):
    def test_fusionne_titres_quasi_identiques(self):
        resultats = [
            {"titre": "Gagnez un iPhone 16 avec la marque X", "lien": "a", "score": 10},
            {"titre": "Gagnez un iPhone 16 avec la marque X !", "lien": "b", "score": 8},
            {"titre": "Gagnez un tout autre lot complètement différent", "lien": "c", "score": 5},
        ]
        dedupe = deduplique_concours(resultats)
        self.assertEqual(len(dedupe), 2)
        self.assertEqual(dedupe[0]["lien"], "a")  # le mieux noté des deux doublons est gardé


if __name__ == "__main__":
    unittest.main()
