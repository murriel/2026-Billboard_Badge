#!/usr/bin/env python3
"""
Convert cat photo (IMG_7958.JPG) into an optimized 960x672 3-color e-paper graphic
(White, Black, Red) for the Billboard Badge, with an authentic 24pt 7-segment display
'murriel' overlay in the bottom-right corner.
"""

import os
import struct
import subprocess
import zlib

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 672
IMG_WIDTH = 874
IMG_HEIGHT = 672
X_OFFSET = (SCREEN_WIDTH - IMG_WIDTH) // 2  # 43 px

COLOR_WHITE = 0
COLOR_BLACK = 1
COLOR_RED = 2

PALETTE = [
    (255, 255, 255),  # 0: White
    (0, 0, 0),        # 1: Black
    (255, 0, 0),      # 2: Red
]


def load_scaled_photo(input_path: str):
    """Scale IMG_7958.JPG to IMG_WIDTH x IMG_HEIGHT raw RGB24 using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={IMG_WIDTH}:{IMG_HEIGHT}",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    raw_bytes, _ = proc.communicate()
    if len(raw_bytes) != IMG_WIDTH * IMG_HEIGHT * 3:
        raise ValueError(f"Unexpected raw image size: {len(raw_bytes)} bytes")
    
    # Place on 960x672 canvas with white side margins
    canvas = [[[255.0, 255.0, 255.0] for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]
    
    idx = 0
    for y in range(IMG_HEIGHT):
        for x in range(IMG_WIDTH):
            r = float(raw_bytes[idx])
            g = float(raw_bytes[idx + 1])
            b = float(raw_bytes[idx + 2])
            canvas[y][x + X_OFFSET] = [r, g, b]
            idx += 3
            
    return canvas


def dither_atkinson(canvas):
    """
    Atkinson dithering for photo against White (0), Black (1), Red (2).
    """
    W = SCREEN_WIDTH
    H = SCREEN_HEIGHT
    output_indices = bytearray(W * H)
    
    for y in range(H):
        for x in range(W):
            pixel = canvas[y][x]
            r, g, b = pixel[0], pixel[1], pixel[2]
            
            # Clamp values
            r = max(0.0, min(255.0, r))
            g = max(0.0, min(255.0, g))
            b = max(0.0, min(255.0, b))
            
            # Check for strong red
            if r > 160.0 and g < 100.0 and b < 100.0 and (r - g) > 70.0:
                chosen_idx = COLOR_RED
                cr, cg, cb = 255.0, 0.0, 0.0
            else:
                # Black or White based on luminance
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if lum >= 128.0:
                    chosen_idx = COLOR_WHITE
                    cr, cg, cb = 255.0, 255.0, 255.0
                else:
                    chosen_idx = COLOR_BLACK
                    cr, cg, cb = 0.0, 0.0, 0.0
                    
            output_indices[y * W + x] = chosen_idx
            
            # Atkinson error diffusion (1/8 to each of 6 neighbors)
            err_r = (r - cr) / 8.0
            err_g = (g - cg) / 8.0
            err_b = (b - cb) / 8.0
            
            neighbors = [
                (x + 1, y), (x + 2, y),
                (x - 1, y + 1), (x, y + 1), (x + 1, y + 1),
                (x, y + 2)
            ]
            for nx, ny in neighbors:
                if 0 <= nx < W and 0 <= ny < H:
                    canvas[ny][nx][0] += err_r
                    canvas[ny][nx][1] += err_g
                    canvas[ny][nx][2] += err_b

    return output_indices


def render_7segment_overlay(indices: bytearray, bottom_right_x=936, bottom_right_y=654):
    """
    Renders 'murriel' in authentic 7-segment digital display styling (24pt)
    inside a sleek dark bezel box in the bottom right corner directly onto
    the output palette indices.
    """
    H = 24  # 24pt height
    T = 3   # 3px segment thickness
    SLANT = 0.16  # classic 9-degree digital slant
    mid = H // 2
    
    # Calculate exact character widths and total layout
    # m: 19px, u: 10px, r: 8px, r: 8px, i: 6px, e: 10px, l: 9px
    # spacing: 4px
    # Total = 19 + 4 + 10 + 4 + 8 + 4 + 8 + 4 + 6 + 4 + 10 + 4 + 9 = 85 px
    TEXT_WIDTH = 88
    BOX_PAD_X = 8
    BOX_PAD_Y = 6
    box_w = TEXT_WIDTH + BOX_PAD_X * 2 + 6
    box_h = H + BOX_PAD_Y * 2
    
    box_x1 = bottom_right_x - box_w
    box_y1 = bottom_right_y - box_h
    box_x2 = bottom_right_x
    box_y2 = bottom_right_y
    
    # 1. Draw solid black bezel plate with red border
    for y in range(box_y1, box_y2):
        for x in range(box_x1, box_x2):
            if 0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT:
                # 1px red border
                if x in (box_x1, box_x2 - 1) or y in (box_y1, box_y2 - 1):
                    indices[y * SCREEN_WIDTH + x] = COLOR_RED
                else:
                    indices[y * SCREEN_WIDTH + x] = COLOR_BLACK
                    
    # Helper to draw slanted rectangles
    text_start_x = box_x1 + BOX_PAD_X + 2
    text_start_y = box_y1 + BOX_PAD_Y
    
    def slant(px, py):
        offset = int((text_start_y + H - py) * SLANT)
        return px + offset, py

    def fill_rect(rx1, ry1, rx2, ry2, color=COLOR_RED):
        for py in range(ry1, ry2):
            for px in range(rx1, rx2):
                sx, sy = slant(px, py)
                if 0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT:
                    indices[sy * SCREEN_WIDTH + sx] = color

    cur_x = text_start_x
    
    # 1. 'm' (two arches joined)
    # Left vertical
    fill_rect(cur_x, text_start_y + mid, cur_x + T, text_start_y + H)
    # Top bar 1
    fill_rect(cur_x + T, text_start_y + mid, cur_x + 9, text_start_y + mid + T)
    # Center vertical
    fill_rect(cur_x + 9, text_start_y + mid, cur_x + 9 + T, text_start_y + H)
    # Top bar 2
    fill_rect(cur_x + 9 + T, text_start_y + mid, cur_x + 18, text_start_y + mid + T)
    # Right vertical
    fill_rect(cur_x + 18, text_start_y + mid, cur_x + 18 + T, text_start_y + H)
    cur_x += 18 + T + 4
    
    # 2. 'u'
    u_w = 10
    fill_rect(cur_x, text_start_y + mid, cur_x + T, text_start_y + H)
    fill_rect(cur_x + T, text_start_y + H - T, cur_x + u_w - T, text_start_y + H)
    fill_rect(cur_x + u_w - T, text_start_y + mid, cur_x + u_w, text_start_y + H)
    cur_x += u_w + 4
    
    # 3. 'r'
    r_w = 8
    fill_rect(cur_x, text_start_y + mid, cur_x + T, text_start_y + H)
    fill_rect(cur_x + T, text_start_y + mid, cur_x + r_w, text_start_y + mid + T)
    cur_x += r_w + 4
    
    # 4. 'r'
    fill_rect(cur_x, text_start_y + mid, cur_x + T, text_start_y + H)
    fill_rect(cur_x + T, text_start_y + mid, cur_x + r_w, text_start_y + mid + T)
    cur_x += r_w + 4
    
    # 5. 'i'
    # dot
    fill_rect(cur_x + 1, text_start_y + mid - 6, cur_x + 1 + T, text_start_y + mid - 3)
    # vertical
    fill_rect(cur_x + 1, text_start_y + mid, cur_x + 1 + T, text_start_y + H)
    cur_x += 6 + 4
    
    # 6. 'e' (classic 7-seg lowercase e: a, b, g, e, d)
    e_w = 10
    # a (top)
    fill_rect(cur_x, text_start_y, cur_x + e_w, text_start_y + T)
    # b (upper-right)
    fill_rect(cur_x + e_w - T, text_start_y, cur_x + e_w, text_start_y + mid)
    # g (middle)
    fill_rect(cur_x, text_start_y + mid - T // 2, cur_x + e_w, text_start_y + mid + T // 2 + 1)
    # e (lower-left)
    fill_rect(cur_x, text_start_y + mid, cur_x + T, text_start_y + H)
    # d (bottom)
    fill_rect(cur_x, text_start_y + H - T, cur_x + e_w, text_start_y + H)
    cur_x += e_w + 4
    
    # 7. 'l' (uppercase L: f, e, d)
    l_w = 9
    fill_rect(cur_x, text_start_y, cur_x + T, text_start_y + H)
    fill_rect(cur_x + T, text_start_y + H - T, cur_x + l_w, text_start_y + H)


def save_palette_png(output_path: str, indices: bytearray):
    """
    Save 960x672 2-bit palette PNG with PLTE matching the badge's
    epd.py / large_png.py expectation.
    """
    W = SCREEN_WIDTH
    H = SCREEN_HEIGHT
    
    # PLTE chunk (White, Black, Red)
    plte_data = bytearray()
    for color in PALETTE:
        plte_data.extend(color)
        
    # IDAT chunk: 2-bit per pixel (4 pixels per byte)
    raw_idat = bytearray()
    for y in range(H):
        raw_idat.append(0)  # Filter byte: None
        row_offset = y * W
        for x in range(0, W, 4):
            b0 = indices[row_offset + x] & 3
            b1 = indices[row_offset + x + 1] & 3
            b2 = indices[row_offset + x + 2] & 3
            b3 = indices[row_offset + x + 3] & 3
            byte_val = (b0 << 6) | (b1 << 4) | (b2 << 2) | b3
            raw_idat.append(byte_val)
            
    compressed = zlib.compress(bytes(raw_idat), level=9)
    
    def make_chunk(chunk_type: bytes, chunk_data: bytes):
        length = len(chunk_data)
        crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        return struct.pack(">I", length) + chunk_type + chunk_data + struct.pack(">I", crc)

    # IHDR: width=960, height=672, bit_depth=2, color_type=3 (palette), comp=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", W, H, 2, 3, 0, 0, 0)
    
    with open(output_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(make_chunk(b"IHDR", ihdr_data))
        f.write(make_chunk(b"PLTE", plte_data))
        f.write(make_chunk(b"IDAT", compressed))
        f.write(make_chunk(b"IEND", b""))

    print(f"Successfully saved {output_path} ({os.path.getsize(output_path)} bytes)")


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    input_img = os.path.join(root_dir, "IMG_7958.JPG")
    output_png = os.path.join(root_dir, "firmware/badge/data/graphics/cat.png")
    
    print(f"Loading and scaling {input_img}...")
    canvas = load_scaled_photo(input_img)
    
    print("Applying Atkinson dithering to photo...")
    indices = dither_atkinson(canvas)
    
    print("Overlaying 7-segment 'murriel' in bottom-right...")
    render_7segment_overlay(indices, bottom_right_x=936, bottom_right_y=654)
    
    print(f"Writing palette PNG to {output_png}...")
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    save_palette_png(output_png, indices)


if __name__ == "__main__":
    main()
