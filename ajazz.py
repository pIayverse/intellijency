import argparse
import hid
import time

VENDOR_ID = 0x0c45
PRODUCT_ID = 0x80b1

def send_packets(packets, delay=0.01):
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    if not devices:
        print("Error: Ajazz AK820 Max HE keyboard not found!")
        return False
    for d in devices:
        try:
            dev = hid.device()
            dev.open_path(d['path'])
            for pkt in packets:
                full_pkt = pkt + [0x00] * (64 - len(pkt))
                dev.write([0x00] + full_pkt[:64])
                if delay > 0:
                    time.sleep(delay)
            dev.close()
        except Exception:
            pass
    return True

EFFECTS = {
    "off": 0x00, "static": 0x01, "point_on": 0x02, "point_off": 0x03,
    "starry": 0x04, "snowfall": 0x05, "floral": 0x06, "dynamic": 0x07,
    "spectrum": 0x08, "color_follow": 0x09, "colorful": 0x0a, "flowing": 0x0b,
    "turning": 0x0c, "one_touch": 0x0d, "two_bird": 0x0e, "ripples": 0x0f,
    "endless": 0x10, "layered": 0x11, "gentle": 0x12, "back_forth": 0x13,
}

def cmd_light(args):
    if args.power == 0:
        mode = 0x00
    elif args.mode in EFFECTS:
        mode = EFFECTS[args.mode]
    else:
        mode = int(args.mode, 0)
    pkt = [
        0xaa, 0x23, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00,
        mode, args.red, args.green, args.blue, 0xff,
        0x00, 0x00, 0x00, args.rgb_mode, args.brightness, args.speed, args.direction, 0x00, 0x00,
        0xaa, 0x55
    ]
    if send_packets([pkt], delay=0):
        print(f"Lighting: Mode={args.mode} (0x{mode:02x}), RGB=({args.red},{args.green},{args.blue}), Rainbow={args.rgb_mode}, Bright={args.brightness}/5, Speed={args.speed}/5")

def cmd_switch(args):
    t_val = int(round(args.trigger * 100))
    p_val = int(round(args.press * 100)) if args.ft else 0
    r_val = int(round(args.release * 100)) if args.ft else 0
    full_flag = 0x01 if (args.ft and args.full) else 0x00
    block = [
        0x03, full_flag, t_val & 0xff, (t_val >> 8) & 0xff,
        p_val & 0xff, (p_val >> 8) & 0xff, r_val & 0xff, (r_val >> 8) & 0xff,
    ]
    offsets = [
        (0x00, 0x00), (0x38, 0x00), (0x70, 0x00), (0xa8, 0x00), (0xe0, 0x00),
        (0x18, 0x01), (0x50, 0x01), (0x88, 0x01), (0xc0, 0x01), (0xf8, 0x01),
        (0x30, 0x02), (0x68, 0x02), (0xa0, 0x02), (0xd8, 0x02), (0x10, 0x03),
        (0x48, 0x03), (0x80, 0x03), (0xb8, 0x03)
    ]
    packets = [[0xaa, 0x27, 0x10, 0xf0, 0x03, 0x00, 0x01, 0x00]]
    for off_low, off_high in offsets:
        packets.append([0xaa, 0x27, 0x38, off_low, off_high, 0x00, 0x00, 0x00] + block * 7)
    if send_packets(packets, delay=0.01):
        print(f"Switches: Trigger={args.trigger}mm, FT={args.ft}, Full={full_flag}")

def cmd_deadzone(args):
    top_val = int(round(args.top * 100)) & 0xff
    bot_val = int(round(args.bottom * 100)) & 0xff
    pkt = [
        0xaa, 0x21, 0x38, 0x00, 0x00, 0x00, 0x01, 0x00,
        0x00, 0x00, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00,
        top_val, bot_val, 0x00, args.enable, 0x00, 0x00, 0x01
    ]
    if send_packets([pkt], delay=0):
        print(f"Dead Zone: Enable={args.enable}, Top={args.top}mm, Bottom={args.bottom}mm")

