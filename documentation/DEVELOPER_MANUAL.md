# 2026 Hackaday Supercon Billboard Badge — Developer Manual

This manual provides complete documentation for developing software on the **2026 Billboard Badge**. It covers everything from writing Python user applications and customizing graphic assets to flashing core binaries and compiling firmware from source.

---

## 1. System Architecture Overview

* **Microcontroller**: ESP32-S3 (Dual-core Xtensa LX7 @ 240 MHz, Octal SPIRAM, 8MB/16MB Flash).
* **Firmware Runtime**: Custom **MicroPython 1.27** compiled with integrated **LVGL 9.x** (Light and Versatile Graphics Library).
* **Display**: 9.7-inch Pervasive Displays E2969JS0B1 3-Color (Black/White/Red) E-Paper Display (960 × 672 resolution).
* **LEDs**: 8-pixel WS2812 NeoPixel strip on GPIO 38.
* **Buttons**:
  * `Menu -`: GPIO 40 (`SW5`)
  * `Menu +`: GPIO 15 (`SW6`)
  * `User A`: GPIO 39 (`SW4`)
  * `User B`: GPIO 16 (`SW7`)
  * `Boot`: GPIO 0 (`SW2` / `SW3`)
* **Filesystem Structure on the Badge**:
  * `/boot.py`: System startup script.
  * `/main.py`: Initializes hardware tasks (buttons, LEDs, display engine, app switcher).
  * `/apps/`: Application directory. Modules placed here are automatically discovered.
  * `/data/`: Graphics (`/data/graphics/`), schedule data (`/data/schedule.csv`), artwork (`/data/gallery/`), and configs.
  * `/lib/`: Badge hardware drivers (`epd.py`, `led_bar.py`, `button.py`, `app_switcher.py`).

---

## 2. Development Setup & Connecting to the Badge

### Prerequisites
Install the required tools on your host machine (Linux, macOS, or Windows):
```bash
# Python 3 and device communication tools
pip install --upgrade esptool mpremote

# ImageMagick (required for dithering images to the 3-color palette)
# macOS:
brew install imagemagick
# Ubuntu / Debian:
sudo apt install imagemagick
```

### Physical Connection
1. Connect the badge to your computer using a high-quality **USB-C data cable**.
2. Identify the serial port created by the ESP32-S3:
   * **Linux**: `/dev/ttyACM0` or `/dev/ttyUSB0`
   * **macOS**: `/dev/cu.usbmodem*` (e.g. `/dev/cu.usbmodem1101`)
   * **Windows**: `COM3`, `COM4`, etc. (visible in Device Manager under Ports)

### Opening the MicroPython REPL
You can immediately interact with Python on the badge using `mpremote`:
```bash
# Automatically detects connected badge and enters interactive REPL
mpremote repl
```
Or specify the port explicitly:
```bash
mpremote connect /dev/ttyACM0 repl
```
* Press `Ctrl+C` to interrupt the running main loop.
* Press `Ctrl+D` to perform a soft reset.
* Type `help()` or import libraries directly to experiment live!

---

## 3. Synchronizing Code & Files (`update.py`)

The repository includes a helper script (`firmware/scripts/update.py`) that syncs local files from `firmware/badge/` to the badge using `mpremote`.

Run all commands from the `firmware/` directory:

### Check Status & File Diffs
```bash
cd firmware
python scripts/update.py ls
```
Status indicators:
* ` ` (Blank): File is synchronized and matches checksum.
* `*`: File differs between local copy and badge.
* `+`: File exists only locally (will be added on push).
* `-`: File exists on the badge but not locally (will be deleted on push).

### Push Files to Badge
Push all updated scripts and new assets to the badge:
```bash
python scripts/update.py push
```
To push and immediately soft-reboot the badge into the new code:
```bash
python scripts/update.py push --reset
```

### Pull Files from Badge
To backup or extract files currently stored on the badge into `firmware/badge-backup/`:
```bash
python scripts/update.py pull
```

---

## 4. Writing a User Application

Adding a new app to the badge is easy: any class subclassing `BaseApp` placed in `firmware/badge/apps/` is automatically registered by `app_switcher.py` at boot!

### App Lifecycle (`BaseApp`)
Each app inherits from `apps.base_app.BaseApp`:
* `self.name`: Name displayed in logs and the menu database.
* `self.sleep_ms`: Delay in milliseconds between execution cycles (default: 100 ms).
* `self.launched`: Set to `True` on the first iteration after an app is selected. Use this flag to draw your initial screen.
* `run(self)`: Synchronous method executed continuously in a loop while your app is active.
* `async arun(self)`: Optional asynchronous coroutine if you require fine-grained async tasks.

### Template Application
Create a new file, e.g. `firmware/badge/apps/my_demo.py`:

