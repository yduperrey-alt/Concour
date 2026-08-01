"""
Tests unitaires du module `constantes` : construction des URLs de recherche
hashtag pour les réseaux sociaux (Instagram/TikTok/Facebook/X).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constantes import HASHTAG_PAR_DEFAUT, normaliser_hashtag, url_reseau_social


class TestNormaliserHashtag(unittest.TestCase):
    def test_retire_le_diese(self):
        self.assertEqual(normaliser_hashtag("#jeuconcours"), "jeuconcours")

    def test_retire_les_espaces(self):
        self.assertEqual(normaliser_hashtag("jeu concours"), "jeuconcours")

    def test_texte_vide_renvoie_le_defaut(self):
        self.assertEqual(normaliser_hashtag(""), HASHTAG_PAR_DEFAUT)
        self.assertEqual(normaliser_hashtag("   "), HASHTAG_PAR_DEFAUT)

    def test_encode_les_caracteres_speciaux(self):
        # Les accents/caractères spéciaux doivent être encodés pour rester
        # valides dans une URL (ex: "voyagé" -> "voyag%C3%A9")
        self.assertIn("%", normaliser_hashtag("voyagé!"))


class TestUrlReseauSocial(unittest.TestCase):
    def test_insere_le_hashtag_dans_le_template(self):
        url = url_reseau_social("https://www.tiktok.com/tag/{hashtag}", "iphone")
        self.assertEqual(url, "https://www.tiktok.com/tag/iphone")

    def test_avec_diese_et_espaces(self):
        url = url_reseau_social("https://x.com/hashtag/{hashtag}", "# jeu concours ")
        self.assertEqual(url, "https://x.com/hashtag/jeuconcours")

    def test_hashtag_vide_utilise_le_defaut(self):
        url = url_reseau_social("https://www.instagram.com/explore/tags/{hashtag}/", "")
        self.assertIn(HASHTAG_PAR_DEFAUT, url)


if __name__ == "__main__":
    unittest.main()
