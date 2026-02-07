#!/bin/bash
echo "--- COMPILATION ONLYAUDIO (MAC) ---"

echo "Nettoyage..."
rm -rf build dist *.spec

echo "Compilation..."
# Notez le deux-points ':' au lieu du point-virgule ';' pour --add-data
pyinstaller --noconsole --onedir --name "OnlyAudio" --add-data "bg_default.png:." --hidden-import=PIL --hidden-import=PIL._tkinter_finder main_final.py

echo "Copie de secours de l'image..."
# Sur Mac, l'exécutable est parfois dans un sous-dossier, on assure le coup
cp bg_default.png dist/OnlyAudio/

echo "TERMINE !"
echo "Votre application est dans le dossier dist/OnlyAudio"