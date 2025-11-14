from djitellopy import Tello
import time

def main():
    drone = Tello()
    drone.connect()
    print(f"배터리 잔량: {drone.get_battery()}%")

    try:
        print("이륙!")
        drone.takeoff()
        time.sleep(3)

        print("위로 30cm 이동")
        drone.move_up(30)
        time.sleep(2)

        print("앞으로 30cm 이동")
        drone.move_forward(30)
        time.sleep(2)

        print("시계 방향 90도 회전")
        drone.rotate_clockwise(90)
        time.sleep(2)

        print("뒤로 30cm 이동")
        drone.move_back(30)
        time.sleep(2)

        print("착륙!")
        drone.land()

    except Exception as e:
        print(f"[오류] {e}")
        try:
            drone.land()
        except:
            pass
    finally:
        drone.end()
        print("프로그램 종료")

if __name__ == "__main__":
    main()