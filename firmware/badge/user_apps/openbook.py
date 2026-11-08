"""Open Book E-Reader App for Billboard Badge

Inspired by Joey Castillo's Open Book project and Libros architecture.
Renders pre-paginated books on the 9.7-inch 960x672 3-color e-paper screen.
Features an interactive Bookshelf directory, multi-book switching, and bookmarks.
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
        self.font_idx = 1  # 24pt Medium font
        self.bookmarks = {}
        self.view_mode = "bookshelf"  # "bookshelf" or "reading"

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
                {"slug": "agatha_christie", "title": "The Mysterious Affair at Styles", "author": "Agatha Christie", "total_chapters": 2},
                {"slug": "beyond_good_and_evil", "title": "Beyond Good and Evil", "author": "Friedrich Nietzsche", "total_chapters": 2},
                {"slug": "dorian_gray", "title": "The Picture of Dorian Gray", "author": "Oscar Wilde", "total_chapters": 2},
                {"slug": "dracula", "title": "Dracula", "author": "Bram Stoker", "total_chapters": 2},
                {"slug": "jane_eyre", "title": "Jane Eyre", "author": "Charlotte Brontë", "total_chapters": 2},
                {"slug": "meditations", "title": "Meditations", "author": "Marcus Aurelius", "total_chapters": 2},
                {"slug": "war_of_the_worlds", "title": "The War of the Worlds", "author": "H. G. Wells", "total_chapters": 2},
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

    def draw_bookshelf(self):
        """Render the Bookshelf directory landing page."""
        leds.fill((0, 1, 1))  # Cyan LED indicates rendering in progress
        self._load_catalog()

        scr = lvgl.obj()
        scr.remove_style_all()
        scr.set_size(display_width, display_height)
        scr.set_style_bg_color(_WHITE, 0)
        scr.set_style_bg_opa(lvgl.OPA.COVER, 0)

        # Header Bar
        header = lvgl.obj(scr)
        header.remove_style_all()
        header.set_pos(40, 12)
        header.set_size(display_width - 80, 36)

        title_lbl = lvgl.label(header)
        title_lbl.set_text("OpenBook — Library & Bookshelf")
        title_lbl.set_style_text_color(_BLACK, 0)
        title_lbl.set_style_text_font(lvgl.font_montserrat_24, 0)
        title_lbl.align(lvgl.ALIGN.LEFT_MID, 0, 0)

        count_lbl = lvgl.label(header)
        count_lbl.set_text(f"{len(self.catalog)} Books Available")
        count_lbl.set_style_text_color(_RED, 0)
        count_lbl.set_style_text_font(lvgl.font_montserrat_16, 0)
        count_lbl.align(lvgl.ALIGN.RIGHT_MID, 0, 0)

        # Red Divider Line
        h_line = lvgl.obj(scr)
        h_line.remove_style_all()
        h_line.set_pos(40, 48)
        h_line.set_size(display_width - 80, 2)
        h_line.set_style_bg_color(_RED, 0)
        h_line.set_style_bg_opa(lvgl.OPA.COVER, 0)

        # Bookshelf List Container
        start_y = 58
        item_height = 80
        for idx, book in enumerate(self.catalog):
            y_pos = start_y + (idx * item_height)
            is_selected = (idx == self.book_idx)

            card = lvgl.obj(scr)
            card.remove_style_all()
            card.set_pos(40, y_pos)
            card.set_size(display_width - 80, item_height - 6)

            # Selected indicator bar on left
            if is_selected:
                bar = lvgl.obj(card)
                bar.remove_style_all()
                bar.set_pos(0, 4)
                bar.set_size(6, item_height - 14)
                bar.set_style_bg_color(_RED, 0)
                bar.set_style_bg_opa(lvgl.OPA.COVER, 0)

            # Book Title
            title = lvgl.label(card)
            title.remove_style_all()
            title.set_pos(18 if is_selected else 10, 4)
            title.set_size(display_width - 120, 28)
            prefix = "▶  " if is_selected else f"{idx + 1}.  "
            title.set_text(f"{prefix}{book.get('title', 'Untitled')}")
            title.set_style_text_font(lvgl.font_montserrat_24, 0)
            title.set_style_text_color(_RED if is_selected else _BLACK, 0)

            # Book Subtitle: Author, total chapters, and bookmark status
            sub = lvgl.label(card)
            sub.remove_style_all()
            sub.set_pos(18 if is_selected else 10, 36)
            sub.set_size(display_width - 120, 22)
            slug = book.get("slug", "")
            bm = self.bookmarks.get(slug, {})
            bm_str = f"   •   Bookmark: Ch {bm.get('chapter', 1)}, Pg {bm.get('page', 0) + 1}" if slug in self.bookmarks else ""
            sub.set_text(f"By {book.get('author', 'Unknown')}  ({book.get('total_chapters', 1)} Chapters){bm_str}")
            sub.set_style_text_font(lvgl.font_montserrat_16, 0)
            sub.set_style_text_color(_BLACK, 0)

        # Footer Divider Line
        f_line = lvgl.obj(scr)
        f_line.remove_style_all()
        f_line.set_pos(40, display_height - 24)
        f_line.set_size(display_width - 80, 1)
        f_line.set_style_bg_color(_BLACK, 0)
        f_line.set_style_bg_opa(lvgl.OPA.COVER, 0)

        # Bottom Footer Controls
        footer = lvgl.obj(scr)
        footer.remove_style_all()
        footer.set_pos(40, display_height - 20)
        footer.set_size(display_width - 80, 16)

        ctrl_lbl = lvgl.label(footer)
        ctrl_lbl.set_text("[User A] Down   [User B] Up   [Boot] Read Book   [Menu +/-] Switch App")
        ctrl_lbl.set_style_text_color(_BLACK, 0)
        ctrl_lbl.set_style_text_font(lvgl.font_montserrat_14, 0)
        ctrl_lbl.align(lvgl.ALIGN.LEFT_MID, 0, 0)

        pos_lbl = lvgl.label(footer)
        pos_lbl.set_text(f"Selected: {self.book_idx + 1}/{len(self.catalog)}")
        pos_lbl.set_style_text_color(_RED, 0)
        pos_lbl.set_style_text_font(lvgl.font_montserrat_14, 0)
        pos_lbl.align(lvgl.ALIGN.RIGHT_MID, 0, 0)

        # Clear and flush display
        display.clear()
        lvgl.screen_load(scr)
        scr.update_layout()
        lvgl.refr_now(display.lv_display)

        display.update()
        leds.fill((0, 1, 0))  # Green LED indicates refresh complete
        gc.collect()

    def draw_current_page(self):
        """Render the reading page for the active book."""
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

        # --- Bottom Control Footer ---
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

        controls_lbl = lvgl.label(footer)
        controls_lbl.set_text("[User A] Next  [User B] Prev  [Boot] Font (Hold: Bookshelf)  [Menu] Switch App")
        controls_lbl.set_style_text_color(_BLACK, 0)
        controls_lbl.set_style_text_font(lvgl.font_montserrat_14, 0)
        controls_lbl.align(lvgl.ALIGN.LEFT_MID, 0, 0)

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

    def run(self):
        if self.launched:
            self._load_catalog()
            self._load_state()
            self.view_mode = "bookshelf"
            print(f"Launching {self.name} on Bookshelf...")
            self.draw_bookshelf()
            return

        # ==========================================
        # 1. BOOKSHELF VIEW NAVIGATION
        # ==========================================
        if self.view_mode == "bookshelf":
            # User A: Move down in bookshelf list
            if UserA.pressed() or MenuPlus.pressed():
                self.book_idx = (self.book_idx + 1) % len(self.catalog)
                print(f"Bookshelf: selected #{self.book_idx + 1} ({self._curr_book_slug()})")
                self.draw_bookshelf()

            # User B: Move up in bookshelf list
            elif UserB.pressed() or MenuMinus.pressed():
                self.book_idx = (self.book_idx - 1) % len(self.catalog)
                print(f"Bookshelf: selected #{self.book_idx + 1} ({self._curr_book_slug()})")
                self.draw_bookshelf()

            # Boot Button: Open selected book to read
            elif Boot.pressed():
                slug = self._curr_book_slug()
                bm = self.bookmarks.get(slug, {})
                self.current_chapter = bm.get("chapter", 1)
                self.current_page = bm.get("page", 0)
                self.index = None
                self.chapter_data = None
                self.loaded_chapter_id = None
                self.view_mode = "reading"
                print(f"Opening book '{slug}' at Ch {self.current_chapter}, Page {self.current_page + 1}...")
                self.draw_current_page()

        # ==========================================
        # 2. READING VIEW NAVIGATION
        # ==========================================
        elif self.view_mode == "reading":
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

            # Boot Button: Tap = Cycle Font Size, Hold (> 600ms) = Return to Bookshelf
            elif Boot.pressed():
                start_ms = time.ticks_ms()
                is_hold = False
                while Boot.value:
                    if time.ticks_diff(time.ticks_ms(), start_ms) > 600:
                        is_hold = True
                        break
                    time.sleep_ms(20)
                if is_hold:
                    print("Boot held: returning to Bookshelf")
                    self.view_mode = "bookshelf"
                    self.draw_bookshelf()
                else:
                    self.font_idx = (self.font_idx + 1) % len(_FONTS)
                    font_name = _FONTS[self.font_idx][1]
                    print(f"Boot tapped: cycled font to {font_name}")
                    self.draw_current_page()
