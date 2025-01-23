import psutil
import time
import subprocess
from argparse import ArgumentParser
from curses import wrapper

class DiskSpeedMonitor:
    def __init__(self, interval=1, unit="MB"):
        self.interval = interval
        self.unit = unit
        self.running = False
        self.previous_read = 0
        self.previous_write = 0
        self.unit_divisor = self.get_unit_divisor(unit)

    def get_disk_io(self):
        disk_io = psutil.disk_io_counters()
        return disk_io.read_bytes, disk_io.write_bytes

    def calculate_speed(self, current, previous):
        return (current - previous) / self.interval

    def get_unit_divisor(self, unit):
        units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
        return units.get(unit.upper(), 1024**2)  # Default to MB

    def disk_health(self):
        disks = psutil.disk_partitions()
        health_info = []
        for disk in disks:
            try:
                device = disk.device
                health_score = self.get_smart_health(device)
                usage = psutil.disk_usage(disk.mountpoint)
                health_info.append((device, usage.total, usage.used, usage.free, usage.percent, health_score))
            except Exception as e:
                # Skip disks that cannot be accessed or monitored
                continue
        return health_info

    def get_smart_health(self, device):
        try:
            result = subprocess.run(["smartctl", "-A", device], capture_output=True, text=True, check=True)
            lines = result.stdout.split("\n")

            # Parse SMART attributes to derive a health score
            reallocated_sectors = 0
            wear_leveling_count = 100
            power_on_hours = 0

            for line in lines:
                if "Reallocated_Sector_Ct" in line:
                    reallocated_sectors = int(line.split()[9])
                elif "Wear_Leveling_Count" in line:
                    wear_leveling_count = int(line.split()[9])
                elif "Power_On_Hours" in line:
                    power_on_hours = int(line.split()[9])

            # Simplistic health score calculation (can be refined based on thresholds)
            health_score = max(0, 100 - (reallocated_sectors / 10 + power_on_hours / 1000))
            health_score = min(health_score, 100)  # Cap at 100%

            return f"{health_score:.2f}%"
        except Exception as e:
            return "Unknown"

    def monitor(self, stdscr):
        self.previous_read, self.previous_write = self.get_disk_io()
        while self.running:
            time.sleep(self.interval)
            current_read, current_write = self.get_disk_io()
            read_speed = self.calculate_speed(current_read, self.previous_read)
            write_speed = self.calculate_speed(current_write, self.previous_write)

            self.previous_read = current_read
            self.previous_write = current_write

            health_info = self.disk_health()
            self.display_speed(stdscr, read_speed, write_speed, health_info)

    def display_speed(self, stdscr, read_speed, write_speed, health_info):
        stdscr.clear()
        stdscr.addstr(0, 0, f"Disk Read Speed: {self.human_readable_size(read_speed)}/s")
        stdscr.addstr(1, 0, f"Disk Write Speed: {self.human_readable_size(write_speed)}/s")
        stdscr.addstr(3, 0, "Disk Health:")
        stdscr.addstr(4, 0, f"{'Device':<15}{'Total':<15}{'Used':<15}{'Free':<15}{'Usage (%)':<10}{'Health':<10}")
        for i, (device, total, used, free, percent, health) in enumerate(health_info):
            stdscr.addstr(5 + i, 0, f"{device:<15}{self.human_readable_size(total):<15}{self.human_readable_size(used):<15}{self.human_readable_size(free):<15}{percent:<10.2f}{health:<10}")
        stdscr.refresh()

    @staticmethod
    def human_readable_size(size, unit_divisor=1024):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < unit_divisor:
                return f"{size:.2f} {unit}"
            size /= unit_divisor

    def start(self):
        self.running = True
        wrapper(self.monitor)

    def stop(self):
        self.running = False

if __name__ == "__main__":
    parser = ArgumentParser(description="Monitor real-time disk read and write speed.")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="Interval (in seconds) between updates.")
    parser.add_argument("-u", "--unit", type=str, default="MB", choices=["B", "KB", "MB", "GB"], help="Unit for speed and sizes.")
    args = parser.parse_args()

    monitor = DiskSpeedMonitor(interval=args.interval, unit=args.unit)
    print("Starting Disk Speed Monitor. Press Ctrl+C to stop.")

    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\nStopping Disk Speed Monitor...")
        monitor.stop()