```python
"""Custom User Application Example"""

import lvgl
from apps.base_app import BaseApp
from lib.button import MenuMinus, MenuPlus, UserA, UserB, Boot
from lib.epd import display, display_width, display_height
from lib.led_bar import leds

class MyDemoApp(BaseApp):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name or "My Demo")
        self.sleep_ms = 100
        self.launched = False

    def draw_screen(self):
        # Indicate display draw in progress on the LED bar
        leds.fill((0, 1, 1))

        # Clear display buffers (sets to pure white)
        display.clear()

        # You can display a pre-rendered 3-color PNG
        # display.draw_png("/data/graphics/my_graphic.png")

        # Or create an LVGL layout
        scr = lvgl.obj()
        scr.remove_style_all()
        scr.set_size(display_width, display_height)
        scr.set_style_bg_color(lvgl.color_hex(0xFFFFFF), 0)
        scr.set_style_bg_opa(lvgl.OPA.COVER, 0)

        label = lvgl.label(scr)
        label.set_text("Hello Hackaday Supercon!")
        label.set_style_text_color(lvgl.color_hex(0x000000), 0)
        label.set_style_text_font(lvgl.font_montserrat_48, 0)
        label.align(lvgl.ALIGN.CENTER, 0, 0)

        lvgl.screen_load(scr)
        scr.update_layout()
        lvgl.refr_now(display.lv_display)

        # Trigger the physical E-Paper refresh (~15-20s)
        display.update()

        # Mark refresh as finished
        leds.fill((0, 1, 0))

    def run(self):
        # Setup on first launch
        if self.launched:
            print(f"Launching {self.name}...")
            self.draw_screen()
        else:
            # Handle in-app button presses
            if UserA.pressed():
                print("User A button pressed!")
                leds.fill((2, 0, 0)) # Red blink

            if UserB.pressed():
                print("User B button pressed!")
                leds.fill((0, 0, 2)) # Blue blink
```

### Wiring Up User Program A & B Shortcuts
To make your app directly accessible via the **User A** or **User B** hardware buttons:
1. Create `firmware/badge/apps/user_app_a.py` and/or `firmware/badge/apps/user_app_b.py`.
2. Implement your app logic subclassing `BaseApp`.
3. In `lib/app_switcher.py`, the switcher provides direct access to these programs: pressing `User A` or `User B` launches the corresponding user slot program.

---

## 5. Working with Badge Hardware APIs

### Buttons (Direct `machine.Pin` & `lib.button`)

#### Direct MicroPython Convention (Workshop / REPL):
```python
from machine import Pin

# Buttons use internal pull-up resistors (active LOW: 0 = pressed, 1 = released)
menu_minus = Pin(40, Pin.IN, Pin.PULL_UP)  # SW5
menu_plus  = Pin(15, Pin.IN, Pin.PULL_UP)  # SW6
user_a     = Pin(39, Pin.IN, Pin.PULL_UP)  # SW4
user_b     = Pin(16, Pin.IN, Pin.PULL_UP)  # SW7
boot       = Pin(0, Pin.IN, Pin.PULL_UP)   # SW2/SW3

if user_a.value() == 0:
    print("User A button is pressed!")
```

#### Managed App Library (`lib.button`):
Inside application loops, `lib.button` handles state tracking and debouncing:
```python
from lib.button import MenuMinus, MenuPlus, UserA, UserB, Boot

# Check if pressed (only returns True once per click)
if UserA.pressed():
    ...

# Check press duration (in milliseconds)
hold_time = UserA.pressed_ms()

# Raw active state (True if held down)
is_held = UserA.value
```

### LED Bar (Direct `neopixel` & `lib.led_bar`)

You can control the 8 WS2812 RGB LEDs either directly using standard MicroPython (`neopixel` on GPIO 38) as demonstrated in the workshop labs, or via the `lib.led_bar` convenience library:

#### Direct MicroPython Convention (Workshop / REPL):
```python
from machine import Pin
import neopixel

# Initialize the 8-LED bar on GPIO 38
np = neopixel.NeoPixel(Pin(38), 8)

# Update individual LEDs using (R, G, B) tuples (0-255)
np[0] = (32, 0, 0)   # LED 1: Red
np[2] = (0, 32, 0)   # LED 3: Green
np[7] = (0, 0, 32)   # LED 8: Blue

# Push buffered colors out to the physical LEDs
np.write()
```

#### Managed App Library (`lib.led_bar`):
The `leds` singleton provides high-level helpers and async animation sequencers:
```python
from lib.led_bar import leds

# Fill all LEDs with an (R, G, B) tuple (values 0-255; keep <= 10 for comfort!)
leds.fill((2, 1, 0))

# Set an individual LED
leds[0] = (3, 0, 0)  # Set first LED to red
leds.write()

# Run an animated generator sequence
def rainbow_sparkle():
    while True:
        frame = [[i * 2, 0, 4] for i in range(8)]
        yield frame, 100.0  # (LED buffer, delay in ms)

leds.set_sequence(rainbow_sparkle)

# Stop the sequence
leds.clear_sequence()
```

