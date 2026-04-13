import cv2
import mediapipe as mp
import math
import time
from collections import deque

# 恢复成最干净、最官方的写法！
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# ==========================================
# ⚙️ 核心参数配置区
# ==========================================
MIN_DIST = 30
MAX_DIST = 200

PWM_CLOSE = 1500
PWM_OPEN = 600

FILTER_SIZE = 5
DEAD_ZONE_PWM = 30
PRINT_INTERVAL = 0.1

# ==========================================
# 👁️ AI 视觉与算法初始化
# ==========================================
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

cap = cv2.VideoCapture(0)

dist_history = deque(maxlen=FILTER_SIZE)
last_simulated_pwm = 0
last_print_time = 0

print("========================================")
print("🚀 纯软件视觉逻辑测试已启动！")
print("请将手伸入画面。按 'q' 键退出。")
print("========================================")

while cap.isOpened():
    success, img = cap.read()
    if not success:
        print("无法获取摄像头画面，请检查权限！")
        break

    img = cv2.flip(img, 1)
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(imgRGB)

    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(img, handLms, mp_hands.HAND_CONNECTIONS)
            h, w, c = img.shape

            tx, ty = int(handLms.landmark[4].x * w), int(handLms.landmark[4].y * h)
            ix, iy = int(handLms.landmark[8].x * w), int(handLms.landmark[8].y * h)

            cv2.circle(img, (tx, ty), 10, (255, 0, 0), cv2.FILLED)
            cv2.circle(img, (ix, iy), 10, (0, 0, 255), cv2.FILLED)
            cv2.line(img, (tx, ty), (ix, iy), (0, 255, 0), 3)

            # ----------------------------------------
            # 🧠 逻辑 1：计算与滤波
            # ----------------------------------------
            raw_dist = math.hypot(ix - tx, iy - ty)
            dist_history.append(raw_dist)
            smooth_dist = sum(dist_history) / len(dist_history)

            # ----------------------------------------
            # 🧠 逻辑 2：线性映射与死区限幅
            # ----------------------------------------
            ratio = (smooth_dist - MIN_DIST) / (MAX_DIST - MIN_DIST)
            ratio = max(0.0, min(1.0, ratio))

            target_pwm = int(PWM_CLOSE - ratio * (PWM_CLOSE - PWM_OPEN))

            cv2.putText(img, f'Raw Dist: {int(raw_dist)}', (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
            cv2.putText(img, f'Smooth Dist: {int(smooth_dist)}', (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(img, f'Mapped PWM: {target_pwm}', (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 0), 2)

            # ----------------------------------------
            # 🧠 逻辑 3：模拟下发指令
            # ----------------------------------------
            current_time = time.time()
            if (current_time - last_print_time > PRINT_INTERVAL) and (
                    abs(target_pwm - last_simulated_pwm) > DEAD_ZONE_PWM):
                print(
                    f"[视觉指令触发] 拇指:({tx},{ty}) | 食指:({ix},{iy}) | 滤波距离: {int(smooth_dist):3d}px => 目标PWM: {target_pwm}")
                last_simulated_pwm = target_pwm
                last_print_time = current_time

    cv2.imshow("Software Logic Test", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("测试结束。")