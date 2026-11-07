"""App Switcher"""

import asyncio as aio  # type: ignore
import os
import sys
import btree

from apps.base_app import BaseApp
from lib.button import MenuMinus, MenuPlus, UserA, UserB, PRESSED_READ
from lib.led_bar import leds

# MENU_TIMEOUT_MILLISECONDS = 1000


APPMOD_DENYLIST = {
    "__init__",
    "base_app",
    "template",
}


class AppSwitcher:
    def __init__(self, initial_idx: int = 0) -> None:
        self.apps = []
        self.active_idx = initial_idx
        self.selecting_mode = True
        self.selection_idx = initial_idx

        # Discover and safely load apps from both /apps and /user_apps
        search_paths = [("/apps", "apps"), ("/user_apps", "user_apps")]
        for folder, pkg in search_paths:
            try:
                for filename, _, _, _ in os.ilistdir(folder):
                    if not filename.endswith(".py") or filename.startswith("_"):
                        continue
                    app_modname = filename[:-3]
                    if app_modname in APPMOD_DENYLIST:
                        continue
                    try:
                        print(f"Loading {pkg}.{app_modname}...")
                        mod = __import__(f"{pkg}.{app_modname}", None, None, [app_modname])
                        for modattr in mod.__dict__.values():
                            # Subclasses of an app class count too. _abstract skips the
                            # shared base so only the concrete apps are constructed.
                            if not isinstance(modattr, type) or not issubclass(modattr, BaseApp):
                                continue
                            if modattr is BaseApp or modattr.__dict__.get("_abstract"):
                                continue
                            app = modattr()
                            self.apps.append(app)
                            print(f"Added app: {app.name} (from {pkg})")
                    except Exception as exc:
                        print(f"Failed to load app '{app_modname}' from {pkg}:")
                        sys.print_exception(exc)
            except OSError:
                pass

        try:
            apps_file = open("/data/app_list", "r+b")
        except OSError:
            apps_file = open("/data/app_list", "w+b")
        # Now open database itself
        try:
            apps_db = btree.open(apps_file)
            for idx, app in enumerate(self.apps):
                apps_db[bytes([idx])] = bytes(app.name, "UTF-8")
            apps_db.flush()
            apps_db.close()
        except Exception as exc:
            print(f"Failed updating app_list database: {exc}")
        finally:
            try:
                apps_file.close()
            except Exception:
                pass


    async def arun(self):
        while True:
            if self.selecting_mode:
               
                ## Display current app from all installed apps
                leds.menu_display(self.selection_idx, len(self.apps))

                if MenuPlus.pressed():
                    self.selection_idx = (self.selection_idx + 1) % len(self.apps)
                    print(
                        f"Selected app {self.selection_idx}: {self.apps[self.selection_idx].name}"
                    )
                if MenuMinus.pressed():
                    self.selection_idx = (self.selection_idx - 1) % len(self.apps)
                    print(
                        f"Selected app {self.selection_idx}: {self.apps[self.selection_idx].name}"
                    )
                if UserA.pressed() or UserB.pressed():
                    print(f"Switching to {self.apps[self.selection_idx].name}")
                    self.active_idx = self.selection_idx
                    self.apps[self.active_idx].launched = True
                    leds.clear_sequence()
                    leds.fill((0, 0, 0))
                    leds.write()
                    self.selecting_mode = False
                await aio.sleep_ms(10)
            else:
                if MenuMinus.pressed() or MenuPlus.pressed():
                    self.selection_idx = self.active_idx
                    self.selecting_mode = True
                    ## Reset pressed state so that button doesn't advance menu, just enters menu state
                    MenuMinus._pressed_state = PRESSED_READ
                    MenuPlus._pressed_state = PRESSED_READ
                    print("Activated app switching")
                await self.apps[self.active_idx].arun()
                await aio.sleep_ms(0)
                self.apps[self.active_idx].launched = False


switcher = AppSwitcher()
