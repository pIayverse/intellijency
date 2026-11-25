# Intellijency

Control app for the Ajazz AK820 Max HE keyboard and your PC's RGB lighting.

Offline desktop app for the Ajazz AK820 Max HE magnetic (Hall-effect) keyboard, wired version
(USB `0C45:80B1`). Works without Ajazz's official driver or an internet connection.

## Run

```
python -m pip install PySide6 hidapi openrgb-python
python main.py
```

The **RGB Devices** and **General Lighting** tabs control lighting on anything
[OpenRGB](https://openrgb.org) supports: motherboards, graphics cards, coolers and fans, plus keyboards, mice and
headsets from brands such as Wooting, Razer, Corsair, Logitech and SteelSeries. OpenRGB must be running (its Windows
service starts it automatically). Settings beyond lighting (actuation, remapping, macros) are Ajazz AK820 Max HE only;
other brands keep using their own apps for those.

Close SignalRGB or any other RGB app first; only one program can talk to the keyboard at a time.

## What it can do

- **Lighting:** 19 effects, colour, rainbow mode, brightness and speed. The app's keyboard view
  shows the lighting it last applied.
- **Switches & System:** actuation point, Rapid Trigger (down to 0.01 mm in Jeweler Mode),
  dead zones, polling rate up to 8000 Hz, and key calibration.
- **Rappy Snappy & SOCD**, **Key Remapping** (Normal/Fn layers, Mod-Tap, Toggle),
  **Macros** and **Dynamic Keystroke (DKS)**.
- **Profiles:** save and load complete setups.

**Factory Reset** puts every keyboard setting back to factory defaults.

## Command-line tools

`ajazz.py` and `ajazz_calib.py` do the same jobs from a terminal; run either with `--help`.

## Credits

Based on the open-source project by chudoyoodo (MIT licence, see `LICENSE`), with Windows fixes,
an English-only interface and a new look.
