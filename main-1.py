"""
Concours Finder — application Android (Kivy)
Recherche des jeux concours via flux RSS, les classe par score de lot,
et affiche la liste dans une interface tactile.

Point d'entrée : la logique est répartie dans des modules dédiés pour la
maintenabilité (voir chacun pour le détail) :
  - constantes.py : couleurs, icônes, flux RSS, listes de mots-clés
  - analyse.py    : scoring / détection / extraction (fonctions pures, testées)
  - stockage.py   : persistance locale (favoris, historique, préférences...)
  - reseau.py     : téléchargement des flux RSS, ouverture de liens
  - ui.py         : interface Kivy (ConcoursFinderApp)
"""

from ui import ConcoursFinderApp

if __name__ == "__main__":
    ConcoursFinderApp().run()
