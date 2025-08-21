#******************* 使用说明 *****************************
#初始状态下为 NORMAL 短按 --> DELAY --> MARK
#MARK模式下会旋转一定角度 防止在原位误识别
#支持两种方式设置模板
#1、直接将目标人物放在摄像头前
#2、长按进入设置人物模式
#3、在1中设置好目标人物后可以长按切换下一个（按索引）
#MARK 短按 --> DELAY --> DANGER_DETECT
#DANGER_DETECT 将模板控制在画面中心 发射激光
#DANGER_DETECT --> DELAY --> NORMAL
#*********************************************************
import time
import sensor
import image
from image import SEARCH_EX
import pyb
from pyb import Servo,Pin


# ******************** 硬件初始化配置 ********************
sensor.reset()
sensor.set_contrast(2)
sensor.set_gainceiling(16)
sensor.set_framesize(sensor.QVGA)
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_auto_gain(True)
sensor.set_auto_whitebal(True)

# ******************** 用户可配置参数 ********************
TEMPLATE_PATHS = ["0.pgm", "1.pgm", "2.pgm"]
MATCH_THRESHOLD = 0.7
SEARCH_STEP = 6
NORMAL_COLOR = 255      # 正常模板框颜色
DANGER_COLOR = 0        # 危险模板框颜色
TEXT_OFFSET = 5         # 文本偏移
DELAY_TIME = 3000       # 3秒延迟（毫秒）

# ******************** 引脚配置 ********************
KEY_PIN = 'P0'          # 按键引脚
BUZZER_PIN = 'P1'       # 蜂鸣器引脚

#---------------------------------------------------
PAN_SERVO_CH = 1                  # 水平舵机通道
TILT_SERVO_CH = 2                 # 垂直舵机通道
KP_PAN = 0.05                    # 水平方向比例系数
KP_TILT = 0.05                  # 垂直方向比例系数
DEAD_ZONE = 5                    # 控制死区（像素）
MAX_SERVO_DELTA = 3              # 每次最大调整角度
CONFIRM_NUM = 5
# 图像中心坐标 (QVGA: 320x240)
img_center_x = 175
img_center_y = 110
# ******************** 系统状态机 ********************
class SystemState:
    NORMAL = 0          # 默认状态，正常识别
    DELAY_BEFORE_DANGER = 1 # 按键后延迟3秒，准备设置危险模板
    MARK_DANGER = 2         # 此处是标记状态 ---------更改
    DELAY_BEFORE_DETECTION = 3
    DANGER_DETECTION = 4    # 危险检测模式
    DELAY_BEFORE_NORMAL = 5 # 准备切换回正常模式


    # 状态描述映射
    DESCRIPTIONS = {
        NORMAL: "NORMAL",
        DELAY_BEFORE_DANGER: "DELAY",
        MARK_DANGER: "MARK",#---------更改
        DELAY_BEFORE_DETECTION: "DELAY",
        DANGER_DETECTION: "DANGER",
        DELAY_BEFORE_NORMAL: "DELAY"
    }

# ******************** 系统控制器 ********************
class SafetySystem:
    def __init__(self):
        self.current_state = SystemState.NORMAL
        self.state_changed = True  # 状态变化标志
        self.danger_template = None  # 危险模板

        self.templates = self.load_templates()
        print("系统初始化完成 -", self.state_description())

        self.state_start_time = time.ticks_ms()
        self.last_buzzer_time = time.ticks_ms()
        self.last_print_time = time.ticks_ms()
        self.buzzer_state = 1  # 初始关闭

        self.safe_count = 0

        self.mark_confirm_count = 0
        self.mark_candidate = None
        self.isdanger = False

        self.danger_confirm_count = 0

        self.index = 0

        self.center_counter = 0
        self.CENTER_GPIO_STATE = False
    def load_templates(self):
        """加载所有模板文件"""
        templates = []
        for path in TEMPLATE_PATHS:
            try:
                # 预处理模板图像
                template_img = image.Image(path)
                template_img = template_img.gaussian(3)  # 高斯模·糊降噪
                name = path.split(".")[0]
                template = {
                    "image": template_img,
                    "name": name,
                    "path": path
                }
                templates.append(template)
                print(f"预加载模板: {name}")
            except Exception as e:
                print(f"模板加载失败: {path} ({str(e)})")
        return templates

    def state_description(self):
        """获取当前状态描述"""
        return SystemState.DESCRIPTIONS.get(self.current_state, "未知状态")

    def update_state(self, key_pressed):
        """根据按键和状态更新时间逻辑"""
        current_time = time.ticks_ms()
        state_time = time.ticks_diff(current_time, self.state_start_time)

        # 状态转移逻辑
        if self.current_state == SystemState.NORMAL:
            if key_pressed:
                self.current_state = SystemState.DELAY_BEFORE_DANGER
                self.state_start_time = current_time
                print("进入状态:", self.state_description())

        elif self.current_state == SystemState.DELAY_BEFORE_DANGER:
            self.danger_template = None
            if state_time >= DELAY_TIME:
                self.current_state = SystemState.MARK_DANGER
                self.state_start_time = current_time
                print("进入状态:", self.state_description())

