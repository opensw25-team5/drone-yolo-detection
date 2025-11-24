from djitellopy import Tello
from time import sleep

def print_instructions():
    print("===== Tello 키보드 조종 =====")
    print("t : 이륙")
    print("l : 착륙")
    print("w : 앞으로 30cm")
    print("s : 뒤로 30cm")
    print("a : 왼쪽으로 30cm")
    print("d : 오른쪽으로 30cm")
    print("i : 위로 30cm")
    print("o : 아래로 30cm")
    print("q : 종료 (프로그램 끝)")
    print("=============================")

def main():
    drone = Tello()
    drone.connect()
    print(f"배터리 잔량: {drone.get_battery()}%")

    has_taken_off = False
    print_instructions()

    try:
        while True:
            cmd = input("명령 입력(t/l/w/s/a/d/i/o/q): ").strip().lower()

            if cmd == "t":
                drone.takeoff()
                has_taken_off = True

            elif cmd == "l":
                drone.land()
                has_taken_off = False

            elif cmd == "w":
                drone.move_forward(30)

            elif cmd == "s":
                drone.move_back(30)

            elif cmd == "a":
                drone.move_left(30)

            elif cmd == "d":
                drone.move_right(30)

            elif cmd == "i":
                drone.move_up(30)

            elif cmd == "o":
                drone.move_down(30)

            elif cmd == "q":
                print("종료합니다.")
                break

            else:
                print("알 수 없는 명령입니다. 다시 입력해주세요.")

            sleep(0.1)

    except Exception as e:
        print(f"[오류] {e}")
    finally:
        if has_taken_off:
            try:
                drone.land()
            except:
                pass
        drone.end()
        print("프로그램 종료")

if __name__ == "__main__":
    main()