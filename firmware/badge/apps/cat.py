"""Cat Display App for Billboard Badge"""

from apps.base_app import BaseApp
from lib.epd import display
from lib.led_bar import leds
import gc
import time


class CatApp(BaseApp):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name or "Cat")
        self.sleep_ms = 200
        self.launched = False

    def render(self):
        print("Rendering Cat (Murriel)...")
        # Visual feedback on LED bar during draw
        leds.fill((0, 2, 2))
        gc.collect()
        display.clear()
        display.draw_png("/data/graphics/cat.png", row=0, col=0)
        display.update()
        leds.fill((0, 2, 0))
        gc.collect()

    def run(self):
        if self.launched:
            self.render()
