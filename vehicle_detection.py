from ultralytics import YOLO
import cv2
from pathlib import Path
from datetime import datetime
import csv
import time
import ctypes
import os

try:
    import winsound
except ImportError:
    winsound = None

try:
    MCI = ctypes.windll.winmm.mciSendStringA
except AttributeError:
    MCI = None


def load_model_with_recovery(weights_path: str) -> YOLO:
    try:
        return YOLO(weights_path)
    except RuntimeError as err:
        # Recover from partially downloaded/corrupted local .pt files.
        if "PytorchStreamReader failed reading zip archive" in str(err):
            weights_file = Path(weights_path)
            if weights_file.exists():
                weights_file.unlink()
            print(f"Corrupted weights removed: {weights_path}. Re-downloading...")
            return YOLO(weights_path)
        raise


def estimate_distance_meters(box_h: float, frame_w: int) -> float:
    # Approx pinhole estimate. Tuned for 640p-like dashcam footage.
    focal_px = 700.0 * (frame_w / 640.0)
    assumed_object_height_m = 1.6
    distance = (assumed_object_height_m * focal_px) / max(box_h, 1.0)
    return max(0.8, min(80.0, distance))


def is_imminent_collision(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    frame_w: int,
    frame_h: int,
    label: str,
) -> bool:
    # Emergency if a relevant object is large, centered, and low in the frame.
    if label not in {"car", "truck", "bus", "motorcycle", "bicycle", "person"}:
        return False

    box_w = max(x2 - x1, 1.0)
    box_h = max(y2 - y1, 1.0)
    area_ratio = (box_w * box_h) / max(frame_w * frame_h, 1.0)
    center_x = (x1 + x2) * 0.5
    bottom_y = y2

    in_lane_focus = frame_w * 0.20 <= center_x <= frame_w * 0.80
    near_bottom = bottom_y >= frame_h * 0.82
    very_large = area_ratio >= 0.15

    return in_lane_focus and near_bottom and very_large


def estimate_scene_motion(prev_gray, curr_gray) -> float:
    if prev_gray is None:
        return 0.0
    diff = cv2.absdiff(prev_gray, curr_gray)
    return float(diff.mean() / 255.0)


def find_best_previous_match(label: str, cx: float, cy: float, prev_objects: list[dict], used_ids: set[int]):
    best_idx = -1
    best_dist = 1e9
    for idx, obj in enumerate(prev_objects):
        if idx in used_ids or obj["label"] != label:
            continue
        dx = cx - obj["cx"]
        dy = cy - obj["cy"]
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    if best_idx == -1 or best_dist > 120:
        return None, best_dist
    return prev_objects[best_idx], best_dist


def risk_from_distance(distance_m: float) -> str:
    if distance_m < 5:
        return "high"
    if distance_m < 12:
        return "medium"
    return "low"


def action_from_label_and_risk(label: str, risk: str) -> str:
    # Pedestrians should not force a hard STOP unless they become an emergency-close hazard.
    if label == "person":
        if risk == "high":
            return "SLOW"
        return "GO"
    if risk == "high":
        return "STOP"
    if risk == "medium":
        return "SLOW"
    return "GO"


def priority_decision(actions: list[str]) -> str:
    if "STOP" in actions:
        return "STOP"
    if "SLOW" in actions:
        return "SLOW"
    return "GO"


def play_mp3_once(sound_path: Path):
    if MCI is None:
        return
    # Use native Windows MCI so mp3 playback works without extra packages.
    path_bytes = str(sound_path).encode("utf-8")
    MCI(b'close copilot_alert', None, 0, None)
    MCI(b'open "' + path_bytes + b'" type mpegvideo alias copilot_alert', None, 0, None)
    MCI(b'play copilot_alert from 0', None, 0, None)


def beep_for_decision(decision: str, last_beep_at: float, now: float, sound_path: Path | None) -> float:
    if now - last_beep_at < 0.8:
        return last_beep_at

    if decision not in {"STOP", "SLOW"}:
        return last_beep_at

    if sound_path and sound_path.exists():
        play_mp3_once(sound_path)
        return now

    if winsound:
        if decision == "STOP":
            winsound.Beep(1400, 220)
        else:
            winsound.Beep(900, 120)
    return now


