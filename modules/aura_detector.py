import requests, cv2, time, os, json, pyautogui, pygetwindow
import numpy as np
from datetime import datetime
from PIL import ImageGrab

class AuraDetector:
    def __init__(self, aura_config_path=None, config_path=None):
        if aura_config_path is None:
            aura_config_path = os.path.join(os.path.dirname(__file__), "auras.json")
            
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        
        with open(aura_config_path, "r") as file:
            self.auras = json.load(file)
            
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            self.webhook_url = config.get("WebhookLink")
            self.webhook_userid = config.get("WebhookUserID")
            self.roll_ping_minimum = config.get("WebhookRollPingMinimum", 100000)
            self.roll_send_minimum = config.get("WebhookRollSendMinimum", 10000)

        # Convert colors to numpy for easier detect
        for rarity in self.auras.values():
            for aura in rarity.values():
                aura["color"] = np.array(aura["color"])

        # Load star shape reference images
        images_dir = os.path.join(os.path.dirname(__file__), "../images/Stars_Ref")
        self.star_ref_4_corner = [
            cv2.imread(os.path.join(images_dir, "4_corner_star.png"), cv2.IMREAD_GRAYSCALE),
            cv2.imread(os.path.join(images_dir, "4_corner_star_2.png"), cv2.IMREAD_GRAYSCALE)
        ]
        
        self.star_refs_8_corner = [
            cv2.imread(os.path.join(images_dir, "8_corner_star.png"), cv2.IMREAD_GRAYSCALE),
            cv2.imread(os.path.join(images_dir, "8_corner_star_2.png"), cv2.IMREAD_GRAYSCALE)
        ]

        if any(ref is None for ref in self.star_ref_4_corner) or any(ref is None for ref in self.star_refs_8_corner):
            raise FileNotFoundError("Star reference images not found in 'images/Stars_Ref' folder. Try putting your own star as reference.")

        self.previous_aura_name = None
        self.last_detection_time = 0
        self.ignored_4_corner_count = 0
        self.max_ignored_threshold = 2
        
    def rgb_to_hex(self, rgb):
        return int("{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2]), 16)
        
    def send_webhook(self, aura_name, rarity_value, image_path, rgb_color=None, aura_img=None):
        if rgb_color is None:
            # color: 0x5B4E9F
            rgb_color = [91, 78, 159]  # Fallback 
        
        if aura_img is None:
            aura_img = ""

        embed = {
            "title": f"# You rolled {aura_name}!",
            "description": f"** 1/{rarity_value} **",
            "color": self.rgb_to_hex(rgb_color),
            "image": {"url": aura_img},
            "thumbnail": {"url": f"attachment://{os.path.basename(image_path)}"},
        }

        # Determine whether to ping based on rarity
        content = None
        if rarity_value >= self.roll_ping_minimum and self.webhook_userid != '':
            content = f"<@{self.webhook_userid}>"

        with open(image_path, "rb") as f:
            files = {"file": (os.path.basename(image_path), f, "image/png")}
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content

            response = requests.post(self.webhook_url, data={"payload_json": json.dumps(payload)}, files=files)
            if response.status_code != 204 and response.status_code != 200:
                print(f"Error: {response.text}")
            else:
                print("Webhook sent successfully.")

    def rgb_distance(self, color1, color2):
        return np.linalg.norm(np.array(color1) - np.array(color2))

    def hsv_distance(self, hsv1, hsv2):
        hsv1 = hsv1.astype(int)
        hsv2 = hsv2.astype(int)

        dh = min(abs(hsv1[0] - hsv2[0]), 180 - abs(hsv1[0] - hsv2[0])) / 180.0
        ds = abs(hsv1[1] - hsv2[1]) / 255.0
        dv = abs(hsv1[2] - hsv2[2]) / 255.0
        return np.sqrt(dh**2 + ds**2 + dv**2) * 255


    def is_pure_black_background(self, image, bbox):
        x, y, w, h = bbox
        tolerance = 5 
        corners = [
            image[y, x - 10],  
            image[y, x + w - 10],
            image[y + h - 10, x],  
            image[y + h - 10, x + w - 10]
        ]
        for corner in corners:
            if not np.all(corner < tolerance):
                return False
        return True

    def detect_star_shape(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect 4-corner star
        max_confidence_4 = 0
        best_4_corner_bbox = None
        for star_ref in self.star_ref_4_corner:
            res_4_corner = cv2.matchTemplate(gray, star_ref, cv2.TM_CCOEFF_NORMED)
            loc_4 = np.where(res_4_corner >= 0.75)
            confidence_4 = np.max(res_4_corner) if len(loc_4[0]) > 0 else 0

            if confidence_4 > max_confidence_4:
                max_confidence_4 = confidence_4
                for pt in zip(*loc_4[::-1]):
                    bbox = (pt[0], pt[1], star_ref.shape[1], star_ref.shape[0])
                    if self.is_pure_black_background(image, bbox):
                        self.ignored_4_corner_count = 0
                        best_4_corner_bbox = bbox
                        break
                else:
                    self.ignored_4_corner_count += 1

        # Detect 8-corner star
        max_confidence_8 = 0
        best_8_corner_bbox = None
        for star_ref in self.star_refs_8_corner:
            res_8_corner = cv2.matchTemplate(gray, star_ref, cv2.TM_CCOEFF_NORMED)
            loc_8 = np.where(res_8_corner >= 0.75)
            confidence_8 = np.max(res_8_corner) if len(loc_8[0]) > 0 else 0

            if confidence_8 > max_confidence_8:
                max_confidence_8 = confidence_8
                for pt in zip(*loc_8[::-1]):
                    best_8_corner_bbox = (pt[0], pt[1], star_ref.shape[1], star_ref.shape[0])

        if self.ignored_4_corner_count >= self.max_ignored_threshold:
            if max_confidence_8 >= 0.75:
                return best_8_corner_bbox, "8_corners"
            return None, None

        if max_confidence_8 > max_confidence_4 and max_confidence_8 >= 0.75:
            return best_8_corner_bbox, "8_corners"
        elif max_confidence_4 >= 0.75 and best_4_corner_bbox is not None:
            return best_4_corner_bbox, "4_corners"
        return None, None

    def adjust_brightness(self, image, factor=1):
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hsv_image[:, :, 2] = np.clip(hsv_image[:, :, 2] * factor, 0, 255).astype(np.uint8)
        return cv2.cvtColor(hsv_image, cv2.COLOR_HSV2BGR)

    # Get the Roblox window size and return rX as roblox window position, rY as roblox window position and rW as roblox window width, rH as roblox window height
    def getRobloxWindowSize(self):
        window_list = pyautogui.getAllTitles()
        for window in window_list:
            if "Roblox" in window:
                window_info = pygetwindow.getWindowsWithTitle(window)[0]
                return window_info.left+8, window_info.top+8, window_info.width-16, window_info.height-16

    def isColorBlack(self, color):
        return color[0] < 80 and color[1] < 80 and color[2] < 80

    def isColorWhite(self, color):
        return color[0] > 175 and color[1] > 175 and color[2] > 175

    def detect_aura(self, image):
        rX, rY, rW, rH = self.getRobloxWindowSize()
        scanPoints = [[rX+1,rY+31],[rX+rW-2,rY+31],[rX+1,rY+rH-2],[rX+rW-2,rY+rH-2]]
        blackCorners = 0
        whiteCorners = 0
        cornerResults = []

        for point in scanPoints:
            pColor = image[point[1], point[0]]
            if self.isColorBlack(pColor):
                blackCorners += 1
            if self.isColorWhite(pColor):
                whiteCorners += 1
            cornerResults.append(pColor)

        current_time = time.time()
        if current_time - self.last_detection_time < 15:
            return None

        star_bbox, star_type = self.detect_star_shape(image)
        if not ((blackCorners >= 4 and star_bbox) or (star_bbox and self.isColorBlack(cornerResults[0]) and self.isColorBlack(cornerResults[1]) and not self.isColorWhite(cornerResults[2]))):
            return None

        x, y, w, h = star_bbox
        center_x, center_y = x + w // 2, y + h // 2
        
        screenshot = ImageGrab.grab()
        colors = [
            screenshot.getpixel((center_x + dx, center_y + dy))
            for dx in range(-1, 2) for dy in range(-1, 2)
        ]
        center_color = np.mean(colors, axis=0).astype(int)

        detected_hsv = cv2.cvtColor(np.uint8([[center_color]]), cv2.COLOR_RGB2HSV)[0][0]

        # Get the aura group based on star type
        aura_group = (self.auras["1m+"] | self.auras["10m+"] | self.auras["100m+"]) if star_type == "8_corners" else self.auras["10k+"]
        best_aura = None
        min_distance = float('inf')

        for aura_name, aura_info in aura_group.items():
            aura_rgb = aura_info["color"]
            tolerance = aura_info["tolerance"]

            distance_rgb = self.rgb_distance(center_color, aura_rgb)
            if distance_rgb < tolerance:
                aura_hsv = cv2.cvtColor(np.uint8([[aura_rgb]]), cv2.COLOR_RGB2HSV)[0][0]
                distance_hsv = self.hsv_distance(detected_hsv, aura_hsv)

                if distance_hsv < tolerance and distance_hsv < min_distance:
                    min_distance = distance_hsv
                    best_aura = (aura_name, aura_info)

        if best_aura and best_aura[0] != self.previous_aura_name:
            aura_name, aura_info = best_aura
            rarity_value = int(aura_info.get("rarity", 0))

            # Save the detected aura image
            filename = self.save_image(image, aura_name, star_type)

            # Send a webhook notification
            self.send_webhook(aura_name, rarity_value, filename, aura_info["color"], aura_info.get("image"))
            self.previous_aura_name = aura_name
            self.last_detection_time = current_time
            print(f"Detected Aura: {aura_name}")
        else:
            print("No auras detected.")

    def save_image(self, image, aura_name, star_type):
        filename = f"images/auras/{aura_name}_{star_type}.png"
        cv2.imwrite(filename, image)
        print(f"Saved aura image: {filename}")
        return filename

    def run(self, interval=1):
        while True:
            self.getRobloxWindowSize()
            screenshot = pyautogui.screenshot()
            image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            self.detect_aura(image)
            time.sleep(interval)


if __name__ == "__main__":
    detector = AuraDetector()
    detector.run()
