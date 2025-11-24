import cv2
from ultralytics import YOLO  # 추가
from djitellopy import Tello
from time import sleep
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TelloYOLOController:
    def __init__(self):
        self.drone = Tello()
        self.drone.connect()
        logging.info(f"배터리 잔량: {self.drone.get_battery()}%")

        # YOLO 모델 로드 추가
        self.model = YOLO("yolov8n.pt")

        self.drone.streamon()
        self.frame_reader = self.drone.get_frame_read()
        self.frame_width, self.frame_height = 960, 720
        self.running = True

    def run(self):
        try:
            logging.info("YOLO 탐지 시작")
            while self.running:
                frame = self.frame_reader.frame
                if frame is None:
                    continue

                frame = cv2.resize(frame, (self.frame_width, self.frame_height))

                # YOLO 추론 및 시각화 추가
                results = self.model(frame)
                annotated_frame = results[0].plot()

                cv2.imshow("Tello YOLO Stream", annotated_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.running = False
                    break
        except Exception as e:
            logging.error(f"오류: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.drone.streamoff()
        self.drone.end()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    controller = TelloYOLOController()
    controller.run()
