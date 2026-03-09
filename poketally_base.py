import sys
import json
import os
import cv2
import pytesseract
import numpy as np
import mss
from Xlib import display, X
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, 
                             QMessageBox, QLineEdit, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer

class PokeTally(QWidget):
    def __init__(self):
        super().__init__()
        
        self.file_path = "hunt_stats.json"
        self.pokemon_file = "pokemon_list.txt"
        self.last_detected_name = None
        
        self.data = self.load_data()
        self.init_ui()

        self.sct = mss.mss()

        # Timer set to 2 seconds for scanning
        self.detector_timer = QTimer()
        self.detector_timer.timeout.connect(self.scan_for_pokemon)
        self.detector_timer.start(2000)

    def find_window_x11(self, title):
        d = None
        try:
            d = display.Display()
            root = d.screen().root
            net_client_list = d.intern_atom('_NET_CLIENT_LIST')
            prop = root.get_full_property(net_client_list, X.AnyPropertyType)
            
            if not prop:
                return None

            for window_id in prop.value:
                window = d.create_resource_object('window', window_id)
                wm_name = window.get_wm_name()
                
                # Check if 'mgba' is in the window title
                if wm_name and title.lower() in wm_name.lower():
                    # Translate window (0,0) to absolute screen (X,Y)
                    pos = root.translate_coords(window_id, 0, 0)
                    geom = window.get_geometry()
                    
                    coords = {
                        'left': pos.x, 
                        'top': pos.y, 
                        'width': geom.width, 
                        'height': geom.height
                    }
                    
                    # LOGGING BASICS: Print the location to console
                    print(f"TARGET FOUND: '{wm_name}' at X:{coords['left']} Y:{coords['top']}")
                    return coords
        except Exception as e:
            print(f"X11 Window Error: {e}")
        finally:
            if d: d.close()
        return None

    def scan_for_pokemon(self):
        win = self.find_window_x11(self.data["window_title"])
        if not win:
            # Only print if we can't find it to avoid console spam
            # print("Searching for mGBA...") 
            return

        # Define the detection area relative to the window
        # Adjust these if the OCR is missing the name
        off_x, off_y = 40, 60 
        w, h = 250, 60
        
        monitor = {
            "top": win['top'] + off_y, 
            "left": win['left'] + off_x, 
            "width": w, 
            "height": h
        }

        try:
            # Capture the specific box
            sct_img = self.sct.grab(monitor)
            cv_img = np.array(sct_img)
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGRA2BGR)
            
            # Save debug image so you can see WHAT the script sees
            cv2.imwrite("debug_box.png", cv_img)
            
            # Basic OCR Pre-processing
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            
            # Tesseract OCR
            detected_text = pytesseract.image_to_string(thresh, config='--psm 7').strip().lower()
            
            if len(detected_text) > 2:
                if detected_text != self.last_detected_name:
                    print(f"OCR DETECTED: '{detected_text}'")
                    self.last_detected_name = detected_text
                    
                    target = self.data["target_name"].lower()
                    if target in detected_text:
                        print(f"LOGGED MATCH: {target.upper()}")
                        self.add_target()
                    else:
                        print("LOGGED ENCOUNTER: Generic")
                        self.add_generic()
            else:
                self.last_detected_name = None

        except Exception as e:
            print(f"Capture error: {e}")

    def init_ui(self):
        self.setWindowTitle("PokeTally")
        self.setFixedSize(280, 260)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")

        layout = QVBoxLayout()
        self.total_lbl = QLabel(str(self.data['total']))
        self.total_lbl.setStyleSheet("font-size: 32px; font-weight: bold;")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("TOTAL ENCOUNTERS"))
        layout.addWidget(self.total_lbl)

        self.target_header = QLabel(f"{self.data['target_name'].upper()} ENCOUNTERS")
        self.target_val_lbl = QLabel(str(self.data['target']))
        self.target_val_lbl.setStyleSheet("font-size: 24px; color: #3498db;")
        self.target_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.target_header)
        layout.addWidget(self.target_val_lbl)

        btn_layout = QHBoxLayout()
        b1 = QPushButton("+1 Any"); b1.clicked.connect(self.add_generic)
        b2 = QPushButton(f"+1 {self.data['target_name']}"); b2.clicked.connect(self.add_target)
        btn_layout.addWidget(b1); btn_layout.addWidget(b2)
        layout.addLayout(btn_layout)

        util_layout = QHBoxLayout()
        s = QPushButton("Settings"); s.clicked.connect(self.open_settings)
        r = QPushButton("Reset"); r.clicked.connect(self.reset_tally)
        util_layout.addWidget(s); util_layout.addStretch(); util_layout.addWidget(r)
        layout.addLayout(util_layout)
        self.setLayout(layout)

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        l = QVBoxLayout(dialog)
        p_in = QLineEdit(self.data["target_name"])
        w_in = QLineEdit(self.data["window_title"])
        l.addWidget(QLabel("Target:")); l.addWidget(p_in)
        l.addWidget(QLabel("Window:")); l.addWidget(w_in)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); l.addWidget(bb)
        if dialog.exec():
            self.data["target_name"] = p_in.text().strip().capitalize()
            self.data["window_title"] = w_in.text().strip()
            self.update_stats()

    def add_generic(self): self.data['total'] += 1; self.update_stats()
    def add_target(self): self.data['total'] += 1; self.data['target'] += 1; self.update_stats()
    
    def update_stats(self):
        self.total_lbl.setText(str(self.data['total']))
        self.target_header.setText(f"{self.data['target_name'].upper()} ENCOUNTERS")
        self.target_val_lbl.setText(str(self.data['target']))
        self.save_data()import sys
