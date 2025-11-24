import cv2
from ultralytics import YOLO
from djitellopy import Tello
from time import sleep
import threading
from queue import Queue
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TelloYOLOController:
    def __init__(self):
        self.drone = Tello()
        self.drone.connect()

        self.model = YOLO("yolov8n.pt")
        self.drone.streamon()
        self.frame_reader = self.drone.get_frame_read()
        self.frame_width, self.frame_height = 960, 720

        self.has_taken_off = False
        self.running = True

        # 스레드 통신용 큐 생성
        self.frame_queue = Queue(maxsize=2)
        self.detection_queue = Queue(maxsize=2)

        # 스레드 분리
        self.capture_thread = threading.Thread(target=self.capture_frames, daemon=True)
        self.detection_thread = threading.Thread(
            target=self.process_detections, daemon=True
        )
        self.control_thread = threading.Thread(
            target=self.execute_commands, daemon=True
        )

        self.control_thread.start()
        self.capture_thread.start()
        self.detection_thread.start()

    def capture_frames(self):
        while self.running:
            frame = self.frame_reader.frame
            if frame is None:
                continue

            frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            self.frame_queue.put(frame)
            sleep(0.005)

    def process_detections(self):
        while self.running:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                results = self.model(frame)
                annotated_frame = results[0].plot()

                if self.detection_queue.full():
                    try:
                        self.detection_queue.get_nowait()
                    except:
                        pass
                self.detection_queue.put(annotated_frame)
            sleep(0.005)

    def execute_commands(self):
        while self.running:
            cmd = input("Command (t:takeoff, l:land, w/s/a/d:move): ")
            if cmd == "t" and not self.has_taken_off:
                self.drone.takeoff()
                self.has_taken_off = True
            elif cmd == "l" and self.has_taken_off:
                self.drone.land()
                self.has_taken_off = False
            elif cmd == "w":
                self.drone.move_forward(30)
            elif cmd == "s":
                self.drone.move_back(30)
            elif cmd == "a":
                self.drone.move_left(30)
            elif cmd == "d":
                self.drone.move_right(30)
            elif cmd == "i":
                self.drone.move_up(30)
            elif cmd == "o":
                self.drone.move_down(30)
            elif cmd == "q":
                self.running = False
                break
            sleep(0.1)

    def run(self):
        try:
            while self.running:
                if not self.detection_queue.empty():
                    frame = self.detection_queue.get()
                    cv2.imshow("Tello Multithreaded", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.running = False
                    break
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        self.capture_thread.join()
        self.detection_thread.join()
        self.drone.end()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    c = TelloYOLOController()
    c.run()
