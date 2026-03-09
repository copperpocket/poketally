import sys
import json
import os
import cv2
import pytesseract
import numpy as np
import mss
import csv
from PyQt6.QtWidgets import QCompleter
from datetime import datetime
from Xlib import display, X
from difflib import SequenceMatcher
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, 
                             QMessageBox, QLineEdit, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer

class PokeTally(QWidget):
    def __init__(self):
        super().__init__()
        self.file_path = "hunt_stats.json"
        self.pokemon_file = "pokemon_list.txt"
        self.log_file = "encounter_log.csv"
        self.last_detected_name = None
        
        self.data = self.load_data()
        self.master_list = self.load_pokemon_list()
        
        self.init_ui()
        self.ensure_csv_header()
        self.sct = mss.mss()

        self.detector_timer = QTimer()
        self.detector_timer.timeout.connect(self.scan_for_pokemon)
        self.detector_timer.start(2000)

    def ensure_csv_header(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Pokemon", "OCR_Text", "Confidence", "Is_Target"])

    def log_to_csv(self, name, ocr_text, conf, is_target):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, name, ocr_text, round(conf, 2), is_target])

    def load_pokemon_list(self):
        if os.path.exists(self.pokemon_file):
            with open(self.pokemon_file, "r") as f:
                return [line.strip().upper() for line in f if len(line.strip()) > 2]
        return []

    def get_best_match(self, ocr_text):
        ocr_text = ocr_text.upper().strip()
        is_nidoran_base = "NIDOR" in ocr_text or "MIDOR" in ocr_text
        is_evolved = any(x in ocr_text for x in ("INA", "INO", "IMO"))
        
        if is_nidoran_base and not is_evolved:
            if any(marker in ocr_text for marker in ("S", "5", "8", "B")):
                return ("NIDORAN-M", 0.95)
            if any(marker in ocr_text for marker in ("Q", "0", "O", "F")):
                return ("NIDORAN-F", 0.95)

        best_name = None
        highest_ratio = 0
        for name in self.master_list:
            if abs(len(ocr_text) - len(name)) > 2: 
                continue 
            ratio = SequenceMatcher(None, ocr_text, name).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_name = name
        
        return (best_name, highest_ratio) if highest_ratio > 0.65 else (None, 0)

    def find_window_x11(self, title):
        d = None
        try:
            d = display.Display()
            root = d.screen().root
            prop = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
            if not prop: return None
            for window_id in prop.value:
                window = d.create_resource_object('window', window_id)
                wm_name = window.get_wm_name()
                if wm_name and title.lower() in wm_name.lower():
                    pos = root.translate_coords(window_id, 0, 0)
                    geom = window.get_geometry()
                    return {'left': pos.x, 'top': pos.y, 'width': geom.width, 'height': geom.height}
        except: pass
        finally:
            if d: d.close()
        return None

    def scan_for_pokemon(self):
        win = self.find_window_x11(self.data["window_title"])
        if not win: return

        monitor = {
            "left": int(win['left'] + (win['width'] * 0.075)),
            "top": int(win['top'] + (win['height'] * 0.16)),
            "width": int(win['width'] * 0.25),
            "height": int(win['height'] * 0.07)
        }

        try:
            sct_img = self.sct.grab(monitor)
            cv_img = np.array(sct_img)
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGRA2BGR)
            cv2.imwrite("debug_raw.png", cv_img)
            
            cv_img = cv2.resize(cv_img, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
            cv2.imwrite("debug_ocr.png", thresh)
            
            raw_text = pytesseract.image_to_string(thresh, config=r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ-580Q').strip()

            if len(raw_text) >= 3:
                best_name, confidence = self.get_best_match(raw_text)
                if not best_name or best_name == self.last_detected_name:
                    return

                print(f"Detected: {best_name} (OCR: '{raw_text}' | Conf: {confidence:.2f})")
                self.last_detected_name = best_name
                
                is_target = best_name == self.data["target_name"].upper()
                self.log_to_csv(best_name, raw_text, confidence, is_target)

                if is_target:
                    self.add_target()
                else:
                    self.add_generic()
            elif len(raw_text) == 0:
                self.last_detected_name = None
        except Exception as e:
            print(f"Scan error: {e}")

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
        self.target_btn = QPushButton(f"+1 {self.data['target_name']}")
        self.target_btn.clicked.connect(self.add_target)
        btn_layout.addWidget(b1); btn_layout.addWidget(self.target_btn)
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
        
        # AUTOCOMPLETE
        completer = QCompleter(self.master_list)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        p_in.setCompleter(completer)

        l.addWidget(QLabel("Target Name (e.g. 'Pika'):"))
        l.addWidget(p_in)
        l.addWidget(QLabel("Window Title:"))
        l.addWidget(w_in)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); l.addWidget(bb)
        
        if dialog.exec():
            # RESTORED PREDICTION LOGIC
            new_val = p_in.text().strip()
            best_name, ratio = self.get_best_match(new_val)
            
            # If we found a good match in our master list, use that!
            if best_name and ratio > 0.5:
                self.data["target_name"] = best_name.capitalize()
            else:
                self.data["target_name"] = new_val.capitalize()
                
            self.data["window_title"] = w_in.text().strip()
            self.update_stats()

    def add_generic(self): self.data['total'] += 1; self.update_stats()
    def add_target(self): self.data['total'] += 1; self.data['target'] += 1; self.update_stats()
    
    def update_stats(self):
        self.total_lbl.setText(str(self.data['total']))
        self.target_header.setText(f"{self.data['target_name'].upper()} ENCOUNTERS")
        self.target_val_lbl.setText(str(self.data['target']))
        self.target_btn.setText(f"+1 {self.data['target_name']}") 
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