"""Génère les icônes de la PWA : champignon stylisé, chapeau brun uni, sur fond vert forêt.

Pas de chapeau rouge à points blancs, qui évoquerait l'amanite tue-mouches (toxique).

Usage : python web/scripts/generer_icones.py (depuis la racine du dépôt, avec Pillow).
"""

from pathlib import Path

from PIL import Image, ImageDraw

FOND = (31, 61, 43)
CHAPEAU = (139, 90, 43)
PIED = (244, 241, 234)
SORTIE = Path(__file__).resolve().parent.parent / "public" / "icons"


def icone(taille: int, marge: float) -> Image.Image:
    """`marge` : part de l'icône laissée libre autour du motif (zone sûre des icônes masquables)."""
    echelle = 4  # dessin suréchantillonné puis réduit, pour adoucir les bords
    t = taille * echelle
    image = Image.new("RGB", (t, t), FOND)
    d = ImageDraw.Draw(image)
    m = t * marge
    zone = t - 2 * m
    cx = t / 2
    largeur_pied = zone * 0.26
    d.rounded_rectangle(
        (cx - largeur_pied / 2, m + zone * 0.40, cx + largeur_pied / 2, m + zone * 0.95),
        radius=largeur_pied * 0.35, fill=PIED,
    )
    d.pieslice((m, m + zone * 0.08, m + zone, m + zone * 0.88), 180, 360, fill=CHAPEAU)
    return image.resize((taille, taille), Image.LANCZOS)


SORTIE.mkdir(parents=True, exist_ok=True)
icone(192, 0.12).save(SORTIE / "icone-192.png", optimize=True)
icone(512, 0.12).save(SORTIE / "icone-512.png", optimize=True)
icone(512, 0.22).save(SORTIE / "icone-masquable-512.png", optimize=True)
icone(180, 0.12).save(SORTIE / "apple-touch-icon.png", optimize=True)
