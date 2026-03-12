import sys
import json
import os
from Xlib import display, X
from PyQt6.QtWidgets import QCompleter
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel,
                             QMessageBox, QLineEdit, QDialog, QDialogButtonBox,
                             QGridLayout, QFrame, QFileDialog, QCheckBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
import subprocess
from datetime import datetime

# --------------------------------------------------
# MASTER DASHBOARD CLASS
# --------------------------------------------------
class MasterDashboard(QWidget):
    def __init__(self, num_instances=1):
        super().__init__()
        self.num_instances = num_instances
        self.data_dir = os.path.abspath("data") # Use Absolute Path
        if not os.path.exists(self.data_dir): os.makedirs(self.data_dir)

        self.config = self.load_config()
        self.pokemon_file = "pokemon_list.txt"
        self.workers = []  
        self.emulators = [] 
        self.is_tracking = False 
        self.master_list = self.load_pokemon_list()

        self.emu_w, self.emu_h, self.cols = 480, 320, 3
        self.row_gap, self.top_padding = 32, 32
        
        self.setWindowTitle("PokeTally MISSION CONTROL")
        self.setMinimumSize(850, 600)
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QFrame(); header.setStyleSheet("background: #1a1a1a; border-radius: 10px; border: 1px solid #333;")
        h_lay = QVBoxLayout(header)
        self.target_name_lbl = QLabel("CURRENT TARGET: LOADING...")
        self.target_name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_name_lbl.setStyleSheet("font-size: 20px; color: #3498db; font-weight: bold;")
        
        stats_hbox = QHBoxLayout()
        self.combined_total_lbl = QLabel("0")
        self.combined_total_lbl.setStyleSheet("font-size: 42px; color: #f1c40f;")
        self.combined_target_lbl = QLabel("0")
        self.combined_target_lbl.setStyleSheet("font-size: 42px; color: #3498db;")
        
        stats_hbox.addWidget(self.combined_total_lbl); stats_hbox.addWidget(self.combined_target_lbl)
        h_lay.addWidget(self.target_name_lbl); h_lay.addLayout(stats_hbox)
        layout.addWidget(header)

        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        layout.addWidget(self.grid_container)
        self.build_grid()

        cfg_f = QFrame(); cfg_f.setStyleSheet("background: #1a1a1a; border-radius: 8px; padding: 10px;")
        cfg_l = QGridLayout(cfg_f)
        self.count_input = QLineEdit(str(self.num_instances)); self.count_input.setFixedWidth(40)
        self.count_input.textChanged.connect(self.update_instance_count)
        self.debug_check = QCheckBox("Enable Verbose Logs")
        self.emu_path = QLineEdit(self.config.get("emu_path", ""))
        self.rom_path = QLineEdit(self.config.get("rom_path", ""))
        
        cfg_l.addWidget(QLabel("Instances:"), 0, 0); cfg_l.addWidget(self.count_input, 0, 1); cfg_l.addWidget(self.debug_check, 0, 2)
        cfg_l.addWidget(QLabel("Emulator:"), 1, 0); cfg_l.addWidget(self.emu_path, 1, 1)
        cfg_l.addWidget(QLabel("ROM:"), 2, 0); cfg_l.addWidget(self.rom_path, 2, 1)
        layout.addWidget(cfg_f)

        btn_l = QHBoxLayout()
        self.toggle_btn = QPushButton("🚀 Start Program"); self.toggle_btn.setMinimumHeight(50)
        self.toggle_btn.setStyleSheet("background-color: #27ae60; font-weight: bold;")
        self.toggle_btn.clicked.connect(self.toggle_program)
        set_btn = QPushButton("Change Target"); set_btn.setMinimumHeight(50)
        reset_btn = QPushButton("Reset All"); reset_btn.setMinimumHeight(50); reset_btn.setStyleSheet("color: #e74c3c;")
        
        btn_l.addWidget(self.toggle_btn, 2); btn_l.addWidget(set_btn, 1); btn_l.addWidget(reset_btn, 1)
        set_btn.clicked.connect(self.open_global_settings); reset_btn.clicked.connect(self.reset_all)
        layout.addLayout(btn_l)

    def reposition_emulators(self):
        d = None
        try:
            screen = QGuiApplication.primaryScreen().geometry()
            d = display.Display(); root = d.screen().root
            prop = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
            if not prop: return
            matches = [d.create_resource_object('window', wid) for wid in prop.value if "mGBA" in (d.create_resource_object('window', wid).get_wm_name() or "")]
            matches.sort(key=lambda w: w.id)
            for i, win in enumerate(matches):
                if i >= self.num_instances: break
                row, col = i // self.cols, i % self.cols
                nx = screen.x() + (col * self.emu_w)
                ny = screen.y() + self.top_padding + (row * (self.emu_h + self.row_gap))
                win.configure(x=nx, y=ny, width=self.emu_w, height=self.emu_h)
            d.sync()
        except: pass
        finally: 
            if d: d.close()

    def build_grid(self):
        for i in reversed(range(self.grid.count())): 
            if self.grid.itemAt(i).widget(): self.grid.itemAt(i).widget().setParent(None)
        self.instance_widgets, self.audio_indicators = {}, {}
        for i in range(1, self.num_instances + 1):
            f = QFrame(); f.setStyleSheet("background: #1e1e1e; border: 1px solid #333;")
            fl = QVBoxLayout(f)
            ind = QLabel("🔊 LIVE"); ind.setStyleSheet("color: #27ae60; font-size: 10px;"); ind.setVisible(False)
            self.audio_indicators[i] = ind
            t_v = QLabel("Total: 0"); g_v = QLabel("Target: 0")
            fl.addWidget(ind); fl.addWidget(QLabel(f"GAME {i}")); fl.addWidget(t_v); fl.addWidget(g_v)
            self.grid.addWidget(f, (i-1)//3, (i-1)%3)
            self.instance_widgets[i] = (t_v, g_v)
        if 1 in self.audio_indicators: self.audio_indicators[1].setVisible(True)

    def toggle_program(self):
        if not self.is_tracking: self.start_program()
        else: self.stop_program()

    def start_program(self):
        emu = os.path.abspath(self.emu_path.text().strip())
        rom = os.path.abspath(self.rom_path.text().strip())
        
        if not (os.path.exists(emu) and os.path.exists(rom)):
            QMessageBox.critical(self, "Error", "Invalid Emulator or ROM path!")
            return

        bridge_dir = os.path.join(self.data_dir, "bridge")
        script_dir = os.path.join(self.data_dir, "scripts")
        os.makedirs(bridge_dir, exist_ok=True)
        os.makedirs(script_dir, exist_ok=True)

        for i in range(1, self.num_instances + 1):
            lua_path = os.path.abspath(os.path.join(script_dir, f"worker_{i}.lua"))
            bridge_path = os.path.abspath(os.path.join(bridge_dir, f"found_{i}.txt"))
            
            # --- UPDATED LUA WITH PULSE CHECK ---
            lua_code = f"""
            local last_species = 0
            local timer = 0
            console:log(">> DEEP SCAN ACTIVE - WATCHING 0x02024020+ <<")
            
            function checkEncounter()
                timer = timer + 1
                local base = 0x02024020 -- Start slightly earlier to see the whole block
                
                -- Print diagnostics every 120 frames (~2 seconds)
                if timer > 120 then
                    local line = ""
                    for offset = 0, 16, 2 do
                        local val = emu:read16(base + offset)
                        line = line .. string.format("[%X]:%d  ", base + offset, val)
                    end
                    console:log(line)
                    timer = 0
                end

                -- Logic to actually catch the Pokemon (we'll refine the address based on your results)
                -- Checking the most likely candidates for FireRed/LeafGreen
                local candidate1 = emu:read16(0x0202402C)
                local candidate2 = emu:read16(0x0202402E)
                local candidate3 = emu:read16(0x0202443C) -- Common alt for some ROM hacks/versions
                
                local found = 0
                if candidate1 > 0 and candidate1 < 412 then found = candidate1
                elseif candidate2 > 0 and candidate2 < 412 then found = candidate2
                elseif candidate3 > 0 and candidate3 < 412 then found = candidate3 end

                if found > 0 and found ~= last_species then
                    console:log("!! LOGGING ENCOUNTER: ID " .. found)
                    local f = io.open("{bridge_path}", "w")
                    if f then f:write(tostring(found)); f:close() end
                    last_species = found
                elseif found == 0 then
                    last_species = 0
                end
            end
            
            callbacks:add("frame", checkEncounter)
            """
            with open(lua_path, "w") as f: f.write(lua_code)
            
            # Use absolute path for the script flag
            self.emulators.append(subprocess.Popen([emu, "-s", lua_path, rom]))

        QTimer.singleShot(2000, self.reposition_emulators)
        QTimer.singleShot(2500, self.launch_workers)
        QTimer.singleShot(3000, self.mute_all_but_first)
        self.is_tracking = True
        self.toggle_btn.setText("🛑 Stop Program"); self.toggle_btn.setStyleSheet("background-color: #e74c3c;")

    def launch_workers(self):
        script_path = os.path.abspath(sys.argv[0])
        debug_flag = "debug" if self.debug_check.isChecked() else "normal"
        for i in range(1, self.num_instances + 1):
            self.workers.append(subprocess.Popen([sys.executable, script_path, str(i), debug_flag]))

    def mute_all_but_first(self):
        for i, proc in enumerate(self.emulators): self.set_emu_audio(proc.pid, mute=(i != 0))

    def set_emu_audio(self, pid, mute=True):
        try:
            output = subprocess.check_output(["pactl", "list", "sink-inputs"]).decode()
            target_id, current_id = None, None
            for line in output.splitlines():
                if "Sink Input #" in line: current_id = line.split("#")[-1]
                if f'application.process.id = "{pid}"' in line: target_id = current_id; break
            if target_id: subprocess.run(["pactl", "set-sink-input-mute", target_id, "1" if mute else "0"])
        except: pass

    def spotlight_instance(self, index):
        if index >= len(self.emulators): return
        for i, proc in enumerate(self.emulators):
            self.set_emu_audio(proc.pid, mute=(i != index))
            if (i+1) in self.audio_indicators: self.audio_indicators[i+1].setVisible(i == index)

    def keyPressEvent(self, event):
        if event.text().isdigit():
            val = int(event.text())
            if 1 <= val <= self.num_instances: self.spotlight_instance(val - 1)
        super().keyPressEvent(event)

    def stop_program(self):
        for p in self.workers + self.emulators:
            try: p.terminate()
            except: pass
        self.workers, self.emulators = [], []
        self.is_tracking = False
        self.toggle_btn.setText("🚀 Start Program"); self.toggle_btn.setStyleSheet("background-color: #27ae60;")

    def update_display(self):
        gt, gg = 0, 0
        name = "None"
        for i in range(1, self.num_instances + 1):
            fp = os.path.join(self.data_dir, f"hunt_stats_{i}.json")
            if os.path.exists(fp):
                with open(fp, "r") as f:
                    d = json.load(f)
                    if i in self.instance_widgets:
                        self.instance_widgets[i][0].setText(f"Total: {d.get('total', 0)}")
                        self.instance_widgets[i][1].setText(f"Target: {d.get('target', 0)}")
                    gt += d.get("total", 0); gg += d.get("target", 0); name = d.get("target_name", "???")
        self.combined_total_lbl.setText(str(gt)); self.combined_target_lbl.setText(str(gg))
        self.target_name_lbl.setText(f"GLOBAL TARGET: {name.upper()}")

    def open_global_settings(self):
        dialog = QDialog(self); dialog.setWindowTitle("Set Target")
        l = QVBoxLayout(dialog); p_in = QLineEdit()
        comp = QCompleter(self.master_list); comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        p_in.setCompleter(comp); l.addWidget(QLabel("Target Pokemon:")); l.addWidget(p_in)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); l.addWidget(bb)
        if dialog.exec():
            new_t = p_in.text().strip().capitalize()
            for i in range(1, 10):
                f_p = os.path.join(self.data_dir, f"hunt_stats_{i}.json")
                # Ensure the file exists before writing to it
                if not os.path.exists(f_p):
                    with open(f_p, "w") as f: json.dump({"total": 0, "target": 0, "target_name": new_t}, f)
                else:
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

    def load_config(self):
        cp = os.path.join(self.data_dir, "config.json")
        return json.load(open(cp, "r")) if os.path.exists(cp) else {"emu_path": "/usr/bin/mgba-qt", "rom_path": ""}

    def save_config(self):
        cp = os.path.join(self.data_dir, "config.json")
        with open(cp, "w") as f: json.dump({"emu_path": self.emu_path.text(), "rom_path": self.rom_path.text()}, f)

    def update_instance_count(self):
        try:
            val = int(self.count_input.text())
            if 1 <= val <= 9: self.num_instances = val; self.build_grid()
        except: pass

