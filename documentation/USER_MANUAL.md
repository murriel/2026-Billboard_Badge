# 2026 Hackaday Supercon Billboard Badge — User Manual

Welcome to the **Billboard Badge**! This badge features a recycled 9.7-inch three-color electronic paper (e-paper / EPD) screen from commercial department store shelf tags, powered by an ESP32-S3 microcontroller, eight addressable RGB LEDs, four navigation buttons, and three Simple Add-On (SAO) expansion ports.

---

## 1. Quick Start & Powering the Badge

### Power Options
* **USB-C Port**: Plug in a standard USB-C cable to any 5V USB charger, portable power bank, or computer. This powers the board and charges any connected LiPo battery.
* **LiPo / Li-Ion Battery**: Solder or connect a single-cell 3.7V Lithium-Polymer (LiPo) battery to the onboard battery pads (`TP1` / `TP2`). The board includes an onboard **MCP73831** charge controller.
* **Power Switch**: Slide the power switch on the back of the board to toggle between battery power and standby.

> [!NOTE]
> **E-Paper Persistence**: The 9.7-inch e-paper display is **bistable**. Once an image or schedule is drawn, it remains visible on the screen **indefinitely with zero power consumption**, even if you turn off the switch or unplug the badge!

---

## 2. Buttons & Navigation

The primary control buttons are located on the **back** of the badge along the edge.

```
       [ Top Edge of Badge ]
 _______________________________________
|                                       |
|  [SW4]       [SW5]      [SW6]   [SW7] |
| User A      Menu -     Menu +  User B |
|_______________________________________|
```

### Button Functions

| Button | Label / Switch | Default Function |
| :--- | :--- | :--- |
| **Menu +** | `SW6` (IO15) | Advances forward to the next menu item |
| **Menu -** | `SW5` (IO40) | Steps backward to the previous menu item |
| **User A** | `SW4` (IO39) | **Select / Launch** highlighted menu item & quick-launch **User Program A** |
| **User B** | `SW7` (IO16) | **Select / Launch** highlighted menu item & quick-launch **User Program B** |
| **BOOT** | `SW2` / `SW3` (IO0) | Microcontroller boot mode (used for flashing/recovery) |
| **RESET** | Reset switch | Hard hardware reset / restart |

> [!WARNING]
> **Silkscreen Errata Note**: On some hardware revisions, the **`+`** and **`-`** symbols on the rear silkscreen are swapped. If pressing `+` moves the selection to the left, use the physical switches as wired: `SW6` is **Menu +** and `SW5` is **Menu -**.

### Navigating the Menu
1. **Browse**: While on any screen, tap **Menu +** or **Menu -** to activate Menu Mode. The LED bar illuminates to indicate your current position.
2. **Cycle**: Keep tapping **Menu +** or **Menu -** to cycle through installed applications.
3. **Select / Launch**: Press **User A** or **User B** to confirm and load the selected application.
4. **Direct User Programs**: When you or another hacker install custom programs into the `User A` or `User B` slots, pressing those buttons directly triggers those custom routines.

---

## 3. LED Menu Indicators

The row of 8 addressable WS2812 RGB LEDs on the back of the board acts as your real-time status and menu selector:

```
  (1)       (2)       (3)       (4)       (5)      (6)   (7)   (8)
 [Load]   [Sat Sched] [Sun Sched] [Art]  [Name]   [ --- Open Slots --- ]
```

When cycling through the menu, the active item is highlighted by a bright white cursor over the page's color group:

| Position | Screen / Application | Description |
| :---: | :--- | :--- |
| **LED 1** (Leftmost) | **Load Screen** | Supercon-X splash screen and startup logo. |
| **LED 2** | **Saturday Agenda** | Talk schedule and stages for Saturday. |
| **LED 3** | **Sunday Agenda** | Talk schedule and stages for Sunday. |
| **LED 4** | **Art Gallery** | Cycles through artwork from Hackaday Art Director Joe Kim. |
| **LED 5** | **Name Badge** | Full-screen digital name and handle badge. |
| **LED 6** | **OpenBook E-Reader** | Full-screen book reader with 7 built-in public domain classics. |
| **LED 7 – 8** | *User Slots* | Reserved for your own custom apps and demos! |

