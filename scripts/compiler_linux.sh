#!/bin/bash
echo "--- COMPILATION ONLYAUDIO (LINUX) ---"

echo "Nettoyage..."
rm -rf build dist *.spec

echo "Compilation..."
# Note : Pas besoin de win32timezone ici
# Le séparateur pour --add-data est ':' comme sur Mac
pyinstaller --noconsole --onedir --name "OnlyAudio" \
 --add-data "bg_default.png:." \
 --hidden-import=PIL --hidden-import=PIL._tkinter_finder \
 main_final.py

echo "Copie de secours de l'image..."
cp bg_default.png dist/OnlyAudio/

# On s'assure que le binaire est exécutable
chmod +x dist/OnlyAudio/OnlyAudio

echo "TERMINE !"
echo "Pour lancer : ./dist/OnlyAudio/OnlyAudio"