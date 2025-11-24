import cv2
from djitellopy import Tello
from time import sleep
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TelloController:
    def __init__(self):
        self.drone = Tello()
        self.drone.connect()
        logging.info(f"배터리 잔량: {self.drone.get_battery()}%")

        self.drone.streamon()
        self.frame_reader = self.drone.get_frame_read()
        self.frame_width, self.frame_height = 960, 720
        self.running = True

    def run(self):
        try:
            logging.info("스트리밍 시작")
            while self.running:
                frame = self.frame_reader.frame
                if frame is None:
                    continue

                frame = cv2.resize(frame, (self.frame_width, self.frame_height))
                cv2.imshow("Tello Stream", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.running = False
                    break
                sleep(0.01)

        except Exception as e:
            logging.error(f"오류 발생: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.drone.streamoff()
        self.drone.end()
        cv2.destroyAllWindows()
        logging.info("종료")


if __name__ == "__main__":
    controller = TelloController()
    controller.run()
