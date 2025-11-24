## Tello YOLO Object Tracking & Crop Saver

### 프로젝트 개요
DJI Tello 드론의 카메라 영상을 실시간으로 받아 **YOLOv8 객체 탐지**를 수행하고,  
탐지된 객체 주변을 잘라(`crop`) **클래스별 디렉터리에 자동 저장**하는 프로그램입니다.  
스레드와 큐를 활용해 **영상 캡처 / 객체 탐지 / 드론 조작 / 이미지 저장**을 병렬 처리합니다.

---

## 주요 기능

- **실시간 드론 영상 수신**
  - `djitellopy.Tello`를 사용해 Tello 드론에 연결 및 스트리밍 (`streamon`)
  - 프레임 크기 리사이즈 후 처리 (`960x720` 기준)

- **YOLOv8 객체 탐지**
  - `ultralytics.YOLO("yolov8n.pt")` 모델 사용
  - 최소 신뢰도(`min_confidence`, 기본 0.40) 이상인 박스만 후보로 사용
  - 후보 중 **가장 큰 박스(면적 최댓값)** 를 기준 객체로 선택

- **크롭 이미지 자동 저장**
  - 기준(또는 모든) 객체 주변을 약간의 마진(`crop_margin`, 기본 0.05) 포함해 crop
  - `runs/crops/<클래스명>/` 폴더에 `타임스탬프_클래스ID_신뢰도_가로x세로.jpg` 형식으로 저장
  - 저장 간격: `save_interval_sec` (기본 0.20초)
  - `save_all_detections`:
    - `False`: 한 프레임당 가장 큰 객체 1개만 저장
    - `True`: 한 프레임의 모든 후보 객체 저장

- **실시간 시각화**
  - YOLO 결과를 그린 프레임(바운딩 박스 포함) 표시
  - 가장 큰 객체의 중심점에 **초록색 원** 표시
  - 화면 좌측 상단에 클래스명 텍스트 오버레이

- **키보드 기반 드론 조작**
  - 터미널에서 입력받아 명령 실행
  - **조작 키**
    - `t` : 이륙 (`takeoff`)
    - `l` : 착륙 (`land`)
    - `w` : 전진 30cm
    - `s` : 후진 30cm
    - `a` : 좌측 이동 30cm
    - `d` : 우측 이동 30cm
    - `i` : 상승 30cm
    - `o` : 하강 30cm
  - 잘못된 입력 시 1초 대기 후 재입력 요청

- **멀티스레드 구조**
  - **`capture_thread`**: 드론 영상 캡처 → `frame_queue`에 적재
  - **`detection_thread`**: YOLO 탐지 및 crop 저장 작업 큐잉 → `detection_queue`, `save_queue`
  - **`control_thread`**: 키보드 입력을 통한 드론 조작 (`execute_commands`)
  - **`saver_thread`**: `save_worker`에서 crop 이미지 실제 저장
  - 각 큐는 `Queue` 로 구현, 오버플로 방지 로직 포함

---

## 사용된 파일 및 구조

- **`oss.py`**
  - `TelloYOLOController` 클래스 정의 및 실행 진입점
  - 주요 메서드:
    - `__init__`: 드론 연결, 모델 로드, 스레드/큐 초기화
    - `capture_frames`: 프레임 캡처 스레드
    - `process_detections`: YOLO 탐지 및 crop 저장 요청
    - `enqueue_crop_save`: crop 저장 작업 큐잉
    - `save_worker`: crop 이미지 실제 저장
    - `execute_commands`: 키보드 입력 기반 드론 조작
    - `run`: 메인 루프 (영상 표시 및 종료 처리)
    - `cleanup`: 스트림 종료, 착륙, 리소스 해제
    - `print_instructions`: 조작키 안내 로그 출력
    - `process_detection`: 단일 프레임에 대한 탐지/크롭 처리용 보조 함수

---

## 실행 환경 및 의존성

- **Python**
  - Python 3.8 이상 권장

- **필수 패키지**
  - `opencv-python`
  - `ultralytics` (YOLOv8)
  - `djitellopy`
  - `numpy`

- **기타**
  - DJI Tello 드론
  - 드론과 같은 네트워크(보통 Tello Wi-Fi)에 연결된 PC

### 설치 방법 예시

```bash
# 가상환경 생성 (선택)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install --upgrade pip

pip install opencv-python ultralytics djitellopy numpy
```

> `yolov8n.pt` 가 로컬에 없으면 `ultralytics` 가 자동으로 다운로드합니다.  
> 네트워크 환경에 따라 시간이 다소 걸릴 수 있습니다.

---

## 실행 방법

1. **Tello 전원 및 Wi-Fi 연결**
   - Tello 전원을 켜고, PC를 Tello Wi-Fi에 연결합니다.

2. **프로그램 실행**

```bash
python oss.py
```

3. **터미널에서 조작키 입력**
   - 프로그램이 시작되면 터미널에 `keyboard control activated:` 프롬프트가 표시됩니다.
   - 위의 조작키(`t`, `l`, `w`, `s`, `a`, `d`, `i`, `o`)를 입력하여 드론을 제어합니다.
   - 영상 창에서 `q` 키를 누르면 프로그램이 종료됩니다.

---

## 출력 데이터 구조

- **크롭 이미지 저장 경로**
  - 기본 루트: `runs/crops/`
  - 예시:
    - `runs/crops/person/20251124_153012_123_cls0_0.87_120x240.jpg`
- 파일명 규칙:
  - **`<타임스탬프>_cls<클래스ID>_<신뢰도>_<가로>x<세로>.jpg`**

---

## 주요 설정 변경 방법

`TelloYOLOController.__init__` 내부에서 기본값을 변경할 수 있습니다.

- **`self.min_confidence`**: 저장/표시할 최소 신뢰도 (기본 0.40)
- **`self.save_interval_sec`**: 프레임 간 최소 저장 간격 초 (기본 0.20)
- **`self.save_all_detections`**:
  - `False`: 프레임당 가장 큰 객체 1개만 저장
  - `True`: 프레임당 모든 후보 박스 저장
- **`self.crop_margin`**: 박스 주변으로 확장할 비율 (기본 0.05)

---

## 참고 자료

- **Ultralytics YOLOv8**: 설치 및 사용법, 모델 옵션 참고  
- **djitellopy**: Tello 드론 제어용 Python 라이브러리  
- **DJI Tello SDK 문서**: 드론 명령 세부 동작 참고

---

## 주의 사항

- 드론 비행 시 **실내/실외 안전**을 충분히 확보하고 사람/물체와의 충돌을 방지해야 합니다.
- YOLO 객체 탐지 성능은 조명, 거리, 모델 종류에 따라 달라질 수 있습니다.
- 장시간 실행 시 `runs/crops` 폴더의 용량이 커질 수 있으므로 주기적인 정리가 필요합니다.