# ---------------------------- 更改 -----------------------------------
        elif self.current_state == SystemState.MARK_DANGER:
            if key_pressed and self.danger_template:
                self.current_state = SystemState.DELAY_BEFORE_DETECTION
                self.state_start_time = current_time
                print("进入状态:", self.state_description())
            elif key_pressed:
                print("请先标注危险人物！")#如果未标注 不切换状态

        elif self.current_state == SystemState.DELAY_BEFORE_DETECTION:
            pan_servo.angle(0)
            if state_time >= DELAY_TIME:
                self.current_state = SystemState.DANGER_DETECTION
                self.state_start_time = current_time
                print("进入状态:", self.state_description())

        elif self.current_state == SystemState.DANGER_DETECTION:
            if key_pressed:
                self.current_state = SystemState.DELAY_BEFORE_NORMAL
                self.state_start_time = current_time
                print("进入状态:", self.state_description())

        elif self.current_state == SystemState.DELAY_BEFORE_NORMAL:
            pan_servo.angle(0)
            tilt_servo.angle(0)
            gpio.low()
            if state_time >= DELAY_TIME:
                self.current_state = SystemState.NORMAL
                self.danger_template = None
                self.state_start_time = current_time
                self.isdanger = False
                print("进入状态:", self.state_description())
                print("警报解除")

    def run_danger_detection(self, img):
        current_time = time.ticks_ms()
        danger_detected = False
        danger_confirmed = False
        target_cx, target_cy = None, None

        for template in self.templates:
            result = img.find_template(
                template["image"],
                MATCH_THRESHOLD,
                step=SEARCH_STEP,
                search=SEARCH_EX
            )

            if result:
                x, y, w, h = result
                center_x, center_y = x + w//2, y + h//2

                is_danger = self.danger_template == template["name"]
                color = DANGER_COLOR if is_danger else NORMAL_COLOR
                thickness = 3 if is_danger else 1
                mark_size = 7 if is_danger else 3

                img.draw_rectangle(result, color=color, thickness=thickness)
                text_y = y - TEXT_OFFSET if y > TEXT_OFFSET else 0
                img.draw_string(x, text_y, template["name"],
                               color=color, scale=1.2 if is_danger else 1)
                img.draw_cross(center_x, center_y, color=color, size=mark_size)

                if is_danger:
                    danger_detected = True
                    target_cx, target_cy = center_x, center_y

        if danger_detected and self.danger_confirm_count < CONFIRM_NUM :
            self.danger_confirm_count += 1
        elif danger_detected and self.danger_confirm_count == CONFIRM_NUM :
            self.danger_confirm_count = CONFIRM_NUM
        else:
            self.danger_confirm_count = 0

        img.draw_string(5, 35,
            f"confirm:{self.danger_confirm_count}/{CONFIRM_NUM}",
            color=NORMAL_COLOR
        )

        danger_confirmed = self.danger_confirm_count >= CONFIRM_NUM

        if not danger_confirmed and current_time - self.last_print_time > 1000:
            self.safe_count += 1
            print(f"[SAFE] {self.safe_count} - 未检测到危险模板")
            self.last_print_time = current_time

        if danger_confirmed and target_cx is not None:
            print(target_cx, target_cy)
            self.stabilize_target(target_cx, target_cy)
            self.check_center(target_cx - img_center_x , target_cy - img_center_y)

            # 每 500ms 翻转蜂鸣器和输出危险模板
            if time.ticks_diff(current_time, self.last_buzzer_time) > 500:
                self.buzzer_state ^= 1  # 翻转 0/1
                buzzer.value(self.buzzer_state)
                self.last_buzzer_time = current_time
                print(f"[WARNING!] 检测到危险模板: {self.danger_template}")

        else:
            buzzer.value(1)

        return danger_confirmed


    #---------------------------------------------------------------------------

    def run_normal_detection(self, img):
        # 检测所有模板
        for template in self.templates:
            result = img.find_template(
                template["image"],
                MATCH_THRESHOLD,
                step=SEARCH_STEP,
                search=SEARCH_EX
            )

            if result:
                # 解包匹配结果
                x, y, w, h = result
                center_x, center_y = x + w//2, y + h//2

                color =  NORMAL_COLOR
                thickness = 1
                mark_size = 3

                # 绘制矩形框
                img.draw_rectangle(result, color=color, thickness=thickness)

                # 绘制模板名称
                text_y = y - TEXT_OFFSET if y > TEXT_OFFSET else 0
                img.draw_string(x, text_y, template["name"],
                               color=color, scale=1)

                # 绘制中心点标记
                img.draw_cross(center_x, center_y, color=color, size=mark_size)


    def run_markmode(self, img , key_longpressed):
        pan_servo.angle(-55)
        # 等待1秒后才允许开始计数
        if time.ticks_diff(time.ticks_ms(), self.state_start_time) < 1000:
            img.draw_string(5, 35, "WAIT STABLE...", color=NORMAL_COLOR)
            self.mark_confirm_count = 0
            self.mark_candidate = None
            return
        img.draw_string(5,35,f"CONFIRM_NUM:{self.mark_confirm_count}", color=NORMAL_COLOR)
        for template in self.templates:
            result = img.find_template(
                template["image"],
                MATCH_THRESHOLD,
                step=SEARCH_STEP,
                search=SEARCH_EX
            )

            if result:
                x, y, w, h = result
                center_x, center_y = x + w//2, y + h//2

                color = NORMAL_COLOR
                thickness = 1
                mark_size = 3

                img.draw_rectangle(result, color=color, thickness=thickness)
                text_y = y - TEXT_OFFSET if y > TEXT_OFFSET else 0
                img.draw_string(x, text_y, template["name"],
                               color=color, scale=1)
                img.draw_cross(center_x, center_y, color=color, size=mark_size)
                if self.mark_candidate == template["name"]:
                    self.mark_confirm_count += 1
                else:
                    self.mark_candidate = template["name"]
                    self.mark_confirm_count = 1


                # 连续5帧检测到同一个模板 -> 确认危险模板
                if self.mark_confirm_count >= CONFIRM_NUM:
                    self.danger_template = self.mark_candidate
                    self.isdanger = True
                    print(f"[确认] 设置危险模板: {self.danger_template}")
                    self.mark_confirm_count = 0
                    self.mark_candidate = None
                    self.index = self.templates.index(template)
                break

        if key_longpressed and not self.isdanger :
            print("长按切换人物模式")
            self.index = 0
            self.danger_template = self.templates[self.index]["name"]
            self.isdanger = True
            print(f"[确认]设置危险模板: {self.danger_template}")
        elif key_longpressed and self.isdanger:
            self.index =( self.index + 1 ) % len(self.templates)
            self.danger_template = self.templates[self.index]["name"]
            print(f"切换到危险模板: {self.danger_template}")



    #---------------------------------------------------------------------------
    def draw_state_info(self, img):
        """绘制系统状态信息"""
        # 状态描述
        state_desc = self.state_description()
        img.draw_string(5, 5, f"STATE:{state_desc}", color=NORMAL_COLOR)

        # 危险模板信息
        if self.danger_template:
            img.draw_string(5, 20, f"TRACK:{self.danger_template}", color=DANGER_COLOR)

        # 倒计时显示（当处于延迟状态时）
        current_time = time.ticks_ms()
        state_time = time.ticks_diff(current_time, self.state_start_time)

        if self.current_state in [SystemState.DELAY_BEFORE_DANGER,SystemState.DELAY_BEFORE_DETECTION,SystemState.DELAY_BEFORE_NORMAL]:
            remaining = max(0, DELAY_TIME - state_time) / 1000
            img.draw_string(img.width()//2-20, img.height()//2-10,
                           f"{remaining:.1f}s", color=NORMAL_COLOR)