def draw_dashboard(frame, fps: float, decision: str, counts: dict[str, int], nearest_text: str, alert_text: str):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (min(520, w - 10), 180), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    decision_color = {
        "STOP": (0, 0, 255),
        "SLOW": (0, 200, 255),
        "GO": (0, 255, 0),
    }.get(decision, (255, 255, 255))

    cv2.putText(frame, f"Decision: {decision}", (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.85, decision_color, 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (24, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Nearest: {nearest_text}", (24, 104), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (230, 230, 230), 2)
    cv2.putText(frame, f"Objects: {counts}", (24, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (210, 210, 210), 1)
    cv2.putText(frame, "ESC to exit", (24, 164), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)

    # High-visibility center alert message.
    center_overlay = frame.copy()
    cv2.rectangle(center_overlay, (30, h - 120), (w - 30, h - 35), (10, 10, 10), -1)
    cv2.addWeighted(center_overlay, 0.45, frame, 0.55, 0, frame)
    cv2.putText(frame, alert_text, (50, h - 68), cv2.FONT_HERSHEY_SIMPLEX, 1.05, decision_color, 3)

# Load YOLO model (auto-downloads if not present)
model = load_model_with_recovery("yolov8n.pt")

# Use webcam (0) OR replace with another path.
cap = cv2.VideoCapture("road.mp4")
if not cap.isOpened():
    raise RuntimeError("Unable to open video source: road.mp4")

frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
video_fps = cap.get(cv2.CAP_PROP_FPS)
video_fps = video_fps if video_fps and video_fps > 1 else 30.0

outputs_dir = Path("outputs")
outputs_dir.mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_video_path = outputs_dir / f"vehicle_overlay_{stamp}.mp4"
output_log_path = outputs_dir / f"detection_log_{stamp}.csv"

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(str(output_video_path), fourcc, video_fps, (frame_w, frame_h))

filtered_classes = {"person", "car", "truck", "bus", "motorcycle", "bicycle"}
too_close_threshold_m = 0.6
alert_sound_file = Path("dragon-studio-censor-beep-1-372459 (1).mp3")

last_time = time.time()
last_beep_at = 0.0
frame_id = 0
prev_gray = None
prev_objects: list[dict] = []
stationary_streak = 0
hazard_streak = 0

with output_log_path.open("w", newline="", encoding="utf-8") as log_file:
    logger = csv.writer(log_file)
    logger.writerow([
        "timestamp",
        "frame_id",
        "label",
        "confidence",
        "distance_m",
        "risk",
        "object_action",
        "final_decision",
    ])

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_id += 1
        now = time.time()
        dt = max(now - last_time, 1e-6)
        last_time = now
        fps = 1.0 / dt
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        scene_motion = estimate_scene_motion(prev_gray, gray)

        results = model(frame, verbose=False)
        annotated_frame = results[0].plot()

        object_actions: list[str] = []
        counts: dict[str, int] = {}
        nearest_distance = 999.0
        nearest_label = "none"
        nearest_motion_px = 0.0
        nearest_distance_delta = 0.0
        rows_to_log = []
        current_objects: list[dict] = []
        used_prev_ids: set[int] = set()
        any_imminent = False
        any_closing_fast = False
        moving_count = 0

        for box in results[0].boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            if label not in filtered_classes:
                continue

            confidence = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx = (x1 + x2) * 0.5
            cy = (y1 + y2) * 0.5
            area = max((x2 - x1) * (y2 - y1), 1.0)
            box_h = max(y2 - y1, 1.0)
            distance_m = estimate_distance_meters(box_h, frame_w)
            prev_match, motion_px = find_best_previous_match(label, cx, cy, prev_objects, used_prev_ids)
            if prev_match:
                used_prev_ids.add(prev_match["idx"])

            area_growth = 0.0
            distance_delta = 0.0
            if prev_match:
                area_growth = (area - prev_match["area"]) / max(prev_match["area"], 1.0)
                distance_delta = prev_match["distance_m"] - distance_m

            is_moving_obj = motion_px > 6.0 or abs(area_growth) > 0.12 or distance_delta > 0.7
            if is_moving_obj:
                moving_count += 1

            risk = risk_from_distance(distance_m)
            action = action_from_label_and_risk(label, risk)
            object_actions.append(action)
            counts[label] = counts.get(label, 0) + 1

            imminent = is_imminent_collision(x1, y1, x2, y2, frame_w, frame_h, label)
            if imminent:
                any_imminent = True

            if distance_delta > 0.9:
                any_closing_fast = True

            rows_to_log.append((label, confidence, distance_m, risk, action, motion_px, distance_delta, imminent))
            current_objects.append({
                "label": label,
                "cx": cx,
                "cy": cy,
                "area": area,
                "distance_m": distance_m,
            })

            if distance_m < nearest_distance:
                nearest_distance = distance_m
                nearest_label = label
                nearest_motion_px = motion_px
                nearest_distance_delta = distance_delta

            if imminent:
                nearest_distance = min(nearest_distance, 0.6)
                nearest_label = label

            risk_color = {
                "high": (0, 0, 255),
                "medium": (0, 200, 255),
                "low": (0, 255, 0),
            }[risk]

            cv2.putText(
                annotated_frame,
                f"{label} {distance_m:.1f}m {risk}",
                (int(x1), max(20, int(y1) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                risk_color,
                2,
            )

        # Priority-based global decision from all filtered objects.
        final_decision = priority_decision(object_actions)

        # Emergency override when objects are too close and motion indicates collision risk.
        too_close = nearest_distance <= too_close_threshold_m
        total_objects = max(sum(counts.values()), 1)
        moving_ratio = moving_count / total_objects
        scene_stationary = scene_motion < 0.014
        mostly_stopped_objects = moving_ratio <= 0.30
        stopped_traffic_now = (
            too_close
            and mostly_stopped_objects
            and scene_stationary
            and not any_closing_fast
        )

        # Debounce states across frames to avoid jitter flips near traffic lights.
        if stopped_traffic_now:
            stationary_streak += 1
        else:
            stationary_streak = 0

        hazard_now = too_close and (
            any_closing_fast
            or (any_imminent and not scene_stationary)
            or moving_ratio > 0.45
        )
        if hazard_now:
            hazard_streak += 1
        else:
            hazard_streak = max(0, hazard_streak - 1)

        stopped_traffic = stationary_streak >= 8
        confirmed_hazard = hazard_streak >= 2
        has_vehicles = "car" in counts or "truck" in counts or "bus" in counts or "motorcycle" in counts
        only_stationary_persons = (
            "person" in counts
            and not has_vehicles
            and scene_stationary
            and moving_count <= 1
            and not any_closing_fast
        )

        if too_close and confirmed_hazard and not stopped_traffic:
            final_decision = "STOP"
            alert_text = "EMERGENCY STOP: OBJECT TOO CLOSE"
        elif stopped_traffic:
            final_decision = "SLOW"
            alert_text = "TRAFFIC WAIT: VEHICLES STOPPED"
        elif only_stationary_persons:
            final_decision = "GO"
            alert_text = "CLEAR: GO (pedestrian nearby)"
        elif too_close and any_imminent and scene_stationary:
            final_decision = "SLOW"
            alert_text = "CAUTION: CLOSE QUEUE AHEAD"
        elif final_decision == "STOP":
            alert_text = "ALERT: STOP"
        elif final_decision == "SLOW":
            alert_text = "CAUTION: SLOW DOWN"
        else:
            alert_text = "CLEAR: GO"

        # Motion gating for beep:
        # 1) Dashcam context must be moving, 2) nearest object must be moving,
        # 3) nearest object is either approaching OR passing close from behind/side.
        dashcam_is_moving = not scene_stationary
        nearest_object_is_moving = nearest_motion_px > 4.0
        nearest_object_approaching = nearest_distance_delta > 0.35
        nearest_object_passing_close = too_close and nearest_motion_px > 8.0

        # If both scene and nearest object are stationary, explicitly suppress beep.
        both_stationary = (
            scene_stationary
            and (not nearest_object_is_moving)
            and mostly_stopped_objects
        )

        # Only beep on true confirmed emergencies with strict motion context.
        # Beep if approaching OR if passing very close with high motion (from any direction).
        if (
            too_close
            and confirmed_hazard
            and not stopped_traffic
            and not only_stationary_persons
            and dashcam_is_moving
            and nearest_object_is_moving
            and (nearest_object_approaching or nearest_object_passing_close)
            and not both_stationary
        ):
            last_beep_at = beep_for_decision("STOP", last_beep_at, now, alert_sound_file)

        nearest_text = (
            f"{nearest_label} @ {nearest_distance:.1f}m | M:{scene_motion:.3f} | mv:{moving_ratio:.2f}"
            if nearest_label != "none"
            else f"none | M:{scene_motion:.3f}"
        )
        draw_dashboard(annotated_frame, fps, final_decision, counts, nearest_text, alert_text)

        for label, confidence, distance_m, risk, action, motion_px, distance_delta, imminent in rows_to_log:
            logger.writerow([
                datetime.now().isoformat(timespec="milliseconds"),
                frame_id,
                label,
                f"{confidence:.3f}",
                f"{distance_m:.2f}",
                risk,
                action,
                final_decision,
            ])

            cv2.putText(
                annotated_frame,
                f"v:{motion_px:.1f}px dz:{distance_delta:.2f}m",
                (20, frame_h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (180, 180, 180) if not imminent else (0, 0, 255),
                1,
            )

        writer.write(annotated_frame)
        if os.environ.get('DISPLAY') or os.name == 'nt':
            try:
                cv2.imshow("Vehicle Automation Dashboard", annotated_frame)
                if cv2.waitKey(1) == 27:
                    break
            except Exception:
                pass

        prev_gray = gray
        prev_objects = []
        for i, obj in enumerate(current_objects):
            obj["idx"] = i
            prev_objects.append(obj)

cap.release()
writer.release()
if os.environ.get('DISPLAY') or os.name == 'nt':
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

print(f"Saved output video: {output_video_path}")
print(f"Saved detection log: {output_log_path}")