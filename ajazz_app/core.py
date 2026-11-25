import os
import json
import time
import hid

VENDOR_ID = 0x0c45
PRODUCT_ID = 0x80b1

EFFECTS = {
    "Off": 0x00, "Static Brightness": 0x01, "Single Point On": 0x02,
    "Single Point Off": 0x03, "Starry Sky": 0x04, "Snowfall": 0x05,
    "Floral": 0x06, "Dynamic": 0x07, "Spectrum Cycle": 0x08,
    "Color Follow": 0x09, "Colorful": 0x0a, "Flowing": 0x0b,
    "Turning": 0x0c, "One Touch": 0x0d, "Two Birds": 0x0e,
    "Ripples": 0x0f, "Endless": 0x10, "Layered": 0x11,
    "Gentle": 0x12, "Back and Forth": 0x13,
}

OFFSETS_18 = [
    (0x00, 0x00), (0x38, 0x00), (0x70, 0x00), (0xa8, 0x00), (0xe0, 0x00),
    (0x18, 0x01), (0x50, 0x01), (0x88, 0x01), (0xc0, 0x01), (0xf8, 0x01),
    (0x30, 0x02), (0x68, 0x02), (0xa0, 0x02), (0xd8, 0x02), (0x10, 0x03),
    (0x48, 0x03), (0x80, 0x03), (0xb8, 0x03)
]

