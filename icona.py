#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Disegna scaffale.ico: quattro dorsi di libro su fondo rosso scuro."""
import os

from PIL import Image, ImageDraw

QUI = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(QUI, "scaffale.ico")

FONDO = (122, 46, 46)        # lo stesso rosso dell'app
CREMA = (251, 250, 247)
AVORIO = (232, 226, 210)
SCURO = (60, 22, 22)


def disegna(lato=512):
    u = lato / 512          # tutto in proporzione al lato
    img = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # il riquadro di fondo, con gli angoli smussati
    d.rounded_rectangle([0, 0, lato - 1, lato - 1], radius=int(96 * u), fill=FONDO)

    # il ripiano
    d.rectangle([int(70 * u), int(392 * u), int(442 * u), int(414 * u)], fill=SCURO)

    # tre libri in piedi, uno più basso, e uno appoggiato di sbieco
    libri = [(96, 150, 62), (176, 120, 78), (272, 168, 54)]
    for x, alto, largo in libri:
        x0, x1 = int(x * u), int((x + largo) * u)
        y0, y1 = int((392 - alto) * u), int(392 * u)
        d.rounded_rectangle([x0, y0, x1, y1], radius=int(6 * u), fill=CREMA)
        # due nervature sul dorso
        for q in (0.26, 0.74):
            y = int((392 - alto + alto * q) * u)
            d.rectangle([x0 + int(8 * u), y, x1 - int(8 * u), y + int(7 * u)], fill=FONDO)

    # il volume inclinato, quello che si sta consultando
    inclinato = Image.new("RGBA", (int(150 * u), int(70 * u)), (0, 0, 0, 0))
    di = ImageDraw.Draw(inclinato)
    di.rounded_rectangle([0, 0, int(150 * u) - 1, int(70 * u) - 1],
                         radius=int(6 * u), fill=AVORIO)
    di.rectangle([int(18 * u), 0, int(26 * u), int(70 * u)], fill=FONDO)
    inclinato = inclinato.rotate(-64, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(inclinato, (int(330 * u), int(214 * u)))

    return img


def main():
    misure = [16, 24, 32, 48, 64, 128, 256]
    grande = disegna(512)
    grande.save(ICO, format="ICO",
                sizes=[(m, m) for m in misure])
    grande.resize((256, 256), Image.LANCZOS).save(os.path.join(QUI, "scaffale.png"))
    print(f"Scritto {ICO}")
    return ICO


if __name__ == "__main__":
    main()