#------------------------------------------------------------------------------
    def stabilize_target(self, cx, cy):
        """云台控制：将目标稳定在画面中央"""
        global current_pan, current_tilt

        # 计算目标位置与画面中心的偏差
        dx = cx - img_center_x
        dy = cy - img_center_y

        # 限制最大偏差避免过大调整
        dx = max(-img_center_x, min(img_center_x, dx))
        dy = max(-img_center_y, min(img_center_y, dy))

        # 死区处理（目标在中心附近时不调整）
        if abs(dx) > DEAD_ZONE:
            # 计算需要调整的水平角度（比例控制）
            delta_angle =  - dx * KP_PAN

            # 限制单次最大调整角度
            delta_angle = max(-MAX_SERVO_DELTA, min(MAX_SERVO_DELTA, delta_angle))

            # 更新水平角度
            new_pan = current_pan + delta_angle

            # 限制舵机角度范围（-90-90度）
            new_pan = max(-90, min(90, new_pan))

            # 应用新角度并更新记录
            if new_pan != current_pan:
                pan_servo.angle(int(new_pan))
                current_pan = new_pan

        if abs(dy) > DEAD_ZONE:
            # 计算需要调整的垂直角度（注意方向）
            delta_angle = - dy * KP_TILT

            # 限制单次最大调整角度
            delta_angle = max(-MAX_SERVO_DELTA, min(MAX_SERVO_DELTA, delta_angle))

            # 更新垂直角度（注意方向关系）
            new_tilt = current_tilt + delta_angle

            # 限制舵机角度范围（-90-90度）
            new_tilt = max(-90, min(90, new_tilt))

            # 应用新角度并更新记录
            if new_tilt != current_tilt:
                tilt_servo.angle(int(new_tilt))
                current_tilt = new_tilt


    def check_center(self, dx, dy):
        # 判断是否在中心区域
        centered = abs(dx) <= DEAD_ZONE and abs(dy) <= DEAD_ZONE

        if centered:
            self.center_counter += 1   # 连续居中帧数+1
        else:
            self.center_counter = 0    # 一旦不居中，计数清零

        # 当连续 CENTER_CONSECUTIVE_FRAMES 帧都居中，并且 GPIO 还没点亮
        if self.center_counter >= CONFIRM_NUM and not self.CENTER_GPIO_STATE:
            gpio.high()            # 点灯（输出高电平）
            self.CENTER_GPIO_STATE = True
        # 如果偏离中心，并且灯还亮着 -> 熄灭
        elif not centered and self.CENTER_GPIO_STATE:
            gpio.low()
            self.CENTER_GPIO_STATE = False

        return centered