### E-Paper Display (`lib.epd`)
* **Resolution**: `display_width = 960`, `display_height = 672`
* **Color Channels**: Internal framebuffers for `black` and `red`.
```python
from lib.epd import display

display.clear()
display.draw_png("/data/graphics/my_image.png", row=0, col=0)
display.update()  # Queues the global refresh task
```

---

## 6. Graphic Asset Conversion (3-Color Dithering)

The e-paper panel only renders **White**, **Black**, and **Red**. Loading raw 24-bit RGB or large uncompressed images will exhaust ESP32 memory and distort colors.

Images must be reduced to 960 × 672 (or smaller) and dithered to the 3-color palette:

### Color Logic Threshold
* **Red**: Red > 50% and (Green < 50% and Blue < 50%)
* **Black**: Red < 50% and Green < 50% and Blue < 50%
* **White**: All other values

### Converting with ImageMagick
Use the project palette file (`firmware/scripts/palette.gif`):
```bash
magick input.png -remap firmware/scripts/palette.gif output.png
```

To automatically convert and copy all graphics from `assets/graphics/` into `firmware/badge/data/graphics/`:
```bash
python firmware/scripts/copy_assets.py
```

---

## 7. Flashing Core Firmware Binaries

If you need to restore a badge, upgrade MicroPython, or unbrick a device, flash the pre-compiled binary images located in `firmware/bin/`.

### Binary Layout
* `0x00000`: `firmware/bin/bootloader.bin`
* `0x08000`: `firmware/bin/partition-table.bin`
* `0x10000`: `firmware/bin/micropython.bin`
* Full 8MB flash dump: `firmware/bin/supercon26_factory.bin`

### Step 1: Enter ROM Bootloader Mode
1. Connect the badge via USB-C to your computer.
2. Press and hold down the **BOOT** button (`SW2` / `SW3` / IO0).
3. Press and release the **RESET** button.
4. Release the **BOOT** button.
The ESP32-S3 is now in ROM download mode.

### Step 2: Flash Binaries via `esptool.py`
Run the flash command from `firmware/`:
```bash
python -m esptool --chip esp32s3 -b 460800 \
    --before default_reset --after hard_reset write_flash \
    --flash_mode dio --flash_size 8MB --flash_freq 80m \
    0x0 bin/bootloader.bin \
    0x8000 bin/partition-table.bin \
    0x10000 bin/micropython.bin
```

Alternatively, to restore the entire 8MB factory image in one command:
```bash
python -m esptool --chip esp32s3 -b 460800 write_flash 0x0 bin/supercon26_factory.bin
```

---

## 8. Compiling Firmware from Source (Advanced)

For developers who want to add C modules, customize LVGL bindings, or rebuild the MicroPython core:

1. **Install ESP-IDF v5.x**:
   Follow the [Espressif ESP-IDF Installation Guide](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/get-started/):
   ```bash
   cd ~/esp/esp-idf
   ./install.sh esp32s3
   . ./export.sh
   ```

2. **Sync `lv_micropython`**:
   Clone `lv_micropython` and recursively initialize its submodules:
   ```bash
   git clone --recursive https://github.com/lvgl/lv_micropython.git
   ```

3. **Apply Badge Patches**:
   * Copy the board and driver files from `firmware/lv_files/` to their corresponding paths inside `lv_micropython/`.
   * In `lv_micropython/lib/lv_conf.h`, ensure LODEPNG is disabled:
     ```c
     #define LV_USE_LODEPNG 0
     ```

4. **Build the Custom Firmware**:
   ```bash
   cd lv_micropython/ports/esp32
   make BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=BILLBOARD_BADGE
   ```

5. **Flash the Newly Compiled Firmware**:
   ```bash
   python -m esptool --chip esp32s3 -b 460800 \
       --before default_reset --after hard_reset write_flash \
       --flash_mode dio --flash_size 16MB --flash_freq 80m \
       0x0 build-ESP32_GENERIC_S3-BILLBOARD_BADGE/bootloader/bootloader.bin \
       0x8000 build-ESP32_GENERIC_S3-BILLBOARD_BADGE/partition_table/partition-table.bin \
       0x10000 build-ESP32_GENERIC_S3-BILLBOARD_BADGE/micropython.bin
   ```

---

## 9. Sharing Your App

Built something cool? Submit it back to the community!
1. Create a directory under `user_apps/<your_app_name>/`.
2. Include your Python source files, assets, and a `README.md` describing your app.
3. Open a Pull Request on GitHub against the `main` branch.
