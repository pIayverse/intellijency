"""Demo mode (`--demo`): simulated devices and a throwaway settings folder.

Used for screenshots, the trailer and trying the app without hardware. Nothing reaches a real keyboard, OpenRGB,
the registry or the user's settings. Call prepare() before importing ajazz_app.gui, then install().
"""
import json
import os

ENABLED = False

try:
    from openrgb.utils import RGBColor
except ImportError:  # demo still works without the library
    class RGBColor:
        def __init__(self, red, green, blue):
            self.red, self.green, self.blue = red, green, blue

# Generic names on purpose: the demo shows device kinds, not real products.
DEVICES = [
    ("AIO Liquid Cooler 240", "COOLER", ["Direct", "Static", "Breathing", "Spectrum Cycle"]),
    ("Graphics Card", "GPU", ["Direct", "Static", "Color Cycle", "Off"]),
    ("Motherboard", "MOTHERBOARD", ["Direct", "Static", "Spectrum Cycle", "Off"]),
    ("Case Fans ×3", "LEDSTRIP", ["Direct", "Static", "Rainbow"]),
    ("RGB Memory", "DRAM", ["Direct", "Static", "Rainbow"]),
    ("Gaming Mouse", "MOUSE", ["Direct", "Static", "Spectrum Cycle", "Off"]),
    ("RGB Mousepad", "MOUSEMAT", ["Direct", "Static", "Rainbow"]),
    ("Gaming Headset", "HEADSET", ["Direct", "Static", "Spectrum Cycle"]),
]


class _Named:
    def __init__(self, name):
        self.name = name


class _Mode(_Named):
    colors = None


class FakeDevice:
    def __init__(self, idx, name, kind, modes):
        self.id, self.name, self.type = idx, name, _Named(kind)
        self.modes = [_Mode(m) for m in modes]
        self.active_mode = 0
        self.colors = [RGBColor(124, 92, 255)] * 4
        self.leds, self.zones = [0] * 4, [0]

    def set_mode(self, name):
        for i, m in enumerate(self.modes):
            if m.name.lower() == str(name).lower():
                self.active_mode = i

    def set_color(self, color, fast=False):
        self.colors = [color] * len(self.colors)


class FakeClient:
    """Stands in for openrgb.OpenRGBClient; the same device objects survive reconnects."""
    _devices = None

    def __init__(self, *args, **kwargs):
        if FakeClient._devices is None:
            FakeClient._devices = [FakeDevice(i, n, k, m) for i, (n, k, m) in enumerate(DEVICES)]
        self.devices = FakeClient._devices

    def update(self):
        pass

    def disconnect(self):
        pass


def prepare(home: str):
    """Point every settings path at `home` (must run before ajazz_app modules are imported) and seed it."""
    global ENABLED
    ENABLED = True
    os.environ["USERPROFILE"] = home
    os.environ["HOME"] = home
    cfg = os.path.join(home, ".config", "ajazz_studio")
    os.makedirs(cfg, exist_ok=True)
    seeds = {
        "kb_rainbow.json": {"speed": 3, "period": 7.18, "first_red": 5.17, "direction": -1},
        "general_lighting.json": {"effect": "Synced Rainbow", "colour": "#7c5cff", "colour2": "#2fb8ff",
                                  "speed": "Medium", "skip": []},
        "last_state.json": {"state": {"light": {"mode": 8, "r": 124, "g": 92, "b": 255, "rainbow": 1,
                                                "brightness": 5, "speed": 3, "direction": 0}}, "extra": {}},
    }
    for name, data in seeds.items():
        path = os.path.join(cfg, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)


def install():
    """Swap hardware access for simulations."""
    from . import core, pc_rgb, startup
    core.AjazzController.is_connected = lambda self: True
    core.AjazzController.send_packets = lambda self, packets, delay=0.01: True
    core.AjazzController.open_telemetry = lambda self: None
    pc_rgb.OpenRGBClient = FakeClient
    startup.is_enabled = lambda: False
    startup.set_enabled = lambda on: None