def cmd_calib(args):
    print("Starting calibration...")
    if not send_packets([[0xaa, 0x64]], delay=0.2):
        return
    if args.clear:
        send_packets([[0xaa, 0x0f, 0x05]], delay=0.2)
    print(f"Calibration active ({args.time} s). Press keys all the way down!")
    for rem in range(args.time, 0, -1):
        print(f"Remaining: {rem:2d} s...", end="\r")
        time.sleep(1)
    send_packets([[0xaa, 0x65]], delay=0)
    print("\nCalibration finished!")

def cmd_remap(args):
    layer_cmd = 0x26 if args.layer == "fn" else 0x22
    table = [0x00] * 512
    idx = args.slot * 4
    if args.keycode > 0:
        table[idx:idx+4] = [0x02, args.mod, args.keycode, 0x00]
    packets = []
    for i in range(9):
        off = i * 0x38
        packets.append([0xaa, layer_cmd, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + table[i*56:(i+1)*56])
    packets.append([0xaa, layer_cmd, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + table[504:512])
    if send_packets(packets, delay=0.01):
        print(f"Layout ({args.layer}): slot {args.slot} -> HID 0x{args.keycode:02x}")

def _write_pair_mode(mode_code, mode_param, slot1, hid1, slot2, hid2, enable, trigger_mm, press_mm=0.0, release_mm=0.0, full_ft=0):
    t_val, p_val, r_val = int(round(trigger_mm * 100)), int(round(press_mm * 100)), int(round(release_mm * 100))
    sw_table = [[0x03, 0x00, 0x96, 0x00, 0x00, 0x00, 0x00, 0x00] for _ in range(126)]
    if enable:
        adv = [0x00, 0x01 if full_ft else 0x00, t_val & 0xff, (t_val >> 8) & 0xff, p_val & 0xff, (p_val >> 8) & 0xff, r_val & 0xff, (r_val >> 8) & 0xff]
        sw_table[slot1], sw_table[slot2] = adv, adv
    offsets = [
        (0x00, 0x00), (0x38, 0x00), (0x70, 0x00), (0xa8, 0x00), (0xe0, 0x00),
        (0x18, 0x01), (0x50, 0x01), (0x88, 0x01), (0xc0, 0x01), (0xf8, 0x01),
        (0x30, 0x02), (0x68, 0x02), (0xa0, 0x02), (0xd8, 0x02), (0x10, 0x03),
        (0x48, 0x03), (0x80, 0x03), (0xb8, 0x03)
    ]
    packets = [[0xaa, 0x27, 0x38, off_l, off_h, 0x00, 0x00, 0x00] + [b for s in sw_table[i*7:(i+1)*7] for b in s] for i, (off_l, off_h) in enumerate(offsets)]
    key_table = [0x00] * 512
    if enable:
        key_table[slot1*4:slot1*4+4] = [mode_code, mode_param, hid1, hid2]
        key_table[slot2*4:slot2*4+4] = [mode_code, mode_param, hid1, hid2]
    for i in range(9):
        off = i * 0x38
        packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
    packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
    return send_packets(packets, delay=0.01)

def cmd_rs(args):
    if _write_pair_mode(0x0c, 0x00, args.slot1, args.hid1, args.slot2, args.hid2, args.enable, args.trigger):
        print(f"RS ({args.slot1}+{args.slot2}): {'ON' if args.enable else 'OFF'}")

def cmd_socd(args):
    if _write_pair_mode(0x0b, args.pattern, args.slot1, args.hid1, args.slot2, args.hid2, args.enable, args.trigger, args.press, args.release, args.full):
        print(f"SOCD ({args.slot1}+{args.slot2}): {'ON' if args.enable else 'OFF'}, pattern=0x{args.pattern:02x}")

def cmd_dks(args):
    dks_table = [0x00] * 1024
    if args.enable:
        dks_table[0:4] = [int(round(d * 10)) & 0xff for d in args.depths]
        dks_table[4:8] = [k & 0xff for k in args.keys]
        dks_table[8:16] = [args.mask1, 0x00, args.mask2, 0x00, args.mask3, 0x00, args.mask4, 0x00]
    offsets = [
        (0x00, 0x00), (0x38, 0x00), (0x70, 0x00), (0xa8, 0x00), (0xe0, 0x00),
        (0x18, 0x01), (0x50, 0x01), (0x88, 0x01), (0xc0, 0x01), (0xf8, 0x01),
        (0x30, 0x02), (0x68, 0x02), (0xa0, 0x02), (0xd8, 0x02), (0x10, 0x03),
        (0x48, 0x03), (0x80, 0x03), (0xb8, 0x03)
    ]
    packets = [[0xaa, 0x28, 0x38, off_l, off_h, 0x00, 0x00, 0x00] + dks_table[i*56:(i+1)*56] for i, (off_l, off_h) in enumerate(offsets)]
    packets.append([0xaa, 0x28, 0x10, 0xf0, 0x03, 0x00, 0x01, 0x00] + dks_table[1008:1024])
    key_table = [0x00] * 512
    if args.enable:
        key_table[args.slot*4:args.slot*4+4] = [0x08, 0x00, 0x00, 0x00]
    for i in range(9):
        off = i * 0x38
        packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
    packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
    if send_packets(packets, delay=0.01):
        print(f"DKS (slot {args.slot}): {'ON' if args.enable else 'OFF'}")

def cmd_mt(args):
    key_table = [0x00] * 512
    if args.enable:
        t_val = max(1, min(255, int(round(args.time / 10))))
        key_table[args.slot*4:args.slot*4+4] = [0x09, args.hold & 0xff, args.click & 0xff, t_val]
    packets = []
    for i in range(9):
        off = i * 0x38
        packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
    packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
    if send_packets(packets, delay=0.01):
        print(f"MT (slot {args.slot}): {'ON' if args.enable else 'OFF'}, hold=0x{args.hold:02x}, click=0x{args.click:02x}, time={args.time}ms")

def cmd_tgl(args):
    key_table = [0x00] * 512
    if args.enable:
        key_table[args.slot*4:args.slot*4+4] = [0x0a, args.keycode & 0xff, 0x00, 0x00]
    packets = []
    for i in range(9):
        off = i * 0x38
        packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
    packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])
    if send_packets(packets, delay=0.01):
        print(f"TGL (slot {args.slot}): {'ON' if args.enable else 'OFF'}, keycode=0x{args.keycode:02x}")

