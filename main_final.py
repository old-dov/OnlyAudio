import os
import threading
import time
import random
import io
import base64
import json
from datetime import datetime
from PIL import Image as PilImage

# --- CONFIGURATION FENÊTRE ---
from kivy.config import Config
Config.set('graphics', 'position', 'custom')
Config.set('graphics', 'left', 100)
Config.set('graphics', 'top', 100)
Config.set('graphics', 'fullscreen', '0')
Config.set('graphics', 'borderless', '0') 
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'width', '1280')
Config.set('graphics', 'height', '850')
Config.set('input', 'mouse', 'mouse,disable_multitouch')

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.image import Image
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.popup import Popup
from kivy.uix.stencilview import StencilView
from kivy.animation import Animation
from kivy.graphics import Color, Rectangle
from kivy.core.image import Image as CoreImage
from kivy.properties import StringProperty, NumericProperty

# Audio
import pygame
from mutagen import File
from mutagen.id3 import ID3, APIC

# Web Server
from flask import Flask, jsonify
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app_flask = Flask(__name__)
player_instance = None

# --- TRADUCTIONS ---
TR = {
    'fr': {
        'playlist': "LISTE",
        'add_file': "+FICHIER",
        'add_folder': "+DOSSIER",
        'save': "SAUVÉ AUTO",
        'artist': "Artiste Inconnu",
        'album': "Album Inconnu",
        'shuffle': "ALEA",
        'repeat': "BOUCLE",
        'load': "Charger",
        'cancel': "Annuler",
        'popup_file': "Ajouter Fichiers",
        'popup_folder': "Ajouter un Dossier"
    },
    'en': {
        'playlist': "PLAYLIST",
        'add_file': "+FILE",
        'add_folder': "+FOLDER",
        'save': "AUTO SAVED",
        'artist': "Unknown Artist",
        'album': "Unknown Album",
        'shuffle': "SHUFFLE",
        'repeat': "REPEAT",
        'load': "Load",
        'cancel': "Cancel",
        'popup_file': "Add Files",
        'popup_folder': "Add Folder"
    }
}

# --- SERVEUR ---
@app_flask.route('/status')
def get_status():
    if player_instance: return jsonify(player_instance.get_info())
    return jsonify({})
@app_flask.route('/play_pause')
def route_play():
    if player_instance: player_instance.play_pause()
    return "OK"
@app_flask.route('/prev')
def route_prev():
    if player_instance: player_instance.play_prev()
    return "OK"
@app_flask.route('/next')
def route_next():
    if player_instance: player_instance.play_next()
    return "OK"
@app_flask.route('/vol_up')
def route_vol_up():
    if player_instance: player_instance.volume_up()
    return "OK"
@app_flask.route('/vol_down')
def route_vol_down():
    if player_instance: player_instance.volume_down()
    return "OK"
@app_flask.route('/shuffle')
def route_shuffle():
    if player_instance: player_instance.toggle_shuffle()
    return "OK"
@app_flask.route('/repeat')
def route_repeat():
    if player_instance: player_instance.toggle_repeat()
    return "OK"

def run_server():
    app_flask.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# --- WIDGETS ---
class ScrollingLabel(StencilView):
    text = StringProperty("")
    scroll_x = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.label = Label(
            text=self.text, font_size='32sp', bold=True, 
            color=(1, 1, 1, 1), size_hint=(None, None),
            halign='left', valign='middle', markup=True
        )
        self.add_widget(self.label)
        self.bind(text=self.update_text)
        self.bind(pos=self.update_layout, size=self.update_layout)
        self.bind(scroll_x=self.update_layout)
        self.anim = None

    def update_layout(self, *args):
        self.label.height = self.height
        self.label.center_y = self.center_y
        base_x = self.x 
        if self.label.width > self.width:
            self.label.x = base_x - self.scroll_x
        else:
            self.label.x = base_x 

    def update_text(self, *args):
        self.label.text = self.text
        self.label.texture_update()
        self.label.width = self.label.texture_size[0] + 50
        if self.anim: self.anim.cancel(self)
        self.scroll_x = 0
        self.trigger_anim()

    def trigger_anim(self, *args):
        Clock.schedule_once(self._start_anim, 0.2)

    def _start_anim(self, dt):
        if self.anim: self.anim.cancel(self)
        self.scroll_x = 0
        self.update_layout()
        if self.label.width > self.width:
            distance = self.label.width - self.width + 50
            duration = distance / 40.0
            self.anim = Animation(scroll_x=distance, duration=duration, t='linear') + \
                        Animation(duration=2.0) + \
                        Animation(scroll_x=0, duration=0) + \
                        Animation(duration=1.0)
            self.anim.repeat = True
            self.anim.start(self)

class TrackButton(Button):
    def __init__(self, index, title, callback, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.text = title
        self.size_hint_y = None
        self.height = 40
        self.font_size = '14sp'
        self.background_normal = ''
        self.background_color = (0.15, 0.15, 0.15, 1)
        self.halign = 'left'
        self.valign = 'middle'
        self.padding_x = 10
        self.bind(size=self.setter('text_size'))
        self.bind(on_press=lambda x: callback(index))

# --- APP ---
class OnlyAudioPlayer(App):
    playlist = []
    current_index = 0
    is_paused = False
    is_shuffled = False
    is_repeat = False
    vol_level = 0.5
    current_cover_data = None
    current_duration = 0
    lang = 'fr'
    saved_time = 0

    def build(self):
        global player_instance
        player_instance = self
        
        Window.fullscreen = False
        Window.borderless = False
        Window.left = 100
        Window.top = 100
        
        pygame.mixer.init()
        
        self.title = "OnlyAudio"
        Window.clearcolor = (0.05, 0.05, 0.05, 1)

        self.root = BoxLayout(orientation='vertical')

        # HEADER
        header = BoxLayout(size_hint_y=None, height=60, padding=[20, 5], spacing=20)
        with header.canvas.before:
            Color(0.08, 0.08, 0.08, 1)
            Rectangle(pos=header.pos, size=header.size)
        lbl_app_name = Label(text="OnlyAudio", font_size='20sp', bold=True, color=(0.3, 0.7, 1, 1), size_hint_x=None, width=150)
        header.add_widget(lbl_app_name)
        header.add_widget(Label())
        right_header = BoxLayout(size_hint_x=None, width=450, spacing=15)
        self.lbl_clock = Label(text="--:--", font_size='18sp', bold=True, color=(0.8, 0.8, 0.8, 1))
        right_header.add_widget(self.lbl_clock)
        self.btn_lang = Button(text="FR", font_size='14sp', bold=True, background_color=(0.2, 0.4, 0.6, 1), size_hint=(None, None), size=(40, 30), pos_hint={'center_y': 0.5})
        self.btn_lang.bind(on_press=self.toggle_language)
        right_header.add_widget(self.btn_lang)
        btn_full = Button(text="[ ]", font_size='14sp', bold=True, background_color=(0.2, 0.2, 0.2, 1), size_hint=(None, None), size=(40, 30), pos_hint={'center_y': 0.5})
        btn_full.bind(on_press=self.toggle_fullscreen)
        right_header.add_widget(btn_full)
        header.add_widget(right_header)
        self.root.add_widget(header)

        # CENTRAL
        self.central_area = FloatLayout()
        self.bg_image = Image(source='bg_default.png', allow_stretch=True, keep_ratio=True, color=(0.8, 0.8, 0.8, 0.4), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.central_area.add_widget(self.bg_image)
        self.root.add_widget(self.central_area)

        # FOOTER
        footer = BoxLayout(orientation='horizontal', size_hint_y=None, height=300, padding=15, spacing=20)
        with footer.canvas.before:
            Color(0.1, 0.1, 0.1, 1)
            Rectangle(pos=footer.pos, size=footer.size)

        # GAUCHE
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.25)
        pl_tools = GridLayout(cols=2, size_hint_y=None, height=70, spacing=5)
        self.btn_add_file = Button(text=TR[self.lang]['add_file'], background_color=(0.3, 0.3, 0.3, 1), font_size='11sp', bold=True)
        self.btn_add_file.bind(on_press=self.open_file_chooser)
        pl_tools.add_widget(self.btn_add_file)
        self.btn_add_folder = Button(text=TR[self.lang]['add_folder'], background_color=(0.3, 0.3, 0.3, 1), font_size='11sp', bold=True)
        self.btn_add_folder.bind(on_press=self.open_folder_chooser)
        pl_tools.add_widget(self.btn_add_folder)
        self.btn_save = Button(text=TR[self.lang]['save'], background_color=(0.2, 0.5, 0.2, 1), font_size='11sp', bold=True, disabled=True)
        pl_tools.add_widget(self.btn_save)
        pl_tools.add_widget(Label())
        left_panel.add_widget(pl_tools)
        self.scroll_view = ScrollView()
        self.playlist_layout = GridLayout(cols=1, spacing=2, size_hint_y=None)
        self.playlist_layout.bind(minimum_height=self.playlist_layout.setter('height'))
        self.scroll_view.add_widget(self.playlist_layout)
        with self.scroll_view.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            Rectangle(pos=self.scroll_view.pos, size=self.scroll_view.size)
        left_panel.add_widget(self.scroll_view)
        footer.add_widget(left_panel)

        # CENTRE
        center_panel = BoxLayout(orientation='vertical', size_hint_x=0.55, spacing=5, padding=[10, 10])
        info_zone = BoxLayout(orientation='horizontal', spacing=20)
        self.footer_cover = Image(source='bg_default.png', size_hint=(None, None), size=(200, 200), allow_stretch=True, keep_ratio=True)
        info_zone.add_widget(self.footer_cover)
        text_zone = BoxLayout(orientation='vertical', spacing=0)
        self.lbl_track = ScrollingLabel(size_hint_y=None, height=65)
        text_zone.add_widget(self.lbl_track)
        self.lbl_artist = Label(text=TR[self.lang]['artist'], font_size='24sp', bold=True, color=(0, 0.8, 1, 1), halign='left', size_hint_y=None, height=40)
        self.lbl_artist.bind(size=self.lbl_artist.setter('text_size'))
        text_zone.add_widget(self.lbl_artist)
        self.lbl_album = Label(text=TR[self.lang]['album'], font_size='18sp', color=(0.7, 0.7, 0.7, 1), halign='left', size_hint_y=None, height=30)
        self.lbl_album.bind(size=self.lbl_album.setter('text_size'))
        text_zone.add_widget(self.lbl_album)
        text_zone.add_widget(Label())
        info_zone.add_widget(text_zone)
        center_panel.add_widget(info_zone)
        time_layout = BoxLayout(size_hint_y=None, height=40)
        self.lbl_cur = Label(text="0:00", font_size='16sp', bold=True, size_hint_x=None, width=70)
        self.progress_bar = Slider(min=0, max=100, value=0, cursor_size=(30,30), value_track_color=(0, 0.7, 0.7, 1), cursor_image='')
        self.lbl_tot = Label(text="0:00", font_size='16sp', bold=True, size_hint_x=None, width=70)
        time_layout.add_widget(self.lbl_cur)
        time_layout.add_widget(self.progress_bar)
        time_layout.add_widget(self.lbl_tot)
        center_panel.add_widget(time_layout)
        footer.add_widget(center_panel)

        # DROITE
        right_panel = GridLayout(cols=1, spacing=15, size_hint_x=0.20, padding=[20, 30])
        nav_box = BoxLayout(spacing=10, size_hint_y=None, height=60)
        btn_prev = Button(text="|<", font_size='26sp', background_color=(0.2, 0.2, 0.2, 1))
        btn_prev.bind(on_press=lambda x: self.play_prev())
        self.btn_play = Button(text="PLAY", font_size='20sp', background_color=(0, 0.7, 0, 1), bold=True)
        self.btn_play.bind(on_press=lambda x: self.play_pause())
        btn_next = Button(text=">|", font_size='26sp', background_color=(0.2, 0.2, 0.2, 1))
        btn_next.bind(on_press=lambda x: self.play_next())
        nav_box.add_widget(btn_prev)
        nav_box.add_widget(self.btn_play)
        nav_box.add_widget(btn_next)
        right_panel.add_widget(nav_box)
        opt_box = BoxLayout(spacing=10, size_hint_y=None, height=40)
        self.btn_shuffle = Button(text=TR[self.lang]['shuffle'], font_size='12sp', background_color=(0.3, 0.3, 0.3, 1))
        self.btn_shuffle.bind(on_press=lambda x: self.toggle_shuffle())
        self.btn_repeat = Button(text=TR[self.lang]['repeat'], font_size='12sp', background_color=(0.3, 0.3, 0.3, 1))
        self.btn_repeat.bind(on_press=lambda x: self.toggle_repeat())
        opt_box.add_widget(self.btn_shuffle)
        opt_box.add_widget(self.btn_repeat)
        right_panel.add_widget(opt_box)
        vol_box = BoxLayout(spacing=5, size_hint_y=None, height=40)
        btn_vm = Button(text="-", font_size='24sp', bold=True)
        btn_vm.bind(on_press=lambda x: self.volume_down())
        self.lbl_v = Label(text="VOL", font_size='12sp')
        btn_vp = Button(text="+", font_size='24sp', bold=True)
        btn_vp.bind(on_press=lambda x: self.volume_up())
        vol_box.add_widget(btn_vm)
        vol_box.add_widget(self.lbl_v)
        vol_box.add_widget(btn_vp)
        right_panel.add_widget(vol_box)
        footer.add_widget(right_panel)
        self.root.add_widget(footer)

        threading.Thread(target=run_server, daemon=True).start()
        Clock.schedule_interval(self.update_progress, 1)
        Clock.schedule_interval(self.update_clock, 1)

        self.load_state_on_start()
        return self.root

    # --- ARRÊT ET SAUVEGARDE SECURISEE ---
    def on_stop(self):
        self.save_state()

    # --- GESTION FICHIERS UTILISATEUR ---
    def get_state_file(self):
        # Retourne le chemin sûr vers AppData/OnlyAudio/state.json
        data_dir = self.user_data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        return os.path.join(data_dir, 'state.json')

    def save_state(self):
        try:
            pos = 0
            if pygame.mixer.music.get_busy() or self.is_paused:
                pos = pygame.mixer.music.get_pos() / 1000 
            
            data = {
                'playlist': self.playlist,
                'index': self.current_index,
                'volume': self.vol_level,
                'position': pos,
                'is_shuffled': self.is_shuffled,
                'is_repeat': self.is_repeat
            }
            with open(self.get_state_file(), 'w') as f:
                json.dump(data, f)
            print(f"État sauvegardé dans {self.get_state_file()}")
        except Exception as e:
            print(f"Erreur save: {e}")

    def load_state_on_start(self):
        state_file = self.get_state_file()
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                
                self.playlist = data.get('playlist', [])
                self.current_index = data.get('index', 0)
                self.vol_level = data.get('volume', 0.5)
                self.saved_time = data.get('position', 0)
                self.is_shuffled = data.get('is_shuffled', False)
                self.is_repeat = data.get('is_repeat', False)
                
                pygame.mixer.music.set_volume(self.vol_level)
                self.btn_shuffle.background_color = (0, 0.7, 0, 1) if self.is_shuffled else (0.3, 0.3, 0.3, 1)
                self.btn_repeat.background_color = (0, 0.7, 0, 1) if self.is_repeat else (0.3, 0.3, 0.3, 1)
                
                self.refresh_playlist_ui()
                
                if self.playlist and 0 <= self.current_index < len(self.playlist):
                    track = self.playlist[self.current_index]
                    try:
                        pygame.mixer.music.load(track)
                        pygame.mixer.music.play(start=self.saved_time)
                        pygame.mixer.music.pause()
                        self.is_paused = True
                        self.btn_play.text = "PLAY" 
                        self.update_metadata(track)
                        
                        self.progress_bar.value = self.saved_time
                        m = int(self.saved_time // 60)
                        s = int(self.saved_time % 60)
                        self.lbl_cur.text = f"{m}:{s:02d}"
                    except Exception as e: pass
            except Exception as e: print(f"Erreur load: {e}")

    @mainthread
    def toggle_language(self, instance):
        self.lang = 'en' if self.lang == 'fr' else 'fr'
        instance.text = self.lang.upper()
        self.btn_add_file.text = TR[self.lang]['add_file']
        self.btn_add_folder.text = TR[self.lang]['add_folder']
        self.btn_save.text = TR[self.lang]['save']
        self.btn_shuffle.text = TR[self.lang]['shuffle']
        self.btn_repeat.text = TR[self.lang]['repeat']
        self.lbl_v.text = TR[self.lang]['vol']
        if not self.playlist or not pygame.mixer.music.get_busy():
            self.lbl_artist.text = TR[self.lang]['artist']
            self.lbl_album.text = TR[self.lang]['album']

    @mainthread
    def toggle_fullscreen(self, instance):
        if Window.fullscreen:
            Window.fullscreen = False
            Window.borderless = False
            instance.text = "[ ]"
        else:
            Window.fullscreen = 'auto'
            instance.text = " X "

    def update_clock(self, dt):
        now = datetime.now()
        self.lbl_clock.text = now.strftime("%H:%M  |  %d/%m/%Y")

    def open_file_chooser(self, instance):
        self._show_chooser(dirselect=False)

    def open_folder_chooser(self, instance):
        self._show_chooser(dirselect=True)

    def _show_chooser(self, dirselect):
        content = BoxLayout(orientation='vertical')
        filters = ['*.mp3', '*.wav', '*.flac'] if not dirselect else []
        start_path = os.path.expanduser("~/Music")
        if not os.path.exists(start_path): start_path = os.path.expanduser("~")
        
        filechooser = FileChooserIconView(path=start_path, filters=filters, dirselect=dirselect)
        content.add_widget(filechooser)
        
        btn_box = BoxLayout(size_hint_y=None, height=40)
        btn_load = Button(text=TR[self.lang]['load'])
        btn_cancel = Button(text=TR[self.lang]['cancel'])
        btn_box.add_widget(btn_load)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        
        title = TR[self.lang]['popup_folder'] if dirselect else TR[self.lang]['popup_file']
        popup = Popup(title=title, content=content, size_hint=(0.9, 0.9))
        
        def load_selection(instance):
            selected = filechooser.selection
            new_tracks = []
            for path in selected:
                if os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            if file.lower().endswith(('.mp3', '.wav', '.flac')):
                                new_tracks.append(os.path.join(root, file))
                else:
                    new_tracks.append(path)
            for t in new_tracks:
                if t not in self.playlist:
                    self.playlist.append(t)
            self.refresh_playlist_ui()
            popup.dismiss()
            if not pygame.mixer.music.get_busy() and not self.is_paused and new_tracks:
                self.play_music()

        btn_load.bind(on_press=load_selection)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

    @mainthread
    def save_playlist(self, instance):
        # Sauvegarde manuelle (déjà couverte par l'auto-save mais rassurant pour l'utilisateur)
        self.save_state()
        orig_text = instance.text
        instance.text = "OK !"
        Clock.schedule_once(lambda dt: setattr(instance, 'text', orig_text), 1)

    @mainthread
    def refresh_playlist_ui(self):
        self.playlist_layout.clear_widgets()
        for i, track_path in enumerate(self.playlist):
            title = os.path.basename(track_path)
            btn = TrackButton(i, title, self.play_track_by_index)
            if i == self.current_index:
                btn.background_color = (0, 0.5, 0.5, 1)
            self.playlist_layout.add_widget(btn)

    def play_track_by_index(self, index):
        self.current_index = index
        self.play_music()

    @mainthread
    def play_music(self):
        if not self.playlist: return
        track = self.playlist[self.current_index]
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play()
            self.is_paused = False
            self.btn_play.text = "PAUSE"
            self.btn_play.background_color = (0.8, 0.4, 0, 1)
            self.update_metadata(track)
            self.refresh_playlist_ui()
        except Exception as e: print(e)

    @mainthread
    def play_pause(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.is_paused = True
            self.btn_play.text = "PLAY"
            self.btn_play.background_color = (0, 0.7, 0, 1)
        elif self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.btn_play.text = "PAUSE"
            self.btn_play.background_color = (0.8, 0.4, 0, 1)
        else:
            self.play_music()

    def play_next(self):
        if not self.playlist: return
        if self.is_shuffled:
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self.play_music()

    def play_prev(self):
        if not self.playlist: return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.play_music()

    def toggle_shuffle(self):
        self.is_shuffled = not self.is_shuffled
        self.btn_shuffle.background_color = (0, 0.7, 0, 1) if self.is_shuffled else (0.3, 0.3, 0.3, 1)

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        self.btn_repeat.background_color = (0, 0.7, 0, 1) if self.is_repeat else (0.3, 0.3, 0.3, 1)

    def volume_up(self):
        self.vol_level = min(1.0, self.vol_level + 0.1)
        pygame.mixer.music.set_volume(self.vol_level)

    def volume_down(self):
        self.vol_level = max(0.0, self.vol_level - 0.1)
        pygame.mixer.music.set_volume(self.vol_level)

    @mainthread
    def update_metadata(self, file_path):
        try:
            audio = File(file_path)
            title = os.path.basename(file_path)
            artist = TR[self.lang]['artist']
            album = TR[self.lang]['album']
            year = ""
            if audio and audio.info:
                self.current_duration = int(audio.info.length)
                self.lbl_tot.text = f"{self.current_duration//60}:{self.current_duration%60:02d}"
                self.progress_bar.max = self.current_duration
            else:
                self.current_duration = 0
                self.lbl_tot.text = "0:00"
            if audio:
                if 'TIT2' in audio: title = str(audio['TIT2'])
                if 'TPE1' in audio: artist = str(audio['TPE1'])
                if 'TALB' in audio: album = str(audio['TALB'])
                if 'TDRC' in audio: year = str(audio['TDRC'])
                has_cover = False
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        img_data = tag.data
                        try:
                            pil_img = PilImage.open(io.BytesIO(img_data))
                            buf = io.BytesIO()
                            pil_img.save(buf, format='png')
                            buf.seek(0)
                            im = CoreImage(buf, ext='png').texture
                            self.bg_image.texture = im
                            self.footer_cover.texture = im
                            self.current_cover_data = base64.b64encode(img_data).decode('utf-8')
                            has_cover = True
                        except Exception as ex: print(f"Erreur image: {ex}")
                        break
                if not has_cover:
                    self.bg_image.source = 'bg_default.png'
                    self.footer_cover.source = 'bg_default.png'
                    self.current_cover_data = ""
            self.lbl_track.text = title
            self.lbl_artist.text = artist
            year_str = f" ({year})" if year else ""
            self.lbl_album.text = f"{album}{year_str}"
        except Exception as e:
            print(f"Erreur meta: {e}")
            self.lbl_track.text = os.path.basename(file_path)

    def update_progress(self, dt):
        if pygame.mixer.music.get_busy():
            pos = (pygame.mixer.music.get_pos() / 1000) + self.saved_time
            current_pos = pos 
            self.progress_bar.value = current_pos
            current_min = int(current_pos // 60)
            current_sec = int(current_pos % 60)
            self.lbl_cur.text = f"{current_min}:{current_sec:02d}"
        elif not self.is_paused and self.playlist and not pygame.mixer.music.get_busy():
            self.saved_time = 0 # Reset si lecture normale
            if self.is_repeat: self.play_music()
            else: self.play_next()

    def get_info(self):
        pos_ms = pygame.mixer.music.get_pos()
        dur_ms = self.current_duration * 1000 
        return {
            'title': self.lbl_track.text,
            'artist': self.lbl_artist.text,
            'album': self.lbl_album.text,
            'pos': pos_ms,
            'dur': dur_ms,
            'cover_b64': self.current_cover_data
        }

if __name__ == '__main__':
    OnlyAudioPlayer().run()