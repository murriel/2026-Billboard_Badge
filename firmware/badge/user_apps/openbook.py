"""Open Book E-Reader App for Billboard Badge

Inspired by Joey Castillo's Open Book project and Libros architecture.
Renders pre-paginated books on the 9.7-inch 960x672 3-color e-paper screen.
Supports multi-book switching, chapter navigation, and per-book bookmarks.
"""

import gc
import json
import lvgl
import os
import time

from apps.base_app import BaseApp
from lib.button import MenuMinus, MenuPlus, UserA, UserB, Boot
from lib.epd import display, display_width, display_height
from lib.led_bar import leds

_WHITE = lvgl.color_hex(0xFFFFFF)
_BLACK = lvgl.color_hex(0x000000)
_RED   = lvgl.color_hex(0xFF0000)

_FONTS = [
    (lvgl.font_montserrat_16, "16pt"),
    (lvgl.font_montserrat_24, "24pt"),
    (lvgl.font_montserrat_28, "28pt"),
    (lvgl.font_montserrat_32, "32pt"),
]


class OpenBookApp(BaseApp):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name or "OpenBook")
        self.sleep_ms = 50
        self.launched = False

        self.books_base_dir = "/data/books"
        self.state_file = "/data/openbook_state.json"

        self.catalog = []
        self.book_idx = 0
        self.current_chapter = 1
        self.current_page = 0
        self.font_idx = 1  # Medium font
        self.bookmarks = {}

        self.index = None
        self.chapter_data = None
        self.loaded_chapter_id = None

        self._load_catalog()
        self._load_state()

    def _load_catalog(self):
        cat_path = f"{self.books_base_dir}/catalog.json"
        try:
            with open(cat_path, "r") as f:
                self.catalog = json.load(f)
        except Exception:
            # Fallback if catalog.json is missing
            self.catalog = [
                {"slug": "jane_eyre", "title": "Jane Eyre", "author": "Charlotte Brontë"},
                {"slug": "dracula", "title": "Dracula", "author": "Bram Stoker"},
                {"slug": "agatha_christie", "title": "The Mysterious Affair at Styles", "author": "Agatha Christie"},
                {"slug": "dorian_gray", "title": "The Picture of Dorian Gray", "author": "Oscar Wilde"},
                {"slug": "war_of_the_worlds", "title": "The War of the Worlds", "author": "H. G. Wells"},
                {"slug": "meditations", "title": "Meditations", "author": "Marcus Aurelius"},
                {"slug": "beyond_good_and_evil", "title": "Beyond Good and Evil", "author": "Friedrich Nietzsche"},
            ]

    def _curr_book_slug(self):
        if not self.catalog:
            return "jane_eyre"
        return self.catalog[self.book_idx % len(self.catalog)]["slug"]

    def _curr_book_dir(self):
        return f"{self.books_base_dir}/{self._curr_book_slug()}"

    def _load_state(self):
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                active_slug = state.get("active_book", "jane_eyre")
                self.font_idx = state.get("font_idx", self.font_idx)
                self.bookmarks = state.get("bookmarks", {})

                # Find book index matching active slug
                for idx, b in enumerate(self.catalog):
                    if b.get("slug") == active_slug:
                        self.book_idx = idx
                        break

                bm = self.bookmarks.get(active_slug, {})
                self.current_chapter = bm.get("chapter", 1)
                self.current_page = bm.get("page", 0)
        except Exception:
            pass

    def _save_state(self):
        slug = self._curr_book_slug()
        self.bookmarks[slug] = {
            "chapter": self.current_chapter,
            "page": self.current_page,
        }
        try:
            with open(self.state_file, "w") as f:
                json.dump({
                    "active_book": slug,
                    "font_idx": self.font_idx,
                    "bookmarks": self.bookmarks,
                }, f)
        except Exception as ex:
            print(f"Error saving reader state: {ex}")

    def _load_index(self):
        gc.collect()
        book_dir = self._curr_book_dir()
        try:
            with open(f"{book_dir}/index.json", "r") as f:
                self.index = json.load(f)
        except Exception as ex:
            print(f"Error loading index for {book_dir}: {ex}")
            slug = self._curr_book_slug()
            self.index = {
                "title": slug.replace("_", " ").title(),
                "author": "",
                "total_chapters": 1,
                "chapters": [],
            }

    def _load_chapter(self, chapter_id):
        if self.chapter_data is not None and self.loaded_chapter_id == chapter_id:
            return self.chapter_data

        gc.collect()
        book_dir = self._curr_book_dir()
        ch_file = f"{book_dir}/ch{chapter_id:02d}.json"
        try:
            with open(ch_file, "r") as f:
                self.chapter_data = json.load(f)
                self.loaded_chapter_id = chapter_id
        except Exception as ex:
            print(f"Error loading chapter {ch_file}: {ex}")
            self.chapter_data = {
                "title": f"Chapter {chapter_id}",
                "pages": [f"[Could not load chapter {chapter_id}]"],
            }
            self.loaded_chapter_id = chapter_id
        return self.chapter_data

    def draw_current_page(self):
        leds.fill((0, 1, 1))  # Cyan LED indicates rendering in progress

        self._load_index()
        ch_info = self._load_chapter(self.current_chapter)
        pages = ch_info.get("pages", [""])
        total_pages = len(pages)

        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        page_text = pages[self.current_page]
        book_title = self.index.get("title", "OpenBook")
        author_name = self.index.get("author", "")
        chapter_title = ch_info.get("title", f"Chapter {self.current_chapter}")
        total_ch = self.index.get("total_chapters", 1)
        font, font_label = _FONTS[self.font_idx % len(_FONTS)]

        # Construct LVGL screen
        scr = lvgl.obj()
        scr.remove_style_all()
        scr.set_size(display_width, display_height)
        scr.set_style_bg_color(_WHITE, 0)
        scr.set_style_bg_opa(lvgl.OPA.COVER, 0)

        # --- Top Header Bar ---
        header = lvgl.obj(scr)
        header.remove_style_all()
        header.set_pos(40, 12)
        header.set_size(display_width - 80, 36)

        title_lbl = lvgl.label(header)
        author_str = f" — {author_name}" if author_name else ""
        title_lbl.set_text(f"{book_title}{author_str}")
        title_lbl.set_style_text_color(_BLACK, 0)
        title_lbl.set_style_text_font(lvgl.font_montserrat_24, 0)
        title_lbl.align(lvgl.ALIGN.LEFT_MID, 0, 0)

        chap_lbl = lvgl.label(header)
        chap_lbl.set_text(f"{chapter_title} ({self.current_chapter}/{total_ch})")
        chap_lbl.set_style_text_color(_RED, 0)
        chap_lbl.set_style_text_font(lvgl.font_montserrat_16, 0)
        chap_lbl.align(lvgl.ALIGN.RIGHT_MID, 0, 0)

        # Red divider line under header
        h_line = lvgl.obj(scr)
        h_line.remove_style_all()
        h_line.set_pos(40, 48)
        h_line.set_size(display_width - 80, 2)
        h_line.set_style_bg_color(_RED, 0)
        h_line.set_style_bg_opa(lvgl.OPA.COVER, 0)

        # --- Main Reading Body ---
        body_lbl = lvgl.label(scr)
        body_lbl.remove_style_all()
        body_lbl.set_pos(45, 56)
        body_lbl.set_size(display_width - 90, display_height - 86)
        body_lbl.set_text(page_text)
        body_lbl.set_style_text_color(_BLACK, 0)
        body_lbl.set_style_text_font(font, 0)
        body_lbl.set_long_mode(lvgl.LABEL_LONG_MODE.WRAP)

        # --- Bottom Control Footer (Very Small / Compact) ---
        f_line = lvgl.obj(scr)
        f_line.remove_style_all()
        f_line.set_pos(40, display_height - 24)
        f_line.set_size(display_width - 80, 1)
        f_line.set_style_bg_color(_BLACK, 0)
        f_line.set_style_bg_opa(lvgl.OPA.COVER, 0)

        footer = lvgl.obj(scr)
        footer.remove_style_all()
        footer.set_pos(40, display_height - 20)
        footer.set_size(display_width - 80, 16)

        # Controls hint on the left in small 14pt font
        controls_lbl = lvgl.label(footer)
        controls_lbl.set_text("[User A] Next  [User B] Prev  [Boot] Font (Hold: Book)  [Menu] Switch App")
        controls_lbl.set_style_text_color(_BLACK, 0)
        controls_lbl.set_style_text_font(lvgl.font_montserrat_14, 0)
        controls_lbl.align(lvgl.ALIGN.LEFT_MID, 0, 0)

        # Page and Library progress on the right in red accent
        status_lbl = lvgl.label(footer)
        book_info = f"Book {self.book_idx + 1}/{len(self.catalog)}"
        page_info = f"Pg {self.current_page + 1}/{total_pages}"
        status_lbl.set_text(f"{page_info}  •  {book_info}  [{font_label}]")
        status_lbl.set_style_text_color(_RED, 0)
        status_lbl.set_style_text_font(lvgl.font_montserrat_14, 0)
        status_lbl.align(lvgl.ALIGN.RIGHT_MID, 0, 0)

        # Clear and flush display
        display.clear()
        lvgl.screen_load(scr)
        scr.update_layout()
        lvgl.refr_now(display.lv_display)

        # Trigger physical e-paper refresh
        display.update()
        leds.fill((0, 1, 0))  # Green LED indicates refresh complete

        self._save_state()
        gc.collect()

    def switch_book(self, step=1):
        """Switch to next/previous book in catalog, preserving bookmarks."""
        self._save_state()
        self.book_idx = (self.book_idx + step) % len(self.catalog)
        self.index = None
        self.chapter_data = None
        self.loaded_chapter_id = None

        new_slug = self._curr_book_slug()
        bm = self.bookmarks.get(new_slug, {})
        self.current_chapter = bm.get("chapter", 1)
        self.current_page = bm.get("page", 0)

        print(f"Switching book to: {new_slug} (Ch {self.current_chapter}, Pg {self.current_page + 1})")
        self.draw_current_page()

    def run(self):
        if self.launched:
            self._load_catalog()
            self._load_state()
            slug = self._curr_book_slug()
            print(f"Launching {self.name} with '{slug}' at Ch {self.current_chapter}, Page {self.current_page + 1}...")
            self.draw_current_page()
            return

        # User A: Next Page (advances chapter when reaching end of chapter)
        if UserA.pressed() or MenuPlus.pressed():
            ch_info = self._load_chapter(self.current_chapter)
            total_pages = len(ch_info.get("pages", []))
            if self.current_page < total_pages - 1:
                self.current_page += 1
                self.draw_current_page()
            elif self.current_chapter < self.index.get("total_chapters", 1):
                self.current_chapter += 1
                self.current_page = 0
                self.draw_current_page()

        # User B: Previous Page (goes to previous chapter when reaching start)
        elif UserB.pressed() or MenuMinus.pressed():
            if self.current_page > 0:
                self.current_page -= 1
                self.draw_current_page()
            elif self.current_chapter > 1:
                self.current_chapter -= 1
                prev_ch = self._load_chapter(self.current_chapter)
                self.current_page = max(0, len(prev_ch.get("pages", [])) - 1)
                self.draw_current_page()

        # Boot Button: Tap = Cycle Font Size, Hold (> 600ms) = Next Book in Library
        elif Boot.pressed():
            start_ms = time.ticks_ms()
            is_hold = False
            while Boot.value:
                if time.ticks_diff(time.ticks_ms(), start_ms) > 600:
                    is_hold = True
                    break
                time.sleep_ms(20)
            if is_hold:
                print("Boot held: switching to next book")
                self.switch_book(+1)
            else:
                self.font_idx = (self.font_idx + 1) % len(_FONTS)
                font_name = _FONTS[self.font_idx][1]
                print(f"Boot tapped: cycled font to {font_name}")
                self.draw_current_page()