class AjazzController:
    def __init__(self):
        self.state = {
            "light": {"mode": 0x08, "r": 255, "g": 0, "b": 0, "rainbow": 1, "brightness": 5, "speed": 3, "direction": 0},
            "switch": {"axle": 0x01, "trigger": 1.50, "press": 0.30, "release": 0.20, "ft": 0, "full": 0},
            "settings": {"rate": 0x06, "stability": 1, "adaptive": 1, "dz_enable": 1, "dz_top": 0.30, "dz_bottom": 0.30},
            "adv": {"mode": "none", "slot1": 49, "hid1": 0x04, "slot2": 51, "hid2": 0x07, "pattern": 0x04, "trigger": 1.50, "press": 0.25, "release": 0.25, "full": 1}
        }

    def is_connected(self) -> bool:
        try:
            return len(hid.enumerate(VENDOR_ID, PRODUCT_ID)) > 0
        except Exception:
            return False

    def send_packets(self, packets, delay=0.01) -> bool:
        devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
        if not devices:
            print("[HID] Device not found")
            return False
        # Only use the vendor control interfaces (skip the normal keyboard and media-key interfaces)
        targets = [d for d in devices if d.get("usage_page", 0) >= 0xff00]
        if not targets:
            targets = [d for d in devices if d.get("interface_number", 0) == 2]
        if not targets:
            targets = devices
        sent_any = False
        for d in targets:
            dev = None
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                dev.set_nonblocking(1)
                for pkt in packets:
                    full = pkt + [0x00] * (64 - len(pkt))
                    res = dev.write([0x00] + full[:64])
                    if res < 0:
                        raise IOError("HID write failed")
                    if delay > 0:
                        time.sleep(delay)
                sent_any = True
            except Exception as e:
                print(f"[HID] Skipping interface {d.get('path')}: {e}")
            finally:
                if dev:
                    try:
                        dev.close()
                    except Exception:
                        pass
        return sent_any

    def apply_light(self, mode=None, r=None, g=None, b=None, rainbow=None, brightness=None, speed=None, direction=None):
        st = self.state["light"]
        if mode is not None: st["mode"] = mode
        if r is not None: st["r"] = r
        if g is not None: st["g"] = g
        if b is not None: st["b"] = b
        if rainbow is not None: st["rainbow"] = rainbow
        if brightness is not None: st["brightness"] = brightness
        if speed is not None: st["speed"] = speed
        if direction is not None: st["direction"] = direction
        pkt = [
            0xaa, 0x23, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00,
            st["mode"], st["r"], st["g"], st["b"], 0xff,
            0x00, 0x00, 0x00, st["rainbow"], st["brightness"], st["speed"], st["direction"], 0x00, 0x00,
            0xaa, 0x55
        ]
        return self.send_packets([pkt], delay=0)

    def apply_settings(self, rate=None, stability=None, adaptive=None, dz_enable=None, dz_top=None, dz_bottom=None):
        st = self.state["settings"]
        if rate is not None: st["rate"] = rate
        if stability is not None: st["stability"] = stability
        if adaptive is not None: st["adaptive"] = adaptive
        if dz_enable is not None: st["dz_enable"] = dz_enable
        if dz_top is not None: st["dz_top"] = dz_top
        if dz_bottom is not None: st["dz_bottom"] = dz_bottom
        top_val = int(round(st["dz_top"] * 100)) & 0xff
        bot_val = int(round(st["dz_bottom"] * 100)) & 0xff
        pkt = [
            0xaa, 0x21, 0x38, 0x00, 0x00, 0x00, st["stability"], 0x00,
            0x00, 0x00, 0x00, 0x05, 0x00, st["rate"], 0x00, 0x00,
            top_val, bot_val, 0x00, st["dz_enable"], 0x00, 0x00, st["adaptive"]
        ]
        return self.send_packets([pkt], delay=0)

    def apply_switches_and_adv(self):
        sw = self.state["switch"]
        adv = self.state["adv"]
        t_val = int(round(sw["trigger"] * 100))
        p_val = int(round(sw["press"] * 100)) if sw["ft"] else 0
        r_val = int(round(sw["release"] * 100)) if sw["ft"] else 0
        full_flag = 0x01 if (sw["ft"] and sw["full"]) else 0x00

        base_block = [
            sw.get("axle", 0x01), full_flag, t_val & 0xff, (t_val >> 8) & 0xff,
            p_val & 0xff, (p_val >> 8) & 0xff, r_val & 0xff, (r_val >> 8) & 0xff
        ]
        sw_table = [list(base_block) for _ in range(126)]
        key_table = [0x00] * 512

        if adv["mode"] in ("rs", "socd"):
            at = int(round(adv["trigger"] * 100))
            ap = int(round(adv["press"] * 100)) if adv["mode"] == "socd" else 0
            ar = int(round(adv["release"] * 100)) if adv["mode"] == "socd" else 0
            af = 0x01 if (adv["mode"] == "socd" and adv["full"]) else 0x00
            adv_block = [0x00, af, at & 0xff, (at >> 8) & 0xff, ap & 0xff, (ap >> 8) & 0xff, ar & 0xff, (ar >> 8) & 0xff]
            sw_table[adv["slot1"]] = adv_block
            sw_table[adv["slot2"]] = adv_block
            m_code = 0x0c if adv["mode"] == "rs" else 0x0b
            m_param = 0x00 if adv["mode"] == "rs" else adv["pattern"]
            desc = [m_code, m_param, adv["hid1"], adv["hid2"]]
            key_table[adv["slot1"]*4:adv["slot1"]*4+4] = desc
            key_table[adv["slot2"]*4:adv["slot2"]*4+4] = desc

        packets = [[0xaa, 0x27, 0x10, 0xf0, 0x03, 0x00, 0x01, 0x00]]
        for i, (off_l, off_h) in enumerate(OFFSETS_18):
            chunk = [b for s in sw_table[i*7:(i+1)*7] for b in s]
            packets.append([0xaa, 0x27, 0x38, off_l, off_h, 0x00, 0x00, 0x00] + chunk)

        for i in range(9):
            off = i * 0x38
            packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
        packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
        return self.send_packets(packets, delay=0.01)

    def apply_dks(self, slot: int, enable: bool, depths: list, keys: list, masks: list):
        dks_table = [0x00] * 1024
        if enable:
            dks_table[0:4] = [int(round(d * 10)) & 0xff for d in depths[:4]]
            dks_table[4:8] = [k & 0xff for k in keys[:4]]
            dks_table[8:16] = [masks[0], 0x00, masks[1], 0x00, masks[2], 0x00, masks[3], 0x00]
        packets = [[0xaa, 0x28, 0x38, off_l, off_h, 0x00, 0x00, 0x00] + dks_table[i*56:(i+1)*56] for i, (off_l, off_h) in enumerate(OFFSETS_18)]
        packets.append([0xaa, 0x28, 0x10, 0xf0, 0x03, 0x00, 0x01, 0x00] + dks_table[1008:1024])
        key_table = [0x00] * 512
        if enable:
            key_table[slot*4:slot*4+4] = [0x08, 0x00, 0x00, 0x00]
        for i in range(9):
            off = i * 0x38
            packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
        packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
        return self.send_packets(packets, delay=0.01)

    def apply_custom_layer(self, layer: str, entries: dict):
        layer_cmd = 0x26 if layer == "fn" else 0x22
        table = [0x00] * 512
        for slot, cfg in entries.items():
            idx = int(slot) * 4
            mode, k1, k2, param = cfg["mode"], cfg["k1"], cfg["k2"], cfg.get("param", 0)
            if mode == "key" and k1 > 0:
                table[idx:idx+4] = [0x02, param, k1 & 0xff, 0x00]
            elif mode == "mt":
                t_val = max(1, min(255, int(round(param / 10))))
                table[idx:idx+4] = [0x09, k1 & 0xff, k2 & 0xff, t_val]
            elif mode == "tgl":
                table[idx:idx+4] = [0x0a, k1 & 0xff, 0x00, 0x00]
        packets = []
        for i in range(9):
            off = i * 0x38
            packets.append([0xaa, layer_cmd, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + table[i*56:(i+1)*56])
        packets.append([0xaa, layer_cmd, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + table[504:512])
        return self.send_packets(packets, delay=0.01)

    def apply_macro(self, slot: int, steps: list):
        events = []
        for hid_code, is_down, delay_ms in steps:
            flag = 0xb0 if is_down else 0x30
            d = max(0, min(65535, int(delay_ms)))
            events.extend([d & 0xff, (d >> 8) & 0xff, hid_code & 0xff, flag])

        body = [len(events) // 2, 0x00, 0x00, 0x00] + events
        packets = [[0xaa, 0x25, 0x38, 0x00, 0x00, 0x00, 0x00, 0x00, 0x90, 0x01]]
        for off in [0x38, 0x70, 0xa8, 0xe0, 0x18, 0x50]:
            off_h = 0x01 if off in [0x18, 0x50] else 0x00
            packets.append([0xaa, 0x25, 0x38, off, off_h, 0x00, 0x00, 0x00])
        packets.append([0xaa, 0x25, 0x08, 0x88, 0x01, 0x00, 0x00, 0x00])
        packets.append([0xaa, 0x25, len(body) & 0xff, 0x90, 0x01, 0x00, 0x01, 0x00] + body)

        key_table = [0x00] * 512
        key_table[slot*4:slot*4+4] = [0x06, 0x00, 0x00, 0x00]
        for i in range(9):
            off = i * 0x38
            packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
        packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
        return self.send_packets(packets, delay=0.01)

    def factory_reset(self) -> bool:
        self.state = {
            "light": {"mode": 0x08, "r": 255, "g": 0, "b": 0, "rainbow": 1, "brightness": 5, "speed": 3, "direction": 0},
            "switch": {"axle": 0x01, "trigger": 1.50, "press": 0.30, "release": 0.20, "ft": 0, "full": 0},
            "settings": {"rate": 0x06, "stability": 1, "adaptive": 1, "dz_enable": 1, "dz_top": 0.30, "dz_bottom": 0.30},
            "adv": {"mode": "none", "slot1": 49, "hid1": 0x04, "slot2": 51, "hid2": 0x07, "pattern": 0x04, "trigger": 1.50, "press": 0.25, "release": 0.25, "full": 1}
        }
        ok = self.send_packets([[0xaa, 0x0f, 0xff]], delay=0.2)
        time.sleep(0.5)
        for _ in range(20):
            if self.is_connected():
                break
            time.sleep(0.2)
        return ok

    def start_calibration(self, clear=False):
        if not self.send_packets([[0xaa, 0x64]], delay=0.2): return False
        if clear: self.send_packets([[0xaa, 0x0f, 0x05]], delay=0.2)
        return True

    def finish_calibration(self):
        return self.send_packets([[0xaa, 0x65]], delay=0)

    def _state_path(self):
        d = os.path.expanduser("~/.config/ajazz_studio")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "last_state.json")

    def save_last_state(self, extra: dict = None):
        data = {"state": self.state, "extra": extra or {}}
        with open(self._state_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_last_state(self) -> dict:
        path = self._state_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "state" in data:
                self.state.update(data["state"])
            return data.get("extra", {})
        except Exception:
            return {}

    def clear_last_state(self):
        path = self._state_path()
        if os.path.exists(path):
            os.remove(path)

    def save_profile(self, path):
        with open(path, "w", encoding="utf-8") as f: json.dump(self.state, f, indent=2)

    def load_profile(self, path):
        with open(path, "r", encoding="utf-8") as f: self.state = json.load(f)
        self.apply_light()
        self.apply_settings()
        self.apply_switches_and_adv()

    def open_telemetry(self):
        self._telem_dev = None
        for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
            if d.get("interface_number") == 2 or d.get("usage_page", 0) >= 0xff00:
                try:
                    dev = hid.device()
                    dev.open_path(d["path"])
                    dev.set_nonblocking(True)
                    self._telem_dev = dev
                    break
                except Exception:
                    pass

    def poll_calibration_slots(self) -> set:
        done = set()
        if not getattr(self, "_telem_dev", None):
            return done
        while True:
            try:
                data = self._telem_dev.read(64)
            except Exception:
                break
            if not data:
                break
            if len(data) >= 10 and data[0] == 0x55 and data[1] == 0xfb:
                slot = data[2]
                top_adc = data[4] | (data[5] << 8)
                cur_adc = data[8] | (data[9] << 8)
                if (top_adc - cur_adc) > 150:
                    done.add(slot)
        return done

    def close_telemetry(self):
        if getattr(self, "_telem_dev", None):
            try:
                self._telem_dev.close()
            except Exception:
                pass
            self._telem_dev = None