### OpenBook E-Reader Controls
When inside the OpenBook app, a compact control footer is displayed at the bottom of the screen:
* **User A (`SW4`)**: Turn forward to the next page (automatically advances to the next chapter at the end of a chapter).
* **User B (`SW7`)**: Turn back to the previous page (automatically goes to the previous chapter at the start of a chapter).
* **BOOT (`SW2`/`SW3`)**: Cycle to the next book in your library (*Jane Eyre*, *Dracula*, *Dorian Gray*, *War of the Worlds*, etc.).
* **Menu + (`SW6`) / Menu - (`SW5`)**: Open the Badge App Switcher menu at any time to switch back to Nametag, Schedule, or Gallery.
* Reading bookmarks and current page positions are saved automatically per book.

### Status Colors During Refresh
* **Cyan (`(0, 1, 1)`)**: The badge is currently reading flash and rendering layout data into the internal framebuffer.
* **Flashing / Dark**: The display controller is running its high-voltage refresh cycle.
* **Green (`(0, 1, 0)`)**: Refresh cycle complete! Framebuffer latched.

---

## 4. Understanding the E-Paper Display (Slow Refresh Rate)

The display is a **9.7-inch Pervasive Displays E2969JS0B1** electronic paper panel (960 × 672 pixels) supporting three distinct pigments: **Black**, **White**, and **Red**.

### Why is the refresh slow?
Unlike LCD, OLED, or smartphone screens that update 60 times a second, 3-color e-paper physically moves micro-particles suspended in fluid using dual Chip-On-Glass (COG) driver chips:
1. Micro-capsules containing black, white, and red charged pigments are pulsed with high-voltage AC waveforms.
2. The screen flickers, inverts, and clears residual charge over several stages to prevent ghosting and ensure sharp contrast.
3. A full global refresh takes **approximately 15 to 20 seconds**.

### Best Practices:
* **Wait for the refresh to finish**: When you select a new screen or program, give the display 15–20 seconds to finish its drawing sequence before pressing additional buttons.
* **No backlight**: The display relies on ambient light. It looks best under conference room lighting or direct sunlight!
* **Zero battery drain while reading**: Once drawn, the screen does not use any battery power to maintain the image.

---

## 5. Customizing Your Digital Name Badge

Out of the box, the badge includes a **Nametag** app (LED position 5). You can customize it with your own name, callsign, and pronouns!

1. Connect the badge to your laptop with a USB-C data cable.
2. Open `firmware/badge/apps/nametag.py` on your computer.
3. Locate lines 51–60:
   ```python
   hello = lvgl.label(plate)
   hello.set_text("YOUR NAME")          # Enter your name here!
   hello.set_style_text_color(_BLACK, 0)
   hello.set_style_text_font(_FONT, 0)

   world = lvgl.label(plate)
   world.set_text("@your_handle")       # Enter your handle or pronouns
   world.set_style_text_color(_RED, 0)  # You can choose _RED or _BLACK!
   world.set_style_text_font(_FONT, 0)
   ```
4. Push the update to the badge using the update script (see [Developer Manual](file:///Users/neko/Projects/2026-Billboard_Badge/documentation/DEVELOPER_MANUAL.md)):
   ```bash
   python firmware/scripts/update.py push --reset
   ```

---

## 6. Hardware Expansion (SAO Headers & GPIO)

Want to add bling or custom hardware? The badge includes three standard **Simple Add-On (SAO)** connectors and exposed GPIO pins:

* **SAO 1**: GPIO 2 and GPIO 42
* **SAO 2**: GPIO 4 and GPIO 5
* **SAO 3**: GPIO 7 and GPIO 6
* **Shared I2C Bus**: SDA on GPIO 17, SCL on GPIO 18 (accessible on all SAO ports)
* **General Purpose GPIOs**: GPIO 9 and GPIO 41

Plug in any 3.3V I2C or GPIO-driven SAO badge add-on from Supercon to bring extra flair to your billboard!