import json
import os
import cv2
import pytesseract
import numpy as np
import mss
from Xlib import display, X
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, 
                             QMessageBox, QLineEdit, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer

class PokeTally(QWidget):
    def __init__(self):
        super().__init__()
        
        self.file_path = "hunt_stats.json"
        self.pokemon_file = "pokemon_list.txt"
        self.last_detected_name = None
        
        self.data = self.load_data()
        self.init_ui()

        self.sct = mss.mss()

        # Timer set to 2 seconds for scanning
        self.detector_timer = QTimer()
        self.detector_timer.timeout.connect(self.scan_for_pokemon)
        self.detector_timer.start(2000)

    def find_window_x11(self, title):
        d = None
        try:
            d = display.Display()
            root = d.screen().root
            net_client_list = d.intern_atom('_NET_CLIENT_LIST')
            prop = root.get_full_property(net_client_list, X.AnyPropertyType)
            
            if not prop:
                return None

            for window_id in prop.value:
                window = d.create_resource_object('window', window_id)
                wm_name = window.get_wm_name()
                
                # Check if 'mgba' is in the window title
                if wm_name and title.lower() in wm_name.lower():
                    # Translate window (0,0) to absolute screen (X,Y)
                    pos = root.translate_coords(window_id, 0, 0)
                    geom = window.get_geometry()
                    
                    coords = {
                        'left': pos.x, 
                        'top': pos.y, 
                        'width': geom.width, 
                        'height': geom.height
                    }
                    
                    # LOGGING BASICS: Print the location to console
                    print(f"TARGET FOUND: '{wm_name}' at X:{coords['left']} Y:{coords['top']}")
                    return coords
        except Exception as e:
            print(f"X11 Window Error: {e}")
        finally:
            if d: d.close()
        return None

    def scan_for_pokemon(self):
        win = self.find_window_x11(self.data["window_title"])
        if not win:
            # Only print if we can't find it to avoid console spam
            # print("Searching for mGBA...") 
            return

        # Define the detection area relative to the window
        # Adjust these if the OCR is missing the name
        off_x, off_y = 40, 60 
        w, h = 250, 60
        
        monitor = {
            "top": win['top'] + off_y, 
            "left": win['left'] + off_x, 
            "width": w, 
            "height": h
        }

        try:
            # Capture the specific box
            sct_img = self.sct.grab(monitor)
            cv_img = np.array(sct_img)
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGRA2BGR)
            
            # Save debug image so you can see WHAT the script sees
            cv2.imwrite("debug_box.png", cv_img)
            
            # Basic OCR Pre-processing
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            
            # Tesseract OCR
            detected_text = pytesseract.image_to_string(thresh, config='--psm 7').strip().lower()
            
            if len(detected_text) > 2:
                if detected_text != self.last_detected_name:
                    print(f"OCR DETECTED: '{detected_text}'")
                    self.last_detected_name = detected_text
                    
                    target = self.data["target_name"].lower()
                    if target in detected_text:
                        print(f"LOGGED MATCH: {target.upper()}")
                        self.add_target()
                    else:
                        print("LOGGED ENCOUNTER: Generic")
                        self.add_generic()
            else:
                self.last_detected_name = None

        except Exception as e:
            print(f"Capture error: {e}")

    def init_ui(self):
        self.setWindowTitle("PokeTally")
        self.setFixedSize(280, 260)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")

        layout = QVBoxLayout()
        self.total_lbl = QLabel(str(self.data['total']))
        self.total_lbl.setStyleSheet("font-size: 32px; font-weight: bold;")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("TOTAL ENCOUNTERS"))
        layout.addWidget(self.total_lbl)

        self.target_header = QLabel(f"{self.data['target_name'].upper()} ENCOUNTERS")
        self.target_val_lbl = QLabel(str(self.data['target']))
        self.target_val_lbl.setStyleSheet("font-size: 24px; color: #3498db;")
        self.target_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.target_header)
        layout.addWidget(self.target_val_lbl)

        btn_layout = QHBoxLayout()
        b1 = QPushButton("+1 Any"); b1.clicked.connect(self.add_generic)
        b2 = QPushButton(f"+1 {self.data['target_name']}"); b2.clicked.connect(self.add_target)
        btn_layout.addWidget(b1); btn_layout.addWidget(b2)
        layout.addLayout(btn_layout)

        util_layout = QHBoxLayout()
        s = QPushButton("Settings"); s.clicked.connect(self.open_settings)
        r = QPushButton("Reset"); r.clicked.connect(self.reset_tally)
        util_layout.addWidget(s); util_layout.addStretch(); util_layout.addWidget(r)
        layout.addLayout(util_layout)
        self.setLayout(layout)

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        l = QVBoxLayout(dialog)
        p_in = QLineEdit(self.data["target_name"])
        w_in = QLineEdit(self.data["window_title"])
        l.addWidget(QLabel("Target:")); l.addWidget(p_in)
        l.addWidget(QLabel("Window:")); l.addWidget(w_in)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); l.addWidget(bb)
        if dialog.exec():
            self.data["target_name"] = p_in.text().strip().capitalize()
            self.data["window_title"] = w_in.text().strip()
            self.update_stats()

    def add_generic(self): self.data['total'] += 1; self.update_stats()
    def add_target(self): self.data['total'] += 1; self.data['target'] += 1; self.update_stats()
    
    def update_stats(self):
        self.total_lbl.setText(str(self.data['total']))
        self.target_header.setText(f"{self.data['target_name'].upper()} ENCOUNTERS")
        self.target_val_lbl.setText(str(self.data['target']))
        self.save_data()

    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f: return json.load(f)
            except: pass
        return {"total": 0, "target": 0, "target_name": "Rhyhorn", "window_title": "mGBA"}

    def save_data(self):
        with open(self.file_path, "w") as f: json.dump(self.data, f)

    def reset_tally(self):
        if QMessageBox.question(self, 'Reset', "Reset?") == QMessageBox.StandardButton.Yes:
            self.data["total"] = 0; self.data["target"] = 0; self.update_stats()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tally = PokeTally()
    tally.show()
    sys.exit(app.exec())

    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f: return json.load(f)
            except: pass
        return {"total": 0, "target": 0, "target_name": "Rhyhorn", "window_title": "mGBA"}

    def save_data(self):
        with open(self.file_path, "w") as f: json.dump(self.data, f)

    def reset_tally(self):
        if QMessageBox.question(self, 'Reset', "Reset?") == QMessageBox.StandardButton.Yes:
            self.data["total"] = 0; self.data["target"] = 0; self.update_stats()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tally = PokeTally()
    tally.show()
    sys.exit(app.exec())