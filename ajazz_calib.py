import argparse
import hid
import time

VENDOR_ID = 0x0c45
PRODUCT_ID = 0x80b1

def send_cmd(cmd_bytes):
    packet = cmd_bytes + [0x00] * (64 - len(cmd_bytes))
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    if not devices:
        print("Error: keyboard not found!")
        return False
    for d in devices:
        try:
            dev = hid.device()
            dev.open_path(d['path'])
            dev.write([0x00] + packet)
            dev.close()
        except Exception:
            pass
    return True

def run_calibration(duration: int, clear_first: bool):
    print("Putting the keyboard into calibration mode...")
    if not send_cmd([0xaa, 0x64]):
        return
    time.sleep(0.2)

    if clear_first:
        print("Clearing the old calibration...")
        send_cmd([0xaa, 0x0f, 0x05])
        time.sleep(0.2)

    print(f"\n>>> CALIBRATION ACTIVE ({duration} s) <<<")
    print("Typing is paused during calibration. Press each key all the way down!")
    
    for remaining in range(duration, 0, -1):
        print(f"Seconds left: {remaining:2d}...", end="\r")
        time.sleep(1)

    print("\nSaving calibration and returning the keyboard to normal...")
    send_cmd([0xaa, 0x65])
    print("Done! The keyboard is back to normal.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline calibration for the Ajazz AK820 Max HE")
    parser.add_argument("-t", "--time", type=int, default=15, help="Calibration time in seconds (default 15)")
    parser.add_argument("--clear", action="store_true", help="Clear the current calibration first")
    args = parser.parse_args()

    run_calibration(args.time, args.clear)