# ******************** 初始化系统 ********************
# 初始化按键
key = pyb.Pin(KEY_PIN, pyb.Pin.IN, pyb.Pin.PULL_UP)
last_press_time = 0
debounce_delay = 300  # 按键消抖时间
long_press_time = 1000 #长按识别时间
press_start_time = 0 #按键按下时间
# 按键处理
key_pressed = False
key_was_pressed = False
key_longpressed = False


# 初始化蜂鸣器
buzzer = pyb.Pin(BUZZER_PIN, pyb.Pin.OUT_PP)
buzzer.value(1)  # 初始关闭

#初始化激光笔
gpio = Pin("P2", Pin.OUT_PP)
gpio.low()

# 创建安全系统
safety_system = SafetySystem()
clock = time.clock()

pan_servo = Servo(PAN_SERVO_CH)   # 水平舵机
tilt_servo = Servo(TILT_SERVO_CH) # 垂直舵机
pan_servo.angle(0)
tilt_servo.angle(0)
current_pan = 0                 # 记录当前水平角度
current_tilt = 0                # 记录当前垂直角度

# ******************** 主处理循环 ********************
while True:
    clock.tick()
    img = sensor.snapshot().lens_corr()
    current_time = time.ticks_ms()


    if key.value() == 0 and not key_was_pressed and current_time - last_press_time > debounce_delay:
        # 按下
        key_was_pressed = True
        press_start_time = current_time
        last_press_time = current_time
        print("按键按下")

    elif key.value() == 1 and key_was_pressed and current_time - last_press_time > debounce_delay:
        # 松开
        press_duration = current_time - press_start_time
        if press_duration >= long_press_time:
            print("长按")
            key_longpressed = True
        else:
            print("短按")
            key_pressed = True
        key_was_pressed = False
        last_press_time = current_time



    # 更新系统状态
    safety_system.update_state(key_pressed)

    # 根据状态执行不同处理
    if safety_system.current_state == SystemState.DANGER_DETECTION:
        safety_system.run_danger_detection(img)
    elif safety_system.current_state == SystemState.NORMAL:
        safety_system.run_normal_detection(img)
        buzzer.value(1)  # 确保蜂鸣器关闭
    elif safety_system.current_state == SystemState.MARK_DANGER:
        safety_system.run_markmode(img,key_longpressed)
        buzzer.value(1)# 确保蜂鸣器关闭
    else:
        buzzer.value(1)  # 确保蜂鸣器关闭

    key_pressed = False
    key_longpressed = False


    # 绘制系统状态信息
    safety_system.draw_state_info(img)

    # 显示帧率
    fps = clock.fps()
    img.draw_string(img.width()-72, 5, f"FPS:{fps:.1f}", color=NORMAL_COLOR)
