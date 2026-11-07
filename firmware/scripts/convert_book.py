#!/usr/bin/env python3
"""
Convert EPUB books (specifically Standard Ebooks releases) into the
Open Book / Libros format and optimized chapter chunks for the Billboard Badge.
"""

import argparse
import glob
import html
from html.parser import HTMLParser
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile


class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self._curr_p = []
        self._in_p = False
        self._in_heading = False
        self._curr_heading = []
        self.heading = None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4"):
            self._in_heading = True
            self._curr_heading = []
        elif tag == "p":
            self._in_p = True
            self._curr_p = []

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4"):
            self._in_heading = False
            h_text = " ".join("".join(self._curr_heading).split())
            if h_text and not self.heading:
                self.heading = h_text
        elif tag == "p":
            self._in_p = False
            p_text = " ".join("".join(self._curr_p).split())
            if p_text:
                self.paragraphs.append(p_text)

    def handle_data(self, data):
        if self._in_heading:
            self._curr_heading.append(data)
        elif self._in_p:
            self._curr_p.append(data)


def paginate_paragraphs(paragraphs: list[str], target_words_per_page: int = 220) -> list[str]:
    """Group paragraphs into page chunks suitable for the 960x672 display."""
    pages = []
    curr_page_paras = []
    curr_words = 0

    for p in paragraphs:
        p_words = len(p.split())
        # If a single paragraph is enormous, split by sentence
        if p_words > target_words_per_page * 1.5:
            sentences = re.split(r"(?<=[.!?])\s+", p)
            for s in sentences:
                s_words = len(s.split())
                if curr_words + s_words > target_words_per_page and curr_page_paras:
                    pages.append("\n\n".join(curr_page_paras))
                    curr_page_paras = [s]
                    curr_words = s_words
                else:
                    curr_page_paras.append(s)
                    curr_words += s_words
            continue

        if curr_words + p_words > target_words_per_page and curr_page_paras:
            pages.append("\n\n".join(curr_page_paras))
            curr_page_paras = [p]
            curr_words = p_words
        else:
            curr_page_paras.append(p)
            curr_words += p_words

    if curr_page_paras:
        pages.append("\n\n".join(curr_page_paras))

    return pages if pages else [""]


def convert_epub(epub_path: str, output_dir: str, max_chapters: int = 2):
    if not os.path.exists(epub_path):
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    os.makedirs(output_dir, exist_ok=True)
    # Clean up old chapter files in output_dir
    for old_file in glob.glob(os.path.join(output_dir, "ch*.json")):
        try:
            os.remove(old_file)
        except OSError:
            pass

    with zipfile.ZipFile(epub_path, "r") as z:
        # Parse container.xml to locate rootfile OPF
        container_xml = z.read("META-INF/container.xml")
        c_root = ET.fromstring(container_xml)
        ns_c = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        opf_path = c_root.find(".//c:rootfile", ns_c).get("full-path")
        opf_dir = os.path.dirname(opf_path)

        # Parse OPF
        opf_data = z.read(opf_path)
        opf_root = ET.fromstring(opf_data)
        ns_o = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}

        title_el = opf_root.find(".//dc:title", ns_o)
        author_el = opf_root.find(".//dc:creator", ns_o)
        title = title_el.text if title_el is not None else "Untitled"
        author = author_el.text if author_el is not None else "Unknown"

        manifest = {
            item.get("id"): item.get("href")
            for item in opf_root.findall(".//opf:manifest/opf:item", ns_o)
        }
        spine = [
            manifest.get(itemref.get("idref"))
            for itemref in opf_root.findall(".//opf:spine/opf:itemref", ns_o)
        ]

        print(f"Converting: '{title}' by {author} (max {max_chapters} chapters)")

        canonical_lines = [f"# {title}", f"## {author}", ""]
        chapters_meta = []
        chapter_num = 1

        for href in spine:
            if not href:
                continue

            # Skip front/back matter (titlepage, imprint, colophon, preface, epigraph, notes, etc.)
            href_lower = href.lower()
            if any(skip_word in href_lower for skip_word in (
                "titlepage", "imprint", "colophon", "halftitle", "uncopyright",
                "preface", "editorial-note", "dedication", "epigraph", "endnotes", "toc"
            )):
                continue

            full_href = os.path.normpath(os.path.join(opf_dir, href)).replace("\\", "/")
            try:
                doc_bytes = z.read(full_href)
            except KeyError:
                continue

            parser = SimpleHTMLTextExtractor()
            parser.feed(doc_bytes.decode("utf-8", errors="ignore"))

            # Skip divider pages or empty fragments with fewer than 2 paragraphs
            if len(parser.paragraphs) < 2:
                continue

            chapter_title = parser.heading or f"Chapter {chapter_num}"

            # Clean canonical format
            canonical_lines.append("\x0c")  # Form Feed
            canonical_lines.append(f"### {chapter_title}")
            canonical_lines.append("")
            canonical_lines.append("\n\n".join(parser.paragraphs))
            canonical_lines.append("")

            # Paginate for badge display
            pages = paginate_paragraphs(parser.paragraphs, target_words_per_page=220)

            ch_filename = f"ch{chapter_num:02d}.json"
            ch_dest = os.path.join(output_dir, ch_filename)
            with open(ch_dest, "w", encoding="utf-8") as ch_f:
                json.dump({"title": chapter_title, "pages": pages}, ch_f, ensure_ascii=False)

            chapters_meta.append({
                "id": chapter_num,
                "title": chapter_title,
                "file": ch_filename,
                "total_pages": len(pages),
                "total_words": sum(len(p.split()) for p in parser.paragraphs),
            })
            print(f"  [Ch {chapter_num:02d}] {chapter_title}: {len(pages)} pages")
            chapter_num += 1

            if max_chapters and len(chapters_meta) >= max_chapters:
                break

        # Save index.json
        index_data = {
            "title": title,
            "author": author,
            "total_chapters": len(chapters_meta),
            "chapters": chapters_meta,
        }
        with open(os.path.join(output_dir, "index.json"), "w", encoding="utf-8") as idx_f:
            json.dump(index_data, idx_f, indent=2, ensure_ascii=False)

        # Save Joey Castillo Libros canonical format
        canonical_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../books/canonical"))
        os.makedirs(canonical_dir, exist_ok=True)
        book_slug = os.path.basename(os.path.normpath(output_dir))
        canonical_path = os.path.join(canonical_dir, f"{book_slug}_canonical.txt")
        with open(canonical_path, "w", encoding="utf-8") as can_f:
            can_f.write("\n".join(canonical_lines))

        print(f"  -> Saved {len(chapters_meta)} chapters to '{output_dir}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert EPUB to Open Book Badge format")
    parser.add_argument("epub", help="Path to .epub file")
    parser.add_argument("output", help="Output directory on badge")
    parser.add_argument("--max-chapters", type=int, default=2, help="Maximum number of chapters to convert (default: 2)")
    args = parser.parse_args()
    convert_epub(args.epub, args.output, max_chapters=args.max_chapters)