# --------------------------------------------------
# WORKER CLASS
# --------------------------------------------------
POKEDEX = {
    111: "Rhyhorn", 115: "Kangaskhan", 123: "Scyther", 127: "Pinsir", 
    128: "Tauros", 46: "Paras", 47: "Parasect", 48: "Venonat", 
    49: "Venomoth", 102: "Exeggcute", 32: "Nidoran", 33: "Nidorino",
    29: "Nidoran", 30: "Nidorina", 113: "Chansey", 16: "Pidgey", 19: "Rattata"
}

class PokeTally(QWidget):
    def __init__(self, instance_id="1", debug_mode=False):
        super().__init__()
        self.data_dir = os.path.abspath("data")
        self.instance_id, self.debug_mode = instance_id, debug_mode
        self.bridge_file = os.path.join(self.data_dir, "bridge", f"found_{self.instance_id}.txt")
        self.file_path = os.path.join(self.data_dir, f"hunt_stats_{self.instance_id}.json")
        self.log_file = os.path.join(self.data_dir, f"worker_{self.instance_id}_log.txt")
        
        self.data = self.load_data()
        self.memory_timer = QTimer()
        self.memory_timer.timeout.connect(self.scan_memory)
        self.memory_timer.start(500)
        self.log(f"--- WORKER {self.instance_id} STARTED ---")

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        with open(self.log_file, "a") as f: f.write(f"[{ts}] {msg}\n")
        if self.debug_mode: print(f"[W{self.instance_id}] {msg}")

    def load_data(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f: return json.load(f)
        return {"total": 0, "target": 0, "target_name": "Rhyhorn"}

    def scan_memory(self):
        if os.path.exists(self.bridge_file):
            try:
                with open(self.bridge_file, "r") as f:
                    content = f.read().strip()
                    if not content: return
                    sid = int(content)
                
                p_name = POKEDEX.get(sid, f"Unknown_{sid}")
                self.log(f"Bridge Read: ID {sid} -> {p_name}")
                
                self.data['total'] += 1
                if p_name.upper() == self.data["target_name"].upper():
                    self.data['target'] += 1
                    self.log("MATCH FOUND! Target updated.")
                
                with open(self.file_path, "w") as f: json.dump(self.data, f)
                os.remove(self.bridge_file)
            except Exception as e:
                self.log(f"SCAN ERROR: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if len(sys.argv) == 1:
        window = MasterDashboard(); window.show()
    else:
        is_debug = (sys.argv[2] == "debug")
        worker = PokeTally(instance_id=sys.argv[1], debug_mode=is_debug)
    sys.exit(app.exec())