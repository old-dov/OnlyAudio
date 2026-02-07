@echo off
echo --- COMPILATION ONLYAUDIO FINALE ---
echo Nettoyage...
rmdir /s /q build
rmdir /s /q dist
del /q *.spec

echo.
echo Compilation...
:: Note : On compile maintenant "main_final.py"
:: Les imports cachés (PIL, win32timezone) sont toujours nécessaires
pyinstaller --noconsole --onedir --name "OnlyAudio" --icon="icon.ico" --add-data "bg_default.png;." --hidden-import=PIL --hidden-import=PIL._tkinter_finder --hidden-import=win32timezone main_final.py

echo.
echo Copie de secours de l'image de fond...
copy bg_default.png dist\OnlyAudio\

echo.
echo TERMINE !
echo Votre application se trouve dans le dossier dist/OnlyAudio
pause