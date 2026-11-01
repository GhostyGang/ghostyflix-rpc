from __future__ import annotations

import io
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import colorchooser, messagebox
from typing import Any

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import APP_NAME, __version__
from .jellyfin import MediaSession
from .service import PlaybackService, format_clock
from .settings import Settings, settings_directory
from .updates import Release, download_release, find_release, is_newer, launch_replacement, open_release_page

try:
    import pystray
except ImportError:  # Tray support is optional on platforms without a system tray.
    pystray = None  # type: ignore[assignment]


COLORS = {
    'background': '#101216',
    'panel': '#181C22',
    'panel_alt': '#20252D',
    'edge': '#2C333D',
    'text': '#F4F5F7',
    'muted': '#9CA5B1',
    'orange': '#F97316',
    'orange_hover': '#EA580C',
    'green': '#4CC38A',
    'red': '#F87171',
}


def resource_path(*parts: str) -> Path:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return root.joinpath(*parts)


def configure_logging() -> None:
    directory = settings_directory()
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / 'ghostyflix_rpc.log', maxBytes=4_000_000, backupCount=2, encoding='utf-8')
    level = getattr(logging, Settings.load().log_level, logging.INFO)
    logging.basicConfig(level=level, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')


class GhostyFlixApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        super().__init__()
        self.settings = Settings.load()
        self.service = PlaybackService(self.settings)
        self._events: queue.Queue[dict[str, Any]] = self.service.events
        self._active_media: MediaSession | None = None
        self._poster_url = ''
        self._loaded_poster_url = ''
        self._poster_image: ctk.CTkImage | None = None
        self._poster_source: Image.Image | None = None
        self._logo_image: ctk.CTkImage | None = None
        self._tray_icon: Any = None
        self._latest_release: Release | None = None
        self._update_busy = False
        self._preview_started = 0.0
        self._preview_position = 0
        self._preview_after_id: str | None = None
        self._library_rows: list[dict[str, str]] = []
        self._selected_library_ids = {value for value in self.settings.filter_libraries.split(',') if value}
        self._setup_window()
        self._build_shell()
        self._load_settings_into_controls()
        self.service.start()
        self.after(120, self._drain_events)
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(300, self._start_minimized_if_requested)
        if self.settings.automatic_updates:
            self.after(2500, self._check_for_updates)

    def _setup_window(self) -> None:
        self.title(f'{APP_NAME} · {__version__}')
        self.geometry('1120x760')
        self.minsize(940, 640)
        self.configure(fg_color=COLORS['background'])
        icon = resource_path('assets', 'icon.ico')
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

    def _build_shell(self) -> None:
        shell = ctk.CTkFrame(self, fg_color='transparent')
        shell.pack(fill='both', expand=True, padx=24, pady=(18, 22))
        header = ctk.CTkFrame(shell, fg_color='transparent')
        header.pack(fill='x', pady=(0, 18))
        logo_path = resource_path('assets', 'icon.png')
        if logo_path.exists():
            try:
                image = Image.open(logo_path).convert('RGBA')
                self._logo_image = ctk.CTkImage(light_image=image, dark_image=image, size=(50, 50))
                ctk.CTkLabel(header, image=self._logo_image, text='').pack(side='left', padx=(0, 13))
            except Exception:
                pass
        title_area = ctk.CTkFrame(header, fg_color='transparent')
        title_area.pack(side='left', fill='y')
        ctk.CTkLabel(title_area, text='GhostyFlix RPC', font=ctk.CTkFont(size=25, weight='bold'), text_color=COLORS['text']).pack(anchor='w')
        ctk.CTkLabel(title_area, text='Jellyfin playback, styled for your Discord profile', font=ctk.CTkFont(size=12), text_color=COLORS['muted']).pack(anchor='w', pady=(1, 0))
        self.connection_pill = ctk.CTkLabel(
            header, text='●  Not connected', corner_radius=999,
            fg_color=COLORS['panel_alt'], text_color=COLORS['muted'],
            font=ctk.CTkFont(size=12, weight='bold'), padx=13, pady=8,
        )
        self.connection_pill.pack(side='right', anchor='center')

        self.tabs = ctk.CTkTabview(
            shell, fg_color=COLORS['panel'], segmented_button_fg_color=COLORS['panel_alt'],
            segmented_button_selected_color=COLORS['orange'],
            segmented_button_selected_hover_color=COLORS['orange_hover'],
            segmented_button_unselected_color=COLORS['panel_alt'],
            segmented_button_unselected_hover_color='#303741',
            text_color=COLORS['text'], corner_radius=16, border_width=1,
            border_color=COLORS['edge'],
        )
        self.tabs.pack(fill='both', expand=True)
        self.tabs.add('Now Playing')
        self.tabs.add('Connect')
        self.tabs.add('Artwork & Activity')
        self.tabs.add('Preferences')
        self._build_preview_tab()
        self._build_connection_tab()
        self._build_artwork_tab()
        self._build_preferences_tab()
        footer = ctk.CTkFrame(shell, fg_color='transparent')
        footer.pack(fill='x', pady=(12, 0))
        self.status_text = ctk.CTkLabel(footer, text='Ready when you are.', text_color=COLORS['muted'], anchor='w')
        self.status_text.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(footer, text=f'v{__version__}', text_color='#75808C', font=ctk.CTkFont(size=11)).pack(side='right')

    def _build_preview_tab(self) -> None:
        tab = self.tabs.tab('Now Playing')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        intro = ctk.CTkFrame(tab, fg_color='transparent')
        intro.grid(row=0, column=0, sticky='ew', padx=16, pady=(16, 8))
        ctk.CTkLabel(intro, text='Your activity preview', font=ctk.CTkFont(size=20, weight='bold'), text_color=COLORS['text']).pack(anchor='w')
        ctk.CTkLabel(intro, text='A live look at the playback details GhostyFlix is preparing for Discord.', text_color=COLORS['muted']).pack(anchor='w', pady=(4, 0))
        card = ctk.CTkFrame(tab, fg_color='#121519', border_width=1, border_color=COLORS['edge'], corner_radius=18)
        card.grid(row=1, column=0, sticky='nsew', padx=16, pady=12)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=1)
        self.preview_heading = ctk.CTkLabel(card, text='WATCHING YOUR JELLYFIN SERVER', text_color=COLORS['muted'], font=ctk.CTkFont(size=11, weight='bold'), anchor='w')
        self.preview_heading.grid(row=0, column=0, columnspan=2, sticky='ew', padx=18, pady=(17, 14))
        self.poster_label = ctk.CTkLabel(card, text='GHOSTYFLIX', width=148, height=196, corner_radius=12, fg_color=COLORS['panel_alt'], text_color=COLORS['orange'], font=ctk.CTkFont(size=12, weight='bold'))
        self.poster_label.grid(row=1, column=0, rowspan=5, sticky='nw', padx=(18, 20), pady=(0, 18))
        self.preview_title = ctk.CTkLabel(card, text='Start playback to see your activity', text_color=COLORS['text'], font=ctk.CTkFont(size=23, weight='bold'), anchor='w', justify='left', wraplength=630)
        self.preview_title.grid(row=1, column=1, sticky='ew', padx=(0, 20), pady=(6, 2))
        self.preview_subtitle = ctk.CTkLabel(card, text='Movies, episodes, and music will appear here.', text_color=COLORS['muted'], font=ctk.CTkFont(size=14), anchor='w', wraplength=650, justify='left')
        self.preview_subtitle.grid(row=2, column=1, sticky='ew', padx=(0, 20), pady=(0, 15))
        times = ctk.CTkFrame(card, fg_color='transparent')
        times.grid(row=3, column=1, sticky='ew', padx=(0, 20), pady=(4, 0))
        times.grid_columnconfigure(0, weight=1)
        self.elapsed_label = ctk.CTkLabel(times, text='0:00', text_color=COLORS['text'], font=ctk.CTkFont(size=12, weight='bold'))
        self.elapsed_label.grid(row=0, column=0, sticky='w')
        self.duration_label = ctk.CTkLabel(times, text='0:00', text_color=COLORS['text'], font=ctk.CTkFont(size=12, weight='bold'))
        self.duration_label.grid(row=0, column=1, sticky='e')
        self.preview_progress = ctk.CTkProgressBar(times, height=10, corner_radius=999, fg_color='#333A43', progress_color=COLORS['orange'])
        self.preview_progress.set(0)
        self.preview_progress.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.preview_state = ctk.CTkLabel(card, text='Waiting for Jellyfin playback', text_color=COLORS['orange'], font=ctk.CTkFont(size=13, weight='bold'), anchor='w')
        self.preview_state.grid(row=4, column=1, sticky='ew', padx=(0, 20), pady=(14, 4))
        hint = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=12)
        hint.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 16))
        ctk.CTkLabel(hint, text='Discord uses its own activity card design. This preview reflects the title, status, poster, and timing GhostyFlix sends.', text_color=COLORS['muted'], wraplength=800, justify='left').pack(fill='x', padx=16, pady=12)

    def _build_connection_tab(self) -> None:
        tab = self.tabs.tab('Connect')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        title = self._section_title(tab, 'Connect Jellyfin', 'Sign in once. GhostyFlix will watch the connected Jellyfin account for playback.')
        title.grid(row=0, column=0, columnspan=2, sticky='ew', padx=18, pady=(18, 14))
        self.server_entry = self._labeled_entry(tab, 1, 0, 'Server address', 'https://jellyfin.example.com', columnspan=2)
        mode = ctk.CTkFrame(tab, fg_color='transparent')
        mode.grid(row=2, column=0, columnspan=2, sticky='ew', padx=18, pady=(10, 6))
        ctk.CTkLabel(mode, text='Sign-in method', text_color=COLORS['muted'], font=ctk.CTkFont(size=12, weight='bold')).pack(anchor='w', pady=(0, 7))
        self.auth_mode = tk.StringVar(value='Quick Connect')
        self.auth_picker = ctk.CTkSegmentedButton(mode, values=['Quick Connect', 'API key'], variable=self.auth_mode, command=self._change_auth_mode, selected_color=COLORS['orange'], selected_hover_color=COLORS['orange_hover'], unselected_color=COLORS['panel_alt'])
        self.auth_picker.pack(anchor='w')

        self.quick_panel = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        self.quick_panel.grid(row=3, column=0, sticky='nsew', padx=(18, 8), pady=(8, 12))
        ctk.CTkLabel(self.quick_panel, text='QUICK CONNECT', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).pack(anchor='w', padx=16, pady=(15, 4))
        ctk.CTkLabel(self.quick_panel, text='Generate a short code, then approve it from a signed-in Jellyfin device.', text_color=COLORS['muted'], wraplength=390, justify='left').pack(anchor='w', padx=16, pady=(0, 12))
        self.quick_code_label = ctk.CTkLabel(self.quick_panel, text='— — — — — —', text_color=COLORS['text'], font=ctk.CTkFont(size=26, weight='bold'), letter_spacing=4)
        self.quick_code_label.pack(anchor='w', padx=16, pady=(0, 12))
        quick_actions = ctk.CTkFrame(self.quick_panel, fg_color='transparent')
        quick_actions.pack(fill='x', padx=12, pady=(0, 13))
        ctk.CTkButton(quick_actions, text='Get a code', command=self._start_quick_connect, height=38, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(side='left', padx=4)
        ctk.CTkButton(quick_actions, text='Copy code', command=self._copy_quick_code, height=38, fg_color='#343B45', hover_color='#414B58').pack(side='left', padx=4)
        self.quick_instruction = ctk.CTkLabel(self.quick_panel, text='Jellyfin → user menu → Quick Connect → enter code → approve', text_color=COLORS['muted'], wraplength=390, justify='left', font=ctk.CTkFont(size=11))
        self.quick_instruction.pack(anchor='w', padx=16, pady=(0, 14))

        self.api_panel = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        self.api_panel.grid(row=3, column=1, sticky='nsew', padx=(8, 18), pady=(8, 12))
        ctk.CTkLabel(self.api_panel, text='API KEY SIGN-IN', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).pack(anchor='w', padx=16, pady=(15, 4))
        ctk.CTkLabel(self.api_panel, text='Use a Jellyfin API key if Quick Connect is unavailable on your server.', text_color=COLORS['muted'], wraplength=390, justify='left').pack(anchor='w', padx=16, pady=(0, 11))
        self.username_entry = self._entry(self.api_panel, 'Jellyfin username')
        self.username_entry.pack(fill='x', padx=16, pady=5)
        self.api_key_entry = self._entry(self.api_panel, 'API key', show='•')
        self.api_key_entry.pack(fill='x', padx=16, pady=5)
        ctk.CTkLabel(self.api_panel, text='Create a key in Jellyfin Dashboard → API Keys. Store it only on a trusted PC.', text_color=COLORS['muted'], wraplength=390, justify='left', font=ctk.CTkFont(size=11)).pack(anchor='w', padx=16, pady=(6, 15))

        self.connect_button = ctk.CTkButton(tab, text='Connect to Jellyfin', command=self._connect_selected, height=42, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover'], font=ctk.CTkFont(size=14, weight='bold'))
        self.connect_button.grid(row=4, column=0, sticky='ew', padx=(18, 8), pady=(0, 12))
        self.disconnect_button = ctk.CTkButton(tab, text='Disconnect', command=self._disconnect, height=42, fg_color='#303741', hover_color='#414B58')
        self.disconnect_button.grid(row=4, column=1, sticky='ew', padx=(8, 18), pady=(0, 12))
        library_row = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        library_row.grid(row=5, column=0, columnspan=2, sticky='ew', padx=18, pady=(0, 16))
        library_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(library_row, text='Library filters', text_color=COLORS['text'], font=ctk.CTkFont(size=13, weight='bold')).grid(row=0, column=0, sticky='w', padx=16, pady=(12, 2))
        self.library_summary = ctk.CTkLabel(library_row, text='All libraries included', text_color=COLORS['muted'], anchor='w')
        self.library_summary.grid(row=1, column=0, sticky='ew', padx=16, pady=(2, 12))
        ctk.CTkButton(library_row, text='Choose libraries', command=self._load_libraries, width=150, height=36, fg_color='#343B45', hover_color='#414B58').grid(row=0, column=1, rowspan=2, padx=14, pady=12)
        self._change_auth_mode(self.auth_mode.get())

    def _build_artwork_tab(self) -> None:
        tab = ctk.CTkScrollableFrame(self.tabs.tab('Artwork & Activity'), fg_color='transparent', corner_radius=0)
        tab.pack(fill='both', expand=True)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        top = self._section_title(tab, 'Artwork & activity', 'Choose the artwork, playback details, and badge that GhostyFlix sends to Discord.')
        top.grid(row=0, column=0, columnspan=2, sticky='ew', padx=18, pady=(18, 12))
        artwork_card = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        artwork_card.grid(row=1, column=0, sticky='nsew', padx=(18, 8), pady=8)
        activity_card = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        activity_card.grid(row=1, column=1, sticky='nsew', padx=(8, 18), pady=8)
        ctk.CTkLabel(artwork_card, text='POSTERS & ALBUM ART', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).pack(anchor='w', padx=16, pady=(15, 8))
        ctk.CTkLabel(artwork_card, text='Movie & show poster source', text_color=COLORS['muted']).pack(anchor='w', padx=16)
        self.provider_var = tk.StringVar(value=self.settings.poster_provider)
        self.provider_menu = ctk.CTkOptionMenu(artwork_card, values=['Jellyfin', 'TMDB', 'OMDb'], variable=self.provider_var, width=220, fg_color='#343B45', button_color=COLORS['orange'], button_hover_color=COLORS['orange_hover'])
        self.provider_menu.pack(anchor='w', padx=16, pady=(6, 8))
        self.tmdb_key_entry = self._entry(artwork_card, 'TMDB API key (optional)', show='•')
        self.tmdb_key_entry.pack(fill='x', padx=16, pady=5)
        ctk.CTkButton(artwork_card, text='Get a TMDB key ↗', command=lambda: webbrowser.open('https://www.themoviedb.org/settings/api'), fg_color='transparent', hover_color='#343B45', anchor='w', height=27).pack(fill='x', padx=11)
        self.omdb_key_entry = self._entry(artwork_card, 'OMDb API key or full API URL', show='•')
        self.omdb_key_entry.pack(fill='x', padx=16, pady=(7, 3))
        ctk.CTkButton(artwork_card, text='Get an OMDb key ↗', command=lambda: webbrowser.open('https://www.omdbapi.com/apikey.aspx'), fg_color='transparent', hover_color='#343B45', anchor='w', height=27).pack(fill='x', padx=11)
        self.musicbrainz_var = tk.BooleanVar(value=self.settings.musicbrainz_artwork)
        ctk.CTkCheckBox(artwork_card, text='Prefer MusicBrainz album artwork', variable=self.musicbrainz_var, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=16, pady=(12, 4))
        self.release_over_group_var = tk.BooleanVar(value=self.settings.release_over_group)
        ctk.CTkCheckBox(artwork_card, text='Prefer a specific album release cover', variable=self.release_over_group_var, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=16, pady=4)
        self.season_over_series_var = tk.BooleanVar(value=self.settings.season_over_series)
        ctk.CTkCheckBox(artwork_card, text='Use season artwork for TV episodes', variable=self.season_over_series_var, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=16, pady=4)
        self.textless_posters_var = tk.BooleanVar(value=self.settings.textless_posters)
        ctk.CTkCheckBox(artwork_card, text='Prefer textless posters', variable=self.textless_posters_var, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=16, pady=4)
        self.poster_languages_entry = self._entry(artwork_card, 'Poster languages, e.g. en, fr')
        self.poster_languages_entry.pack(fill='x', padx=16, pady=(5, 4))
        ctk.CTkLabel(artwork_card, text='MusicBrainz and the Cover Art Archive need no API key. Language choices guide TMDB poster selection.', text_color=COLORS['muted'], wraplength=420, justify='left', font=ctk.CTkFont(size=11)).pack(anchor='w', padx=16, pady=(0, 15))
        tmdb_mark = resource_path('assets', 'tmdb-approved-logo.png')
        if tmdb_mark.exists():
            try:
                image = Image.open(tmdb_mark).convert('RGBA')
                image.thumbnail((92, 42), Image.Resampling.LANCZOS)
                self._tmdb_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                ctk.CTkLabel(artwork_card, text='', image=self._tmdb_image).pack(anchor='w', padx=16, pady=(0, 2))
            except Exception:
                pass
        ctk.CTkLabel(artwork_card, text='This product uses the TMDB API but is not endorsed or certified by TMDB.', text_color=COLORS['muted'], wraplength=420, justify='left', font=ctk.CTkFont(size=10)).pack(anchor='w', padx=16, pady=(0, 12))

        ctk.CTkLabel(activity_card, text='ACTIVITY DETAILS', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).pack(anchor='w', padx=16, pady=(15, 9))
        self.genre_var = tk.StringVar(value=str(self.settings.genre_limit))
        self._option_setting(activity_card, 'Movie genres shown', self.genre_var, ['0', '1', '2', '3'])
        self.media_movies_var = tk.BooleanVar(value=self.settings.media_movies)
        self.media_shows_var = tk.BooleanVar(value=self.settings.media_shows)
        self.media_music_var = tk.BooleanVar(value=self.settings.media_music)
        self.show_paused_var = tk.BooleanVar(value=self.settings.show_when_paused)
        self.progress_text_var = tk.BooleanVar(value=self.settings.show_progress_text)
        self.server_name_var = tk.BooleanVar(value=self.settings.show_server_name)
        self.badge_var = tk.BooleanVar(value=self.settings.show_playback_badge)
        self.show_jellyfin_logo_var = tk.BooleanVar(value=self.settings.show_jellyfin_logo)
        for label, variable in (
            ('Movies', self.media_movies_var), ('TV shows and episodes', self.media_shows_var),
            ('Music', self.media_music_var), ('Keep activity visible while paused', self.show_paused_var),
            ('Show watched percentage and time remaining', self.progress_text_var),
            ('Show Jellyfin server name', self.server_name_var),
            ('Show a play / pause badge on the poster', self.badge_var),
            ('Show GhostyFlix logo when the play / pause badge is off', self.show_jellyfin_logo_var),
        ):
            ctk.CTkCheckBox(activity_card, text=label, variable=variable, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=16, pady=5)
        color_row = ctk.CTkFrame(activity_card, fg_color='transparent')
        color_row.pack(fill='x', padx=12, pady=(5, 14))
        ctk.CTkLabel(color_row, text='Badge color', text_color=COLORS['muted']).pack(side='left', padx=4)
        self.badge_color_entry = ctk.CTkEntry(color_row, width=105, placeholder_text='#F97316')
        self.badge_color_entry.pack(side='left', padx=8)
        self.color_swatch = ctk.CTkButton(color_row, text='', width=34, height=30, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover'], command=self._choose_badge_color)
        self.color_swatch.pack(side='left')
        ctk.CTkButton(tab, text='Save activity settings', command=self._save_artwork_settings, height=40, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).grid(row=2, column=0, columnspan=2, sticky='ew', padx=18, pady=(10, 16))

    def _build_preferences_tab(self) -> None:
        tab = ctk.CTkScrollableFrame(self.tabs.tab('Preferences'), fg_color='transparent', corner_radius=0)
        tab.pack(fill='both', expand=True)
        tab.grid_columnconfigure((0, 1), weight=1)
        top = self._section_title(tab, 'Preferences', 'Tune how GhostyFlix runs, checks for playback changes, and receives releases.')
        top.grid(row=0, column=0, columnspan=2, sticky='ew', padx=18, pady=(18, 12))
        playback = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        playback.grid(row=1, column=0, sticky='nsew', padx=(18, 8), pady=8)
        startup = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        startup.grid(row=1, column=1, sticky='nsew', padx=(8, 18), pady=8)
        ctk.CTkLabel(playback, text='PLAYBACK CHECKS', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).pack(anchor='w', padx=16, pady=(15, 6))
        self.poll_var = tk.StringVar(value=str(self.settings.polling_rate))
        self.seek_var = tk.StringVar(value=str(self.settings.seek_threshold))
        self._stepper(playback, 'Playback check interval (seconds)', self.poll_var)
        self._stepper(playback, 'Seek refresh sensitivity (seconds)', self.seek_var)
        ctk.CTkLabel(playback, text='Both values start at 3 seconds. Lower values can feel faster and create more server requests.', text_color=COLORS['muted'], wraplength=420, justify='left', font=ctk.CTkFont(size=11)).pack(anchor='w', padx=16, pady=(10, 16))
        ctk.CTkLabel(startup, text='WINDOW BEHAVIOR', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).pack(anchor='w', padx=16, pady=(15, 7))
        self.start_minimized_var = tk.BooleanVar(value=self.settings.start_minimized)
        self.close_to_tray_var = tk.BooleanVar(value=self.settings.close_to_tray)
        self.open_on_startup_var = tk.BooleanVar(value=self.settings.open_on_startup)
        for label, variable in (
            ('Start minimized', self.start_minimized_var),
            ('Keep running when the window closes', self.close_to_tray_var),
            ('Open GhostyFlix when Windows starts', self.open_on_startup_var),
        ):
            ctk.CTkCheckBox(startup, text=label, variable=variable, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=16, pady=7)
        ctk.CTkLabel(startup, text='Closing to tray requires tray support in your desktop environment.', text_color=COLORS['muted'], wraplength=400, justify='left', font=ctk.CTkFont(size=11)).pack(anchor='w', padx=16, pady=(3, 15))

        updater = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        updater.grid(row=2, column=0, columnspan=2, sticky='ew', padx=18, pady=(8, 10))
        updater.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(updater, text='ONLINE UPDATES', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).grid(row=0, column=0, sticky='w', padx=16, pady=(14, 4))
        ctk.CTkLabel(updater, text='Check public GitHub Releases and install a verified Windows build from inside the app.', text_color=COLORS['muted'], anchor='w', wraplength=650, justify='left').grid(row=1, column=0, sticky='ew', padx=16, pady=(0, 10))
        self.repository_entry = self._entry(updater, 'GitHub repository as owner/name')
        self.repository_entry.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 13))
        self.auto_update_var = tk.BooleanVar(value=self.settings.automatic_updates)
        ctk.CTkCheckBox(updater, text='Check for updates when GhostyFlix starts', variable=self.auto_update_var, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).grid(row=0, column=1, rowspan=2, sticky='ne', padx=16, pady=15)
        self.update_button = ctk.CTkButton(updater, text='Check now', command=self._check_for_updates, width=130, height=36, fg_color='#343B45', hover_color='#414B58')
        self.update_button.grid(row=2, column=1, sticky='e', padx=(8, 16), pady=(0, 13))
        self.install_button = ctk.CTkButton(updater, text='Install & restart', command=self._install_update, width=150, height=36, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover'], state='disabled')
        self.install_button.grid(row=2, column=2, sticky='e', padx=(0, 16), pady=(0, 13))
        self.update_progress = ctk.CTkProgressBar(updater, height=7, progress_color=COLORS['orange'], fg_color='#333A43')
        self.update_progress.grid(row=3, column=0, columnspan=3, sticky='ew', padx=16, pady=(0, 14))
        self.update_progress.set(0)
        diagnostics = ctk.CTkFrame(tab, fg_color=COLORS['panel_alt'], corner_radius=14)
        diagnostics.grid(row=3, column=0, columnspan=2, sticky='ew', padx=18, pady=(8, 10))
        diagnostics.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(diagnostics, text='DIAGNOSTICS', text_color=COLORS['orange'], font=ctk.CTkFont(size=11, weight='bold')).grid(row=0, column=0, sticky='w', padx=16, pady=(14, 4))
        ctk.CTkLabel(diagnostics, text='Choose how much detail to write to the local activity log.', text_color=COLORS['muted'], anchor='w').grid(row=1, column=0, sticky='w', padx=16, pady=(0, 13))
        self.log_level_var = tk.StringVar(value=self.settings.log_level)
        ctk.CTkOptionMenu(diagnostics, values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], variable=self.log_level_var, width=145, fg_color='#343B45', button_color=COLORS['orange'], button_hover_color=COLORS['orange_hover']).grid(row=0, column=1, sticky='e', padx=16, pady=(12, 4))
        actions = ctk.CTkFrame(diagnostics, fg_color='transparent')
        actions.grid(row=0, column=2, rowspan=2, sticky='e', padx=(8, 16), pady=12)
        ctk.CTkButton(actions, text='Open settings folder', command=self._open_settings_folder, height=34, fg_color='#343B45', hover_color='#414B58').pack(side='left', padx=(0, 7))
        ctk.CTkButton(actions, text='Open activity log', command=self._open_activity_log, height=34, fg_color='#343B45', hover_color='#414B58').pack(side='left')
        ctk.CTkButton(tab, text='Save preferences', command=self._save_preferences, height=40, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).grid(row=4, column=0, columnspan=2, sticky='ew', padx=18, pady=(8, 16))

    def _section_title(self, parent: Any, title: str, description: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=20, weight='bold'), text_color=COLORS['text']).pack(anchor='w')
        ctk.CTkLabel(frame, text=description, text_color=COLORS['muted'], wraplength=830, justify='left').pack(anchor='w', pady=(4, 0))
        return frame

    def _entry(self, parent: Any, placeholder: str, show: str | None = None) -> ctk.CTkEntry:
        return ctk.CTkEntry(parent, height=38, placeholder_text=placeholder, show=show, border_color=COLORS['edge'], fg_color='#15191E', text_color=COLORS['text'], placeholder_text_color='#74808C')

    def _labeled_entry(self, parent: Any, row: int, column: int, label: str, placeholder: str, columnspan: int = 1) -> ctk.CTkEntry:
        box = ctk.CTkFrame(parent, fg_color='transparent')
        box.grid(row=row, column=column, columnspan=columnspan, sticky='ew', padx=18, pady=(0, 8))
        ctk.CTkLabel(box, text=label, text_color=COLORS['muted'], font=ctk.CTkFont(size=12, weight='bold')).pack(anchor='w', pady=(0, 6))
        entry = self._entry(box, placeholder)
        entry.pack(fill='x')
        return entry

    def _option_setting(self, parent: Any, label: str, variable: tk.StringVar, values: list[str]) -> None:
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=12, pady=(0, 8))
        ctk.CTkLabel(row, text=label, text_color=COLORS['muted']).pack(side='left', padx=4)
        ctk.CTkOptionMenu(row, values=values, variable=variable, width=86, fg_color='#343B45', button_color=COLORS['orange'], button_hover_color=COLORS['orange_hover']).pack(side='right', padx=4)

    def _stepper(self, parent: Any, label: str, variable: tk.StringVar) -> None:
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=16, pady=(5, 7))
        ctk.CTkLabel(row, text=label, text_color=COLORS['text'], anchor='w').pack(side='left', fill='x', expand=True)
        ctk.CTkButton(row, text='−', command=lambda: self._step_value(variable, -1), width=34, height=32, fg_color='#343B45', hover_color='#414B58').pack(side='left', padx=(5, 2))
        ctk.CTkLabel(row, textvariable=variable, width=34, text_color=COLORS['text'], font=ctk.CTkFont(size=14, weight='bold')).pack(side='left')
        ctk.CTkButton(row, text='+', command=lambda: self._step_value(variable, 1), width=34, height=32, fg_color='#343B45', hover_color='#414B58').pack(side='left', padx=(2, 0))

    @staticmethod
    def _step_value(variable: tk.StringVar, amount: int) -> None:
        try:
            current = int(variable.get())
        except ValueError:
            current = 3
        variable.set(str(min(30, max(1, current + amount))))

    def _load_settings_into_controls(self) -> None:
        for entry, value in (
            (self.server_entry, self.settings.jellyfin_host),
            (self.username_entry, self.settings.jellyfin_username),
            (self.api_key_entry, self.settings.jellyfin_api_key),
            (self.tmdb_key_entry, self.settings.tmdb_api_key),
            (self.omdb_key_entry, self.settings.omdb_api_key),
            (self.poster_languages_entry, self.settings.poster_languages),
            (self.badge_color_entry, self.settings.badge_color),
            (self.repository_entry, self.settings.update_repository),
        ):
            if value:
                entry.insert(0, value)
        self.color_swatch.configure(fg_color=self.settings.badge_color)
        self._set_library_summary()

    def _change_auth_mode(self, value: str) -> None:
        if value == 'Quick Connect':
            self.quick_panel.grid()
            self.api_panel.grid_remove()
        else:
            self.api_panel.grid()
            self.quick_panel.grid_remove()

    def _connect_selected(self) -> None:
        if self.auth_mode.get() == 'Quick Connect':
            self._start_quick_connect()
            return
        server = self._validated_server()
        if not server:
            return
        username = self.username_entry.get().strip()
        key = self.api_key_entry.get().strip()
        if not username or not key:
            messagebox.showinfo('Sign-in details needed', 'Enter your Jellyfin username and API key to continue.', parent=self)
            return
        self.settings.jellyfin_host = server
        self.settings.jellyfin_username = username
        self.settings.jellyfin_api_key = key
        self.settings.save()
        self.service.update_settings(self.settings)
        self.service.connect_api_key(server, username, key)
        self.status_text.configure(text='Checking your Jellyfin sign-in…')

    def _start_quick_connect(self) -> None:
        server = self._validated_server()
        if not server:
            return
        self.settings.jellyfin_host = server
        self.settings.save()
        self.service.update_settings(self.settings)
        self.quick_code_label.configure(text='Getting code…')
        self.service.connect_quick(server)
        self.status_text.configure(text='Contacting Jellyfin…')

    def _validated_server(self) -> str:
        value = self.server_entry.get().strip().rstrip('/')
        if not value.startswith(('http://', 'https://')):
            messagebox.showinfo('Server address needed', 'Enter the full Jellyfin address, including http:// or https://.', parent=self)
            return ''
        return value

    def _copy_quick_code(self) -> None:
        code = self.quick_code_label.cget('text')
        if not code or code in {'— — — — — —', 'Getting code…'}:
            return
        self.clipboard_clear()
        self.clipboard_append(code)
        self.status_text.configure(text='Quick Connect code copied.')

    def _disconnect(self) -> None:
        self.service.disconnect()

    def _save_artwork_settings(self) -> None:
        self.settings.poster_provider = self.provider_var.get()
        self.settings.tmdb_api_key = self.tmdb_key_entry.get().strip()
        self.settings.omdb_api_key = self.omdb_key_entry.get().strip()
        self.settings.musicbrainz_artwork = bool(self.musicbrainz_var.get())
        self.settings.release_over_group = bool(self.release_over_group_var.get())
        self.settings.season_over_series = bool(self.season_over_series_var.get())
        self.settings.textless_posters = bool(self.textless_posters_var.get())
        self.settings.poster_languages = self.poster_languages_entry.get().strip()
        self.settings.genre_limit = min(3, max(0, int(self.genre_var.get())))
        self.settings.media_movies = bool(self.media_movies_var.get())
        self.settings.media_shows = bool(self.media_shows_var.get())
        self.settings.media_music = bool(self.media_music_var.get())
        self.settings.show_when_paused = bool(self.show_paused_var.get())
        self.settings.show_progress_text = bool(self.progress_text_var.get())
        self.settings.show_server_name = bool(self.server_name_var.get())
        self.settings.show_playback_badge = bool(self.badge_var.get())
        self.settings.show_jellyfin_logo = bool(self.show_jellyfin_logo_var.get())
        self.settings.badge_color = self._validated_color()
        self.settings.save()
        self.service.update_settings(self.settings)
        if self._poster_source is not None:
            self._set_preview_image(self._poster_source)
        self.status_text.configure(text='Activity settings saved.')

    def _validated_color(self) -> str:
        value = self.badge_color_entry.get().strip()
        if len(value) == 7 and value.startswith('#') and all(char in '0123456789abcdefABCDEF' for char in value[1:]):
            return value.upper()
        return '#F97316'

    def _choose_badge_color(self) -> None:
        picked = colorchooser.askcolor(color=self._validated_color(), parent=self)
        if picked and picked[1]:
            self.badge_color_entry.delete(0, 'end')
            self.badge_color_entry.insert(0, picked[1].upper())
            self.color_swatch.configure(fg_color=picked[1])

    def _save_preferences(self) -> None:
        try:
            polling = min(30, max(1, int(self.poll_var.get())))
            seek = min(30, max(1, int(self.seek_var.get())))
        except ValueError:
            messagebox.showinfo('Check the timing values', 'Playback and seek intervals must be a number from 1 to 30.', parent=self)
            return
        self.settings.polling_rate = polling
        self.settings.seek_threshold = seek
        self.settings.start_minimized = bool(self.start_minimized_var.get())
        self.settings.close_to_tray = bool(self.close_to_tray_var.get())
        self.settings.open_on_startup = bool(self.open_on_startup_var.get())
        self.settings.automatic_updates = bool(self.auto_update_var.get())
        self.settings.log_level = self.log_level_var.get().upper()
        repository = self.repository_entry.get().strip()
        if repository:
            self.settings.update_repository = repository
        self.settings.save()
        self.service.update_settings(self.settings)
        logging.getLogger().setLevel(getattr(logging, self.settings.log_level, logging.INFO))
        self._set_startup_registration(self.settings.open_on_startup)
        self.status_text.configure(text='Preferences saved.')

    def _open_settings_folder(self) -> None:
        self._open_local_path(settings_directory())

    def _open_activity_log(self) -> None:
        self._open_local_path(settings_directory() / 'ghostyflix_rpc.log')

    @staticmethod
    def _open_local_path(path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix:
                path.touch(exist_ok=True)
            if hasattr(os, 'startfile'):
                os.startfile(str(path))
            else:
                webbrowser.open(path.as_uri())
        except OSError as exc:
            messagebox.showerror('Could not open file', str(exc))

    def _set_startup_registration(self, enabled: bool) -> None:
        if os.name != 'nt':
            return
        try:
            import winreg
            key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as registry:
                if enabled:
                    command = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" -m ghostyflix_rpc'
                    winreg.SetValueEx(registry, 'GhostyFlixRPC', 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(registry, 'GhostyFlixRPC')
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            logging.warning('Could not update the Windows startup entry: %s', type(exc).__name__)
            messagebox.showinfo('Startup setting not applied', 'Windows did not allow the startup entry to be changed.', parent=self)

    def _load_libraries(self) -> None:
        self.status_text.configure(text='Loading Jellyfin libraries…')
        self.service.list_libraries()

    def _show_libraries(self, items: list[dict[str, str]]) -> None:
        self._library_rows = items
        window = ctk.CTkToplevel(self)
        window.title('Choose libraries')
        window.geometry('440x500')
        window.transient(self)
        window.grab_set()
        ctk.CTkLabel(window, text='Choose where playback can appear', font=ctk.CTkFont(size=19, weight='bold'), text_color=COLORS['text']).pack(anchor='w', padx=20, pady=(20, 5))
        ctk.CTkLabel(window, text='Blacklist hides checked libraries. Whitelist shows only checked libraries.', text_color=COLORS['muted'], wraplength=390, justify='left').pack(anchor='w', padx=20, pady=(0, 13))
        self.filter_mode_var = tk.StringVar(value='Blacklist' if self.settings.filter_mode == 'blacklist' else 'Whitelist')
        ctk.CTkSegmentedButton(window, values=['Blacklist', 'Whitelist'], variable=self.filter_mode_var, selected_color=COLORS['orange'], selected_hover_color=COLORS['orange_hover']).pack(anchor='w', padx=20, pady=(0, 12))
        listing = ctk.CTkScrollableFrame(window, fg_color=COLORS['panel_alt'], corner_radius=12)
        listing.pack(fill='both', expand=True, padx=20, pady=4)
        self._library_vars: dict[str, tk.BooleanVar] = {}
        if not items:
            ctk.CTkLabel(listing, text='No libraries were returned by Jellyfin.', text_color=COLORS['muted']).pack(anchor='w', padx=12, pady=12)
        for item in items:
            identifier = item['id']
            variable = tk.BooleanVar(value=identifier in self._selected_library_ids)
            self._library_vars[identifier] = variable
            ctk.CTkCheckBox(listing, text=item['name'], variable=variable, checkbox_width=18, checkbox_height=18, fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(anchor='w', padx=12, pady=7)
        actions = ctk.CTkFrame(window, fg_color='transparent')
        actions.pack(fill='x', padx=20, pady=16)
        ctk.CTkButton(actions, text='Cancel', command=window.destroy, fg_color='#343B45', hover_color='#414B58').pack(side='right', padx=(8, 0))
        ctk.CTkButton(actions, text='Save filters', command=lambda: self._save_library_filter(window), fg_color=COLORS['orange'], hover_color=COLORS['orange_hover']).pack(side='right')

    def _save_library_filter(self, window: ctk.CTkToplevel) -> None:
        self._selected_library_ids = {identifier for identifier, variable in self._library_vars.items() if variable.get()}
        self.settings.filter_libraries = ','.join(sorted(self._selected_library_ids))
        self.settings.filter_mode = 'blacklist' if self.filter_mode_var.get() == 'Blacklist' else 'whitelist'
        self.settings.save()
        self.service.update_settings(self.settings)
        self._set_library_summary()
        window.destroy()

    def _set_library_summary(self) -> None:
        ids = {value for value in self.settings.filter_libraries.split(',') if value}
        if not ids:
            self.library_summary.configure(text='All libraries included')
            return
        names = [row['name'] for row in self._library_rows if row['id'] in ids]
        mode = 'Hide' if self.settings.filter_mode == 'blacklist' else 'Only show'
        self.library_summary.configure(text=f'{mode}: {", ".join(names) if names else f"{len(ids)} selected library/libraries"}')

    def _drain_events(self) -> None:
        if not self.winfo_exists():
            return
        try:
            while True:
                event = self._events.get_nowait()
                kind = event.get('type')
                if kind == 'status':
                    self.status_text.configure(text=str(event.get('text') or ''))
                elif kind == 'error':
                    text = str(event.get('text') or 'Something went wrong.')
                    self.status_text.configure(text=text[:160])
                    logging.warning('Service error: %s', text[:300])
                elif kind == 'quick_code':
                    self.quick_code_label.configure(text=str(event.get('code') or ''))
                    self.status_text.configure(text='Approve the code from a signed-in Jellyfin device.')
                elif kind == 'connected':
                    self.connection_pill.configure(text=f'●  Connected · {event.get("name") or "Jellyfin"}', text_color=COLORS['green'])
                    self.quick_code_label.configure(text='Connected ✓')
                    self.status_text.configure(text=f'Connected to {event.get("server") or "Jellyfin"}.')
                elif kind == 'playback':
                    self._render_playback(
                        event.get('media'), str(event.get('poster') or ''), event.get('preview_art')
                    )
                elif kind == 'poster_image':
                    image = event.get('image')
                    if event.get('url') == self._poster_url and image is not None:
                        self._poster_source = image.copy().convert('RGBA')
                        self._loaded_poster_url = self._poster_url
                        self._set_preview_image(self._poster_source)
                    elif event.get('url') == self._poster_url:
                        self.poster_label.configure(image=None, text='ARTWORK UNAVAILABLE')
                elif kind == 'libraries':
                    self.status_text.configure(text='Choose the libraries that can appear in Discord.')
                    self._show_libraries(event.get('items') or [])
                elif kind == 'presence':
                    if event.get('active'):
                        self.connection_pill.configure(text='●  Activity live', text_color=COLORS['green'])
                    elif self.settings.jellyfin_token:
                        self.connection_pill.configure(text=f'●  Connected · {self.settings.jellyfin_username or "Jellyfin"}', text_color=COLORS['green'])
                elif kind == 'update_check':
                    self._on_update_check(event)
                elif kind == 'update_progress':
                    self.update_progress.set(float(event.get('value') or 0) / 100)
                elif kind == 'update_downloaded':
                    self._finish_update_download(event)
        except queue.Empty:
            pass
        self._animate_preview()
        self.after(120, self._drain_events)

    def _render_playback(self, media: MediaSession | None, poster_url: str, preview_art: bytes | None = None) -> None:
        if poster_url != self._poster_url:
            self._poster_source = None
            self._loaded_poster_url = ''
        self._active_media = media
        self._poster_url = poster_url
        self._preview_started = time.monotonic()
        self._preview_position = media.position_seconds if media else 0
        if media is None:
            self.preview_heading.configure(text='WATCHING YOUR JELLYFIN SERVER')
            self.preview_title.configure(text='Start playback to see your activity')
            self.preview_subtitle.configure(text='Movies, episodes, and music will appear here.')
            self.preview_state.configure(text='Waiting for Jellyfin playback')
            self.elapsed_label.configure(text='0:00')
            self.duration_label.configure(text='0:00')
            self.preview_progress.set(0)
            self.poster_label.configure(image=None, text='GHOSTYFLIX')
            self._poster_image = None
            self._poster_source = None
            self._loaded_poster_url = ''
            return
        heading = f'{"LISTENING TO" if media.media_type == "Music" else "WATCHING"} {media.server_name.upper()}'
        self.preview_heading.configure(text=heading[:80])
        display_title = media.title
        if media.media_type == 'Movie' and media.year:
            display_title += f' ({media.year})'
        elif media.media_type == 'Music':
            display_title = media.title
        self.preview_title.configure(text=display_title)
        genres = ' · '.join(media.genres[:max(0, self.settings.genre_limit)]) if media.media_type in {'Movie', 'Episode'} else ''
        self.preview_subtitle.configure(text=media.subtitle or genres or ('Movie' if media.media_type == 'Movie' else media.media_type))
        self.preview_state.configure(text=self._preview_status_text(media))
        self.elapsed_label.configure(text=self._clock(media.position_seconds))
        self.duration_label.configure(text=self._clock(media.duration_seconds))
        self.preview_progress.set(media.progress)
        if preview_art:
            try:
                image = Image.open(io.BytesIO(preview_art)).convert('RGBA')
                self._poster_source = image
                self._loaded_poster_url = poster_url
                self._set_preview_image(image)
            except Exception:
                self.poster_label.configure(image=None, text='ARTWORK UNAVAILABLE')
        elif poster_url and poster_url == self._loaded_poster_url and self._poster_image:
            if self._poster_source is not None:
                self._set_preview_image(self._poster_source)
        else:
            self.poster_label.configure(image=None, text='LOADING ART…' if poster_url else 'GHOSTYFLIX')
        if poster_url and poster_url != self._loaded_poster_url:
            threading.Thread(target=self._download_preview_image, args=(poster_url,), daemon=True).start()

    def _set_preview_image(self, source: Image.Image) -> None:
        image = source.convert('RGBA').resize((148, 196), Image.Resampling.LANCZOS)
        media = self._active_media
        if self.settings.show_playback_badge and media is not None:
            draw = ImageDraw.Draw(image)
            left, top = 96, 144
            draw.ellipse((left - 3, top - 3, left + 51, top + 51), fill='#090B0E')
            draw.ellipse((left, top, left + 48, top + 48), fill=self._validated_color())
            if media.paused:
                draw.rounded_rectangle((left + 15, top + 12, left + 22, top + 36), radius=2, fill='#FFFFFF')
                draw.rounded_rectangle((left + 27, top + 12, left + 34, top + 36), radius=2, fill='#FFFFFF')
            else:
                draw.polygon(((left + 18, top + 11), (left + 18, top + 37), (left + 37, top + 24)), fill='#FFFFFF')
        self._poster_image = ctk.CTkImage(light_image=image, dark_image=image, size=(148, 196))
        self.poster_label.configure(image=self._poster_image, text='')

    def _download_preview_image(self, url: str) -> None:
        try:
            import requests
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert('RGBA')
            image.thumbnail((148, 196), Image.Resampling.LANCZOS)
            self._events.put({'type': 'poster_image', 'url': url, 'image': image})
        except Exception:
            self._events.put({'type': 'poster_image', 'url': url, 'image': None})

    def _animate_preview(self) -> None:
        media = self._active_media
        if not media:
            return
        position = media.position_seconds
        if not media.paused:
            position += max(0, int(time.monotonic() - self._preview_started))
        position = min(position, media.duration_seconds) if media.duration_seconds else position
        self.elapsed_label.configure(text=self._clock(position))
        if media.duration_seconds:
            self.preview_progress.set(min(1, max(0, position / media.duration_seconds)))
        remaining = max(0, media.duration_seconds - position)
        percent = int(position / media.duration_seconds * 100) if media.duration_seconds else 0
        self.preview_state.configure(text=self._preview_status_text(media, percent, remaining))

    def _preview_status_text(self, media: MediaSession, percent: int | None = None, remaining: int | None = None) -> str:
        values = ['Paused' if media.paused else 'Playing']
        if self.settings.show_progress_text and media.duration_seconds:
            pct = int(media.progress * 100) if percent is None else percent
            left = media.remaining_seconds if remaining is None else remaining
            values.extend((f'{pct}% watched', f'{format_clock(left)} left'))
        return '  ·  '.join(values)

    @staticmethod
    def _clock(seconds: int) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes}:{seconds:02}'

    def _check_for_updates(self) -> None:
        if self._update_busy:
            return
        self._save_repository_only()
        repo = self.settings.update_repository
        self._update_busy = True
        self.update_button.configure(state='disabled', text='Checking…')
        threading.Thread(target=self._check_update_worker, args=(repo,), daemon=True).start()

    def _save_repository_only(self) -> None:
        repository = self.repository_entry.get().strip()
        if repository:
            self.settings.update_repository = repository
            self.settings.save()

    def _check_update_worker(self, repository: str) -> None:
        try:
            release = find_release(repository)
            self._events.put({'type': 'update_check', 'release': release, 'newer': bool(release and is_newer(release))})
        except Exception as exc:
            self._events.put({'type': 'update_check', 'error': str(exc)})

    def _on_update_check(self, event: dict[str, Any]) -> None:
        self._update_busy = False
        self.update_button.configure(state='normal', text='Check now')
        release = event.get('release')
        if event.get('error'):
            self.status_text.configure(text=f'Update check failed: {str(event["error"])[:120]}')
            return
        if not release:
            self.status_text.configure(text='No Windows release is available yet.')
            return
        if event.get('newer'):
            self._latest_release = release
            self.install_button.configure(state='normal')
            self.status_text.configure(text=f'GhostyFlix {release.version} is ready to install.')
        else:
            self._latest_release = None
            self.install_button.configure(state='disabled')
            self.status_text.configure(text=f'You have the latest version · v{__version__}.')

    def _install_update(self) -> None:
        if not self._latest_release or self._update_busy:
            return
        if not getattr(sys, 'frozen', False):
            open_release_page(self.settings.update_repository)
            self.status_text.configure(text='Opened the latest release page. In-app installation requires the Windows app build.')
            return
        self._update_busy = True
        self.install_button.configure(state='disabled', text='Downloading…')
        self.update_progress.set(0)
        threading.Thread(target=self._download_update_worker, args=(self._latest_release,), daemon=True).start()

    def _download_update_worker(self, release: Release) -> None:
        try:
            package = download_release(release, lambda percent: self._events.put({'type': 'update_progress', 'value': percent}))
            self._events.put({'type': 'update_downloaded', 'path': str(package)})
        except Exception as exc:
            self._events.put({'type': 'update_downloaded', 'error': str(exc)})

    def _finish_update_download(self, event: dict[str, Any]) -> None:
        self._update_busy = False
        if event.get('error'):
            self.install_button.configure(state='normal', text='Install & restart')
            self.status_text.configure(text=f'Update could not be installed: {str(event["error"])[:120]}')
            return
        try:
            self.status_text.configure(text='Verified update downloaded. Restarting GhostyFlix…')
            self.service.close()
            launch_replacement(Path(str(event['path'])))
        except Exception as exc:
            self.install_button.configure(state='normal', text='Install & restart')
            self.status_text.configure(text=f'Could not start the installer: {str(exc)[:120]}')

    def _start_minimized_if_requested(self) -> None:
        if self.settings.start_minimized:
            self._hide_to_tray()

    def _on_close(self) -> None:
        if self.settings.close_to_tray:
            self._hide_to_tray()
        else:
            self._exit_app()

    def _hide_to_tray(self) -> None:
        if pystray is None:
            self.iconify()
            self.status_text.configure(text='GhostyFlix is minimized. Tray support is unavailable on this system.')
            return
        if self._tray_icon:
            self.withdraw()
            return
        try:
            image = Image.open(resource_path('assets', 'icon.png')).convert('RGBA')
            menu = pystray.Menu(
                pystray.MenuItem('Show GhostyFlix RPC', lambda icon, item: self.after(0, self._restore_from_tray), default=True),
                pystray.MenuItem('Exit', lambda icon, item: self.after(0, self._exit_app)),
            )
            self._tray_icon = pystray.Icon('ghostyflix-rpc', image, APP_NAME, menu)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
            self.withdraw()
        except Exception as exc:
            logging.warning('Tray icon could not be started: %s', type(exc).__name__)
            self.iconify()

    def _restore_from_tray(self) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.deiconify()
        self.lift()

    def _exit_app(self) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.service.close()
        self.destroy()


def run() -> None:
    configure_logging()
    app = GhostyFlixApp()
    app.mainloop()


if __name__ == '__main__':
    run()
