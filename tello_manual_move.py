from djitellopy import Tello
import time

def main():
    drone = Tello()
    drone.connect()
    print(f"배터리 잔량: {drone.get_battery()}%")


if __name__ == "__main__":
    main()