def cmd_settings(args):
    rate_map = {"1k": 0x03, "4k": 0x05, "8k": 0x06}
    top_val = int(round(args.top * 100)) & 0xff
    bot_val = int(round(args.bottom * 100)) & 0xff
    pkt = [
        0xaa, 0x21, 0x38, 0x00, 0x00, 0x00, args.stability, 0x00,
        0x00, 0x00, 0x00, 0x05, 0x00, rate_map[args.rate], 0x00, 0x00,
        top_val, bot_val, 0x00, args.dz_enable, 0x00, 0x00, args.adaptive
    ]
    if send_packets([pkt], delay=0):
        print(f"Settings: Rate={args.rate.upper()}, AdaptiveCalib={args.adaptive}, DZ={args.dz_enable} ({args.top}/{args.bottom}mm)")

def cmd_macro(args):
    # Macro body: 4-byte header + 4 bytes per event (delay_l, delay_h, hid, flag)
    events = []
    for k in args.keys:
        events.extend([args.delay & 0xff, (args.delay >> 8) & 0xff, k & 0xff, 0xb0])
        events.extend([args.delay & 0xff, (args.delay >> 8) & 0xff, k & 0xff, 0x30])
    header = [len(events) // 2, 0x00, 0x00, 0x00]
    body = header + events

    packets = [[0xaa, 0x25, 0x38, 0x00, 0x00, 0x00, 0x00, 0x00, 0x90, 0x01]]
    for off in [0x38, 0x70, 0xa8, 0xe0, 0x18, 0x50]:
        off_h = 0x01 if off in [0x18, 0x50] else 0x00
        packets.append([0xaa, 0x25, 0x38, off, off_h, 0x00, 0x00, 0x00])
    packets.append([0xaa, 0x25, 0x08, 0x88, 0x01, 0x00, 0x00, 0x00])
    packets.append([0xaa, 0x25, len(body) & 0xff, 0x90, 0x01, 0x00, 0x01, 0x00] + body)

    key_table = [0x00] * 512
    key_table[args.slot*4:args.slot*4+4] = [0x06, 0x00, 0x00, 0x00]
    for i in range(9):
        off = i * 0x38
        packets.append([0xaa, 0x22, 0x38, off & 0xff, (off >> 8) & 0xff, 0x00, 0x00, 0x00] + key_table[i*56:(i+1)*56])
    packets.append([0xaa, 0x22, 0x08, 0xf8, 0x01, 0x00, 0x01, 0x00] + key_table[504:512])

    if send_packets(packets, delay=0.01):
        print(f"Macro M1 written and assigned to slot {args.slot}: keys={[hex(k) for k in args.keys]}, delay={args.delay}ms")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline command-line driver for the Ajazz AK820 Max HE")
    sub = parser.add_subparsers(dest="command", required=True)

    p_light = sub.add_parser("light")
    p_light.add_argument("-p", "--power", type=int, default=1, choices=[0, 1])
    p_light.add_argument("-m", "--mode", type=str, default="static")
    p_light.add_argument("--rgb-mode", type=int, default=0, choices=[0, 1])
    p_light.add_argument("-r", "--red", type=lambda x: int(x, 0), default=0xff)
    p_light.add_argument("-g", "--green", type=lambda x: int(x, 0), default=0x00)
    p_light.add_argument("-b", "--blue", type=lambda x: int(x, 0), default=0x00)
    p_light.add_argument("--brightness", type=int, default=5, choices=[0, 1, 2, 3, 4, 5])
    p_light.add_argument("--speed", type=int, default=3, choices=[1, 2, 3, 4, 5])
    p_light.add_argument("--direction", type=int, default=0, choices=[0, 1])
    p_light.set_defaults(func=cmd_light)

    p_sw = sub.add_parser("switch")
    p_sw.add_argument("--trigger", type=float, default=1.50)
    p_sw.add_argument("--press", type=float, default=0.30)
    p_sw.add_argument("--release", type=float, default=0.20)
    p_sw.add_argument("--ft", type=int, default=1, choices=[0, 1])
    p_sw.add_argument("--full", type=int, default=0, choices=[0, 1])
    p_sw.set_defaults(func=cmd_switch)

    p_dz = sub.add_parser("deadzone")
    p_dz.add_argument("--top", type=float, default=0.30)
    p_dz.add_argument("--bottom", type=float, default=0.30)
    p_dz.add_argument("--enable", type=int, default=1, choices=[0, 1])
    p_dz.set_defaults(func=cmd_deadzone)

    p_cal = sub.add_parser("calib")
    p_cal.add_argument("-t", "--time", type=int, default=15)
    p_cal.add_argument("--clear", action="store_true")
    p_cal.set_defaults(func=cmd_calib)

    p_rem = sub.add_parser("remap")
    p_rem.add_argument("--layer", choices=["normal", "fn"], default="normal")
    p_rem.add_argument("--slot", type=int, default=0)
    p_rem.add_argument("--keycode", type=lambda x: int(x, 0), default=0x00)
    p_rem.add_argument("--mod", type=lambda x: int(x, 0), default=0x00)
    p_rem.set_defaults(func=cmd_remap)

    p_rs = sub.add_parser("rs")
    p_rs.add_argument("--enable", type=int, default=1, choices=[0, 1])
    p_rs.add_argument("--trigger", type=float, default=1.46)
    p_rs.add_argument("--slot1", type=int, default=49)
    p_rs.add_argument("--hid1", type=lambda x: int(x, 0), default=0x04)
    p_rs.add_argument("--slot2", type=int, default=51)
    p_rs.add_argument("--hid2", type=lambda x: int(x, 0), default=0x07)
    p_rs.set_defaults(func=cmd_rs)

    p_socd = sub.add_parser("socd")
    p_socd.add_argument("--enable", type=int, default=1, choices=[0, 1])
    p_socd.add_argument("--pattern", type=lambda x: int(x, 0), default=0x04)
    p_socd.add_argument("--trigger", type=float, default=1.94)
    p_socd.add_argument("--press", type=float, default=0.29)
    p_socd.add_argument("--release", type=float, default=0.33)
    p_socd.add_argument("--full", type=int, default=1, choices=[0, 1])
    p_socd.add_argument("--slot1", type=int, default=49)
    p_socd.add_argument("--hid1", type=lambda x: int(x, 0), default=0x04)
    p_socd.add_argument("--slot2", type=int, default=51)
    p_socd.add_argument("--hid2", type=lambda x: int(x, 0), default=0x07)
    p_socd.set_defaults(func=cmd_socd)

    p_dks = sub.add_parser("dks")
    p_dks.add_argument("--enable", type=int, default=1, choices=[0, 1])
    p_dks.add_argument("--slot", type=int, default=49)
    p_dks.add_argument("--depths", type=float, nargs=4, default=[1.6, 3.0, 3.0, 1.6])
    p_dks.add_argument("--keys", type=lambda x: int(x, 0), nargs=4, default=[0x00, 0x08, 0x00, 0x00])
    p_dks.add_argument("--mask1", type=lambda x: int(x, 0), default=0x00)
    p_dks.add_argument("--mask2", type=lambda x: int(x, 0), default=0x01)
    p_dks.add_argument("--mask3", type=lambda x: int(x, 0), default=0x01)
    p_dks.add_argument("--mask4", type=lambda x: int(x, 0), default=0x00)
    p_dks.set_defaults(func=cmd_dks)

    p_mt = sub.add_parser("mt")
    p_mt.add_argument("--enable", type=int, default=1, choices=[0, 1])
    p_mt.add_argument("--slot", type=int, default=49)
    p_mt.add_argument("--hold", type=lambda x: int(x, 0), default=0x04)
    p_mt.add_argument("--click", type=lambda x: int(x, 0), default=0x05)
    p_mt.add_argument("--time", type=int, default=400)
    p_mt.set_defaults(func=cmd_mt)

    p_tgl = sub.add_parser("tgl")
    p_tgl.add_argument("--enable", type=int, default=1, choices=[0, 1])
    p_tgl.add_argument("--slot", type=int, default=66)
    p_tgl.add_argument("--keycode", type=lambda x: int(x, 0), default=0x27)
    p_tgl.set_defaults(func=cmd_tgl)

    p_set = sub.add_parser("settings")
    p_set.add_argument("--stability", type=int, default=1, choices=[0, 1])
    p_set.add_argument("--rate", choices=["1k", "4k", "8k"], default="8k")
    p_set.add_argument("--adaptive", type=int, default=1, choices=[0, 1])
    p_set.add_argument("--dz-enable", type=int, default=1, choices=[0, 1])
    p_set.add_argument("--top", type=float, default=0.30)
    p_set.add_argument("--bottom", type=float, default=0.30)
    p_set.set_defaults(func=cmd_settings)

    p_mac = sub.add_parser("macro")
    p_mac.add_argument("--slot", type=int, default=0, help="Key slot index (0 = Esc)")
    p_mac.add_argument("--keys", type=lambda x: int(x, 0), nargs="+", default=[0x04, 0x05])
    p_mac.add_argument("--delay", type=int, default=20)
    p_mac.set_defaults(func=cmd_macro)

    args = parser.parse_args()
    args.func(args)
