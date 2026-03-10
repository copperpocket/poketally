import sys
import json
import os
import cv2
import pytesseract
import numpy as np
import mss
from PyQt6.QtWidgets import QCompleter
from Xlib import display, X
from difflib import SequenceMatcher
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel,
                             QMessageBox, QLineEdit, QDialog, QDialogButtonBox,
                             QGridLayout, QFrame, QFileDialog, QCheckBox)
from PyQt6.QtCore import Qt, QTimer
import subprocess

# --------------------------------------------------
# MASTER DASHBOARD CLASS
# --------------------------------------------------
class MasterDashboard(QWidget):
    def __init__(self, num_instances=1):
        super().__init__()
        self.num_instances = num_instances
        self.data_dir = "data"
        if not os.path.exists(self.data_dir): os.makedirs(self.data_dir)

        self.debug_dir = os.path.join(self.data_dir, "debug")
        if not os.path.exists(self.debug_dir): os.makedirs(self.debug_dir)
        
        self.pokemon_file = "pokemon_list.txt"
        self.workers = []  
        self.emulators = [] 
        self.is_tracking = False 
        
        self.master_list = self.load_pokemon_list()
        
        self.setWindowTitle("PokeTally MISSION CONTROL")
        self.setMinimumSize(850, 750)
        self.setStyleSheet("""
            QWidget { background-color: #121212; color: #ffffff; font-family: 'Segoe UI', sans-serif; }
            QPushButton { background-color: #2c3e50; border: 1px solid #34495e; border-radius: 4px; padding: 5px; }
            QPushButton:hover { background-color: #34495e; }
            QLineEdit { background-color: #1e1e1e; border: 1px solid #333; padding: 5px; border-radius: 3px; }
            QLabel { border: none; }
        """)
        
        self.init_ui()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_display)
        self.refresh_timer.start(1000)

    def load_pokemon_list(self):
        if os.path.exists(self.pokemon_file):
            with open(self.pokemon_file, "r") as f:
                return [line.strip().upper() for line in f if len(line.strip()) > 2]
        return []

    def init_ui(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #1a1a1a; border-radius: 10px; border: 1px solid #333;")
        header_layout = QVBoxLayout(header_frame)

        self.target_name_lbl = QLabel("CURRENT TARGET: LOADING...")
        self.target_name_lbl.setStyleSheet("font-size: 20px; color: #3498db; font-weight: bold; border: none;")
        self.target_name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        stats_hbox = QHBoxLayout()
        t_vbox = QVBoxLayout()
        self.combined_total_lbl = QLabel("0")
        self.combined_total_lbl.setStyleSheet("font-size: 42px; font-weight: bold; color: #f1c40f; border: none;")
        t_sub = QLabel("COMBINED ENCOUNTERS")
        t_sub.setStyleSheet("font-size: 11px; color: #7f8c8d; border: none;")
        t_vbox.addWidget(self.combined_total_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        t_vbox.addWidget(t_sub, alignment=Qt.AlignmentFlag.AlignCenter)

        tg_vbox = QVBoxLayout()
        self.combined_target_lbl = QLabel("0")
        self.combined_target_lbl.setStyleSheet("font-size: 42px; font-weight: bold; color: #3498db; border: none;")
        tg_sub = QLabel("TOTAL TARGETS")
        tg_sub.setStyleSheet("font-size: 11px; color: #7f8c8d; border: none;")
        tg_vbox.addWidget(self.combined_target_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        tg_vbox.addWidget(tg_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        
        stats_hbox.addLayout(t_vbox)
        stats_hbox.addLayout(tg_vbox)
        header_layout.addWidget(self.target_name_lbl)
        header_layout.addLayout(stats_hbox)
        self.main_layout.addWidget(header_frame)

        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.main_layout.addWidget(self.grid_container)
        self.build_grid() 

        config_frame = QFrame()
        config_frame.setStyleSheet("background-color: #1a1a1a; border-radius: 8px; padding: 10px; border: 1px solid #222;")
        config_layout = QGridLayout(config_frame)

        config_layout.addWidget(QLabel("Instances:"), 0, 0)
        self.count_input = QLineEdit(str(self.num_instances))
        self.count_input.setFixedWidth(40)
        self.count_input.textChanged.connect(self.update_instance_count)
        config_layout.addWidget(self.count_input, 0, 1)

        self.debug_check = QCheckBox("Debug Mode (Show OCR logs & Save Images)")
        config_layout.addWidget(self.debug_check, 0, 2)

        config_layout.addWidget(QLabel("Emulator:"), 1, 0)
        self.emu_path = QLineEdit("/usr/bin/mgba-qt")
        emu_btn = QPushButton("📁 Browse")
        emu_btn.clicked.connect(self.select_emulator)
        config_layout.addWidget(self.emu_path, 1, 1)
        config_layout.addWidget(emu_btn, 1, 2)

        config_layout.addWidget(QLabel("ROM:"), 2, 0)
        self.rom_path = QLineEdit("")
        rom_btn = QPushButton("📁 Browse")
        rom_btn.clicked.connect(self.select_rom)
        config_layout.addWidget(self.rom_path, 2, 1)
        config_layout.addWidget(rom_btn, 2, 2)

        self.main_layout.addWidget(config_frame)

        btn_layout = QHBoxLayout()
        self.toggle_btn = QPushButton("🚀 Start Program")
        self.toggle_btn.setMinimumHeight(50)
        self.toggle_btn.setStyleSheet("background-color: #27ae60; font-weight: bold; border: none;")
        self.toggle_btn.clicked.connect(self.toggle_program)

        set_btn = QPushButton("Change Target")
        set_btn.setMinimumHeight(50)
        reset_btn = QPushButton("Reset All")
        reset_btn.setMinimumHeight(50)
        reset_btn.setStyleSheet("color: #e74c3c; font-weight: bold; border: none;")
        
        btn_layout.addWidget(self.toggle_btn, 2)
        btn_layout.addWidget(set_btn, 1)
        btn_layout.addWidget(reset_btn, 1)
        
        set_btn.clicked.connect(self.open_global_settings)
        reset_btn.clicked.connect(self.reset_all)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

    def select_emulator(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Emulator")
        if path: self.emu_path.setText(path)

    def select_rom(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select ROM File")
        if path: self.rom_path.setText(path)

    def build_grid(self):
        for i in reversed(range(self.grid.count())): 
            if self.grid.itemAt(i).widget(): self.grid.itemAt(i).widget().setParent(None)
        self.instance_widgets = {}
        for i in range(1, self.num_instances + 1):
            frame = QFrame()
            frame.setStyleSheet("background-color: #1e1e1e; border-radius: 6px; border: 1px solid #333;")
            f_layout = QVBoxLayout(frame)
            title = QLabel(f"GAME {i}"); title.setStyleSheet("color: #555; font-size: 10px; font-weight: bold; border: none;")
            t_row, g_row = QHBoxLayout(), QHBoxLayout()
            t_val = QLabel("0"); t_val.setStyleSheet("color: #f1c40f; font-size: 18px; font-weight: bold; border: none;")
            g_val = QLabel("0"); g_val.setStyleSheet("color: #3498db; font-size: 18px; font-weight: bold; border: none;")
            t_row.addWidget(QLabel("Total:")); t_row.addStretch(); t_row.addWidget(t_val)
            g_row.addWidget(QLabel("Target:")); g_row.addStretch(); g_row.addWidget(g_val)
            f_layout.addWidget(title); f_layout.addLayout(t_row); f_layout.addLayout(g_row)
            self.grid.addWidget(frame, (i-1)//4, (i-1)%4)
            self.instance_widgets[i] = (t_val, g_val)

    def update_instance_count(self):
        try:
            val = int(self.count_input.text())
            if 1 <= val <= 8: self.num_instances = val; self.build_grid()
        except: pass

    def toggle_program(self):
        if not self.is_tracking: self.start_program()
        else: self.stop_program()

    def start_program(self):
        emu, rom = self.emu_path.text().strip(), self.rom_path.text().strip()
        if os.path.exists(emu) and os.path.exists(rom):
            for _ in range(self.num_instances):
                self.emulators.append(subprocess.Popen([emu, rom]))
        
        QTimer.singleShot(2000, self.launch_workers)
        self.is_tracking = True
        self.toggle_btn.setText("🛑 Stop Program")
        self.toggle_btn.setStyleSheet("background-color: #c0392b; font-weight: bold; border: none;")

    def launch_workers(self):
        script_path = os.path.abspath(sys.argv[0])
        debug_flag = "debug" if self.debug_check.isChecked() else "normal"
        for i in range(1, self.num_instances + 1):
            self.workers.append(subprocess.Popen([sys.executable, script_path, str(i), debug_flag]))

    def stop_program(self):
        for p in self.workers + self.emulators:
            try: p.terminate()
            except: pass
        self.workers, self.emulators = [], []
        self.is_tracking = False
        self.toggle_btn.setText("🚀 Start Program")
        self.toggle_btn.setStyleSheet("background-color: #27ae60; font-weight: bold; border: none;")

    def closeEvent(self, event): self.stop_program(); event.accept()

    def update_display(self):
        grand_total, grand_target = 0, 0
        current_name = "Rhyhorn"
        for i in range(1, self.num_instances + 1):
            f_p = os.path.join(self.data_dir, f"hunt_stats_{i}.json")
            if os.path.exists(f_p):
                with open(f_p, "r") as f:
                    d = json.load(f)
                    if i in self.instance_widgets:
                        self.instance_widgets[i][0].setText(str(d.get("total", 0)))
                        self.instance_widgets[i][1].setText(str(d.get("target", 0)))
                    grand_total += d.get("total", 0); grand_target += d.get("target", 0)
                    current_name = d.get("target_name", "???")
        self.combined_total_lbl.setText(str(grand_total))
        self.combined_target_lbl.setText(str(grand_target))
        self.target_name_lbl.setText(f"GLOBAL TARGET: {current_name.upper()}")

    def open_global_settings(self):
        dialog = QDialog(self); dialog.setWindowTitle("Target")
        l = QVBoxLayout(dialog); p_in = QLineEdit()
        comp = QCompleter(self.master_list); comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        p_in.setCompleter(comp); l.addWidget(QLabel("Target Pokemon:")); l.addWidget(p_in)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); l.addWidget(bb)
        if dialog.exec():
            new_t = p_in.text().strip().capitalize()
            for i in range(1, 10):
                f_p = os.path.join(self.data_dir, f"hunt_stats_{i}.json")
                if os.path.exists(f_p):
                    with open(f_p, "r") as f: d = json.load(f)
                    d["target_name"] = new_t
                    with open(f_p, "w") as f: json.dump(d, f)

    def reset_all(self):
        if QMessageBox.question(self, 'Reset', "Reset all counts?") == QMessageBox.StandardButton.Yes:
            for i in range(1, 10):
                f_p = os.path.join(self.data_dir, f"hunt_stats_{i}.json")
                if os.path.exists(f_p):
                    with open(f_p, "r") as f: d = json.load(f)
                    d["total"], d["target"] = 0, 0
                    with open(f_p, "w") as f: json.dump(d, f)

# --------------------------------------------------
# WORKER CLASS
# --------------------------------------------------
class PokeTally(QWidget):
    def __init__(self, instance_id="1", debug_mode=False):
        super().__init__()
        self.data_dir, self.instance_id, self.debug_mode = "data", instance_id, debug_mode
        print(f"> WORKER {self.instance_id} INITIALIZED")
        
        self.anchor_path = "assets/anchor.png"
        self.file_path = os.path.join(self.data_dir, f"hunt_stats_{self.instance_id}.json")
        self.pokemon_file = "pokemon_list.txt"
        self.pending_name, self.pending_count, self.last_detected_name = None, 0, None
        
        self.data = self.load_data()
        self.master_list = self.load_pokemon_list()
        self.sct = mss.mss()
        
        self.detector_timer = QTimer()
        self.detector_timer.timeout.connect(self.scan_for_pokemon)
        self.detector_timer.start(400)

    def load_pokemon_list(self):
        if os.path.exists(self.pokemon_file):
            with open(self.pokemon_file, "r") as f: return [line.strip().upper() for line in f if len(line.strip()) > 2]
        return []

    def load_data(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f: return json.load(f)
        return {"total": 0, "target": 0, "target_name": "Rhyhorn", "window_title": "mGBA"}

    def save_data(self):
        with open(self.file_path, "w") as f: json.dump(self.data, f)

    def get_best_match(self, ocr_text):
        ocr_text = ocr_text.upper().strip()
        best_name, highest_ratio = None, 0
        for name in self.master_list:
            ratio = SequenceMatcher(None, ocr_text, name).ratio()
            if ratio > highest_ratio: highest_ratio = ratio; best_name = name
        return (best_name, highest_ratio) if highest_ratio > 0.65 else (None, 0)

    def find_window_x11(self):
        d = None
        try:
            d = display.Display(); root = d.screen().root
            prop = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
            if not prop: return None
            matches = []
            for wid in prop.value:
                win = d.create_resource_object('window', wid)
                name = win.get_wm_name()
                if name and "mGBA" in name: matches.append(wid)
            matches.sort()
            idx = int(self.instance_id) - 1
            if idx < len(matches):
                win = d.create_resource_object('window', matches[idx])
                pos, geom = root.translate_coords(matches[idx], 0, 0), win.get_geometry()
                return {'left': pos.x, 'top': pos.y, 'width': geom.width, 'height': geom.height}
        except: pass
        finally: 
            if d: d.close()
        return None

    def get_game_bounds(self, frame):
        """Mathematically fits a 1.5 ratio GBA screen into the window, accounting for UI."""
        h_full, w_full = frame.shape[:2]
        
        # 1. FIND THE CONTENT AREA (Ignore black bars on the very edges)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(thresh)
        
        if coords is None: return None
        
        # This is the box containing [Menu Bar + Game + any internal black bars]
        cx, cy, cw, ch = cv2.boundingRect(coords)
        
        # 2. DEFINE THE MENU BAR HEIGHT
        # In mGBA-qt on Linux, the menu is usually ~25-30 pixels.
        # We'll use 28 as a standard. If your green box is slightly low, decrease this.
        # If your green box is slightly high, increase this.
        MENU_H = 22
        
        # The area available for the game
        avail_w = cw
        avail_h = ch - MENU_H
        
        target_ratio = 1.5 # GBA standard
        
        # 3. CALCULATE GAME BOX BASED ON ASPECT RATIO
        if (avail_w / avail_h) > target_ratio:
            # Window is too wide (Pillarboxed: black bars on left/right)
            gh = avail_h
            gw = int(gh * target_ratio)
            gx = cx + (avail_w - gw) // 2
            gy = cy + MENU_H
        else:
            # Window is too tall (Letterboxed: black bars on top/bottom)
            gw = avail_w
            gh = int(gw / target_ratio)
            gx = cx
            gy = cy + MENU_H + (avail_h - gh) // 2
            
        return (gx, gy, gw, gh)

    def scan_for_pokemon(self):
        win = self.find_window_x11()
        if not win: return
        
        try:
            # Grab the whole window so we can see the black bars
            sct_img = self.sct.grab(win)
            frame = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
            
            bounds = self.get_game_bounds(frame)
            if not bounds: return
            
            gx, gy, gw, gh = bounds
            
            # --- YOUR REFINED NUMBERS ---
            # Using your exact percentages from the previous successful run
            y1 = gy + int(gh * 0.125)
            y2 = gy + int(gh * 0.19) 
            x1 = gx + int(gw * 0.075)
            x2 = gx + int(gw * 0.33)
            
            # Slice and dice
            target_roi = frame[y1:y2, x1:x2]
            if target_roi.size == 0: return

            # OCR Pre-processing
            gray_roi = cv2.cvtColor(target_roi, cv2.COLOR_BGR2GRAY)
            img_scaled = cv2.resize(gray_roi, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(img_scaled, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            raw_text = pytesseract.image_to_string(thresh, config=r'--psm 7').strip().upper()
            
            if self.debug_mode:
                debug_frame = frame.copy()
                # Blue: The calculated GAME area (should be perfect 1.5 ratio)
                cv2.rectangle(debug_frame, (gx, gy), (gx+gw, gy+gh), (255, 0, 0), 2) 
                # Green: The Name ROI
                cv2.rectangle(debug_frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
                cv2.imwrite(f"data/debug/match_preview_{self.instance_id}.png", debug_frame)
                cv2.imwrite(f"data/debug/ocr_debug_{self.instance_id}.png", thresh)

            # DETECTION LOGIC
            if len(raw_text) >= 3:
                best_name, conf = self.get_best_match(raw_text)
                if best_name and best_name != self.last_detected_name:
                    if best_name == self.pending_name:
                        self.pending_count += 1
                        if self.pending_count >= 2:
                            print(f"[Worker {self.instance_id}] >>> SUCCESS: {best_name}")
                            self.last_detected_name = best_name
                            self.data['total'] += 1
                            if best_name == self.data["target_name"].upper(): 
                                self.data['target'] += 1
                            self.save_data()
                    else:
                        self.pending_name = best_name
                        self.pending_count = 1
            elif len(raw_text) == 0:
                self.last_detected_name = None
                
        except Exception as e:
            if self.debug_mode: print(f"Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if len(sys.argv) == 1:
        window = MasterDashboard()
        window.show()
    else:
        is_debug = (sys.argv[2] == "debug") if len(sys.argv) > 2 else False
        worker = PokeTally(instance_id=sys.argv[1], debug_mode=is_debug)
    sys.exit(app.exec())