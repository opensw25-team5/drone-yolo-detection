import cv2
from ultralytics import YOLO
from djitellopy import Tello
from time import sleep
import time
import numpy as np
import threading
from queue import Queue
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TelloYOLOController:
    def __init__(self):
        self.drone = Tello()
        self.drone.connect()
        logging.info(f"배터리 잔량: {self.drone.get_battery()}%")

        self.model = YOLO("yolov8n.pt")
        self.class_names = self.model.names

        self.has_taken_off = False

        self.drone.streamon()
        self.frame_reader = self.drone.get_frame_read()
        self.frame_width, self.frame_height = 960, 720
        self.cap = None

        self.center_x = 640 // 2
        self.center_y = 480 // 2
        self.speed = 30

        self.output_root = "runs/crops"
        self.min_confidence = 0.40
        self.save_interval_sec = 0.20
        self.save_all_detections = False
        self.crop_margin = 0.05
        self._last_save_time = 0.0

        self.running = True
        self.frame_queue = Queue(maxsize=2)
        self.detection_queue = Queue(maxsize=2)
        self.command_queue = Queue()
        self.save_queue = Queue(maxsize=128)

        self.capture_thread = threading.Thread(target=self.capture_frames, daemon=True)
        self.detection_thread = threading.Thread(
            target=self.process_detections, daemon=True
        )
        self.control_thread = threading.Thread(
            target=self.execute_commands, daemon=True
        )
        self.saver_thread = threading.Thread(target=self.save_worker, daemon=True)

        self.capture_thread.start()
        self.detection_thread.start()
        self.control_thread.start()
        self.saver_thread.start()

    def capture_frames(self):
        while self.running:
            frame = self.frame_reader.frame
            if frame is None:
                sleep(0.01)
                continue
            if (
                frame.shape[1] != self.frame_width
                or frame.shape[0] != self.frame_height
            ):
                frame = cv2.resize(frame, (self.frame_width, self.frame_height))

            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass

            self.frame_queue.put(frame)
            sleep(0.005)

    def process_detections(self):
        last_command_time = 0.0
        command_cooldown = 0.05

        while self.running:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()

                results = self.model(frame)
                res = results[0]
                annotated_frame = res.plot()

                boxes = res.boxes
                if boxes is not None and len(boxes) > 0:
                    candidates = []
                    for i in range(len(boxes)):
                        b = boxes[i]
                        xyxy = b.xyxy[0].cpu().numpy()
                        conf = (
                            float(b.conf[0].cpu().numpy())
                            if b.conf is not None
                            else 0.0
                        )
                        cls_id = (
                            int(b.cls[0].cpu().numpy()) if b.cls is not None else -1
                        )
                        x1, y1, x2, y2 = xyxy
                        area = max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))
                        if conf >= self.min_confidence:
                            candidates.append((area, i, xyxy, cls_id, conf))

                    now = time.time()
                    if (
                        candidates
                        and (now - self._last_save_time) >= self.save_interval_sec
                    ):
                        if self.save_all_detections:
                            targets = candidates
                        else:
                            targets = [max(candidates, key=lambda x: x[0])]

                        for _, _, xyxy, cls_id, conf in targets:
                            self.enqueue_crop_save(frame, xyxy, cls_id, conf)
                        self._last_save_time = now

                    if candidates:
                        target = max(candidates, key=lambda x: x[0])
                        _, _, xyxy, cls_id, _ = target
                        x1, y1, x2, y2 = map(int, xyxy)
                        target_x = (x1 + x2) // 2
                        target_y = (y1 + y2) // 2

                        cv2.circle(
                            annotated_frame, (target_x, target_y), 5, (0, 255, 0), -1
                        )

                        current_time = time.time()
                        if current_time - last_command_time >= command_cooldown:
                            last_command_time = current_time

                        if 0 <= cls_id < len(self.class_names):
                            class_name = self.class_names[cls_id]
                        else:
                            class_name = "unknown"

                        cv2.putText(
                            annotated_frame,
                            f"Class: {class_name}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2,
                        )

                if self.detection_queue.full():
                    try:
                        self.detection_queue.get_nowait()
                    except:
                        pass
                self.detection_queue.put(annotated_frame)

            sleep(0.005)

    def enqueue_crop_save(self, frame, xyxy, cls_id, conf):
        try:
            if 0 <= int(cls_id) < len(self.class_names):
                cls_name = self.class_names[int(cls_id)]
            else:
                cls_name = "unknown"

            self.save_queue.put_nowait(
                (
                    frame.copy(),
                    tuple(map(float, xyxy)),
                    int(cls_id),
                    float(conf),
                    cls_name,
                )
            )
        except:
            pass

    def save_worker(self):
        while self.running:
            try:
                item = self.save_queue.get(timeout=0.1)
            except:
                continue

            frame, xyxy, cls_id, conf, cls_name = item
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = xyxy

            bw = x2 - x1
            bh = y2 - y1
            mx = bw * self.crop_margin
            my = bh * self.crop_margin

            x1m = int(max(0, np.floor(x1 - mx)))
            y1m = int(max(0, np.floor(y1 - my)))
            x2m = int(min(w, np.ceil(x2 + mx)))
            y2m = int(min(h, np.ceil(y2 + my)))

            if x2m <= x1m or y2m <= y1m:
                continue

            crop = frame[y1m:y2m, x1m:x2m]

            safe_cls = str(cls_name)
            out_dir = os.path.join(self.output_root, safe_cls)
            os.makedirs(out_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            fn = f"{ts}_cls{cls_id}_{conf:.2f}_{crop.shape[1]}x{crop.shape[0]}.jpg"
            out_path = os.path.join(out_dir, fn)

            try:
                cv2.imwrite(out_path, crop)
                logging.info(f"[SAVE] {out_path}")
            except Exception as e:
                logging.error(f"크롭 저장 실패: {e}")

    def execute_commands(self):
        while self.running:
            while True:
                keyboard_control = input("keyboard control activated: ")
                if keyboard_control == "t":
                    self.drone.takeoff()
                    self.has_taken_off = True
                    continue
                elif keyboard_control == "l":
                    self.drone.land()
                    self.has_taken_off = False
                    break
                elif keyboard_control == "w":
                    self.drone.move_forward(30)
                    continue
                elif keyboard_control == "s":
                    self.drone.move_back(30)
                    continue
                elif keyboard_control == "a":
                    self.drone.move_left(30)
                    continue
                elif keyboard_control == "d":
                    self.drone.move_right(30)
                    continue
                elif keyboard_control == "i":
                    self.drone.move_up(30)
                    continue
                elif keyboard_control == "o":
                    self.drone.move_down(30)
                    continue
                else:
                    sleep(1)
                    continue

    def run(self):
        try:
            logging.info("프로그램 시작")
            self.print_instructions()

            while self.running:
                if not self.detection_queue.empty():
                    frame = self.detection_queue.get()
                    cv2.imshow("Tello YOLO Control (Crop Saver)", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.running = False
                    break

                sleep(0.005)

        except Exception as e:
            logging.error(f"오류 발생: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False

        self.capture_thread.join(timeout=1.0)
        self.detection_thread.join(timeout=1.0)
        self.control_thread.join(timeout=1.0)
        self.saver_thread.join(timeout=1.0)

        try:
            try:
                self.drone.streamoff()
            except:
                pass
            if self.has_taken_off:
                self.drone.land()
                self.has_taken_off = False
            self.drone.end()
        except:
            pass

        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        logging.info("프로그램 종료")

    def print_instructions(self):
        logging.info(
            "키보드 조작: t(이륙), l(착륙), w/s/a/d(이동), i(상승), o(하강), q(창 닫기)"
        )

    def process_detection(self, frame):
        results = self.model(frame)
        annotated_frame = results[0].plot()

        if len(results[0].boxes) > 0:
            boxes = results[0].boxes
            max_area = 0
            target_box = None
            target_class = None
            target_conf = 0.0

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy()) if box.conf is not None else 0.0
                area = (x2 - x1) * (y2 - y1)
                if conf >= self.min_confidence and area > max_area:
                    max_area = area
                    target_box = box
                    target_class = int(box.cls[0].cpu().numpy())
                    target_conf = conf

            if target_box is not None:
                xyxy = target_box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                target_x = (x1 + x2) // 2
                target_y = (y1 + y2) // 2
                cv2.circle(annotated_frame, (target_x, target_y), 5, (0, 255, 0), -1)

                self.enqueue_crop_save(frame, xyxy, target_class, target_conf)

                if 0 <= target_class < len(self.class_names):
                    class_name = self.class_names[target_class]
                else:
                    class_name = "unknown"

                cv2.putText(
                    annotated_frame,
                    f"Class: {class_name}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
        return annotated_frame


if __name__ == "__main__":
    controller = TelloYOLOController()
    controller.run()
