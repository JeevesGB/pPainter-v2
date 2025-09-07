import os
import sys
import struct
import subprocess
import json  
import PyQt6
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QColorDialog, QToolBar,
    QVBoxLayout, QWidget, QDockWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QInputDialog, QListWidget, QListWidgetItem,
    QMessageBox 
)
from PyQt6.QtGui import QImage, QPixmap, QColor, QPalette, QAction
from PyQt6.QtCore import Qt, QSize, QStandardPaths  
from PIL import Image


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource (works for dev and for PyInstaller)."""
    import sys, os
    try:
        base_path = sys._MEIPASS  # PyInstaller’s temp folder
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def _config_path() -> str:
    """Return a writable per-user config path (works in dev and PyInstaller)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not base:
        base = os.path.expanduser("~/.ppainter")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "ppainter_config.json")

def load_config() -> dict:
    path = _config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg: dict) -> None:
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def prompt_tim_bpp(parent):
    items = ["4 bpp (16 colors)", "8 bpp (256 colors)", "16 bpp (High Color)", "24 bpp (True Color)"]
    item, ok = QInputDialog.getItem(parent, "Select TIM Bit Depth", "Bit Depth:", items, 3, False)
    if not ok:
        return None
    return {0:4, 1:8, 2:16, 3:24}[items.index(item)]

def load_tim(filepath):
    """
    Load a PSX TIM file.
    Returns a dict: {'bpp', 'clut', 'data', 'width', 'height'}.
    'clut' is a list of (r,g,b) entries (None if no CLUT).
    'data' is a 2D array: either palette indices or (r,g,b) tuples.
    """
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'\x10\x00\x00\x00':
            raise ValueError("Not a TIM file (invalid magic)")
        flags = struct.unpack('<I', f.read(4))[0]
        bpp_flag = flags & 3
        clut_flag = bool(flags & 8)
        bpp = {0:4, 1:8, 2:16, 3:24}.get(bpp_flag)
        if bpp is None:
            raise ValueError("Unsupported TIM bit depth")
        clut = None
        if clut_flag:
            clut_len = struct.unpack('<I', f.read(4))[0]
            ox, oy, w16, h16 = struct.unpack('<HHHH', f.read(8))
            clut_bytes = f.read(clut_len - 12)
            count = w16 * h16
            clut = []
            for i in range(count):
                val = struct.unpack_from('<H', clut_bytes, i*2)[0]
                r = (val & 0x1F); g = (val >> 5) & 0x1F; b = (val >> 10) & 0x1F
                # Expand 5-bit to 8-bit
                r = (r << 3) | (r >> 2)
                g = (g << 3) | (g >> 2)
                b = (b << 3) | (b >> 2)
                clut.append((r, g, b))
        img_len = struct.unpack('<I', f.read(4))[0]
        ox, oy, w16, h16 = struct.unpack('<HHHH', f.read(8))
        img_bytes = f.read(img_len - 12)
        data = []
        if bpp == 4:
            px_width = w16 * 4
            offset = 0
            for y in range(h16):
                row = []
                for x in range(w16):
                    word = struct.unpack_from('<H', img_bytes, offset)[0]
                    offset += 2
                    for i in range(4):
                        idx = (word >> (4*i)) & 0xF
                        row.append(idx)
                data.append(row[:px_width])
        elif bpp == 8:
            px_width = w16 * 2
            offset = 0
            for y in range(h16):
                row = []
                for x in range(w16):
                    word = struct.unpack_from('<H', img_bytes, offset)[0]
                    offset += 2
                    lo = word & 0xFF
                    hi = (word >> 8) & 0xFF
                    row.append(lo); row.append(hi)
                data.append(row[:px_width])
        elif bpp == 16:
            offset = 0
            for y in range(h16):
                row = []
                for x in range(w16):
                    val = struct.unpack_from('<H', img_bytes, offset)[0]
                    offset += 2
                    r = val & 0x1F; g = (val >> 5) & 0x1F; b = (val >> 10) & 0x1F
                    r = (r << 3) | (r >> 2)
                    g = (g << 3) | (g >> 2)
                    b = (b << 3) | (b >> 2)
                    row.append((r, g, b))
                data.append(row)
        elif bpp == 24:
            px_width = (w16 * 2) // 3
            offset = 0
            for y in range(h16):
                row = []
                for x in range(px_width):
                    b = img_bytes[offset]; g = img_bytes[offset+1]; r = img_bytes[offset+2]
                    offset += 3
                    row.append((r, g, b))
                # align to 16-bit boundary
                offset = (y+1) * (w16 * 2)
                data.append(row)
        else:
            raise ValueError("Unsupported bit depth")
        return {'bpp': bpp, 'clut': clut, 'data': data, 'width': (px_width if bpp in (4,8,24) else w16), 'height': h16}

def save_tim(filepath, info):
    """
    Save a TIM file from the given image info dict.
    """
    bpp = info['bpp']; clut = info.get('clut'); data = info['data']
    width = info['width']; height = info['height']
    flags = {4:0, 8:1, 16:2, 24:3}[bpp]
    if clut: flags |= 0x8
    parts = []
    parts.append(b'\x10\x00\x00\x00')
    parts.append(struct.pack('<I', flags))
    if clut:
        size = len(clut)
        cw = size; ch = 1
        clut_block = []
        clut_block.append(struct.pack('<I', 12 + 2*size))
        clut_block.append(struct.pack('<HH', 0, 0))
        clut_block.append(struct.pack('<HH', cw, ch))
        for (r, g, b) in clut:
            r5 = r>>3; g5 = g>>3; b5 = b>>3
            val = (b5<<10)|(g5<<5)|r5
            clut_block.append(struct.pack('<H', val))
        parts.append(b''.join(clut_block))
    # Image block
    if bpp == 4:   w16 = (width+3)//4
    elif bpp == 8: w16 = (width+1)//2
    elif bpp == 16: w16 = width
    elif bpp == 24: w16 = (3*width+1)//2
    else: w16 = width
    h16 = height
    pixels = bytearray()
    if bpp == 4:
        for row in data:
            for x in range(w16):
                val = 0
                for i in range(4):
                    idx = row[x*4+i] if x*4+i < len(row) else 0
                    val |= (idx&0xF) << (4*i)
                pixels += struct.pack('<H', val)
    elif bpp == 8:
        for row in data:
            for x in range(w16):
                lo = row[x*2] if x*2 < len(row) else 0
                hi = row[x*2+1] if x*2+1 < len(row) else 0
                pixels += struct.pack('<H', (hi<<8)|lo)
    elif bpp == 16:
        for row in data:
            for (r, g, b) in row:
                val = ((b>>3)<<10)|((g>>3)<<5)|(r>>3)
                pixels += struct.pack('<H', val)
    elif bpp == 24:
        for row in data:
            for (r, g, b) in row:
                pixels += bytes((b, g, r))
        row_len = w16*2
        for y in range(height):
            used = len(data[y])*3
            pad = row_len - used
            if pad>0:
                pixels += b'\x00'*pad
    img_len = 12 + len(pixels)
    img_block = []
    img_block.append(struct.pack('<I', img_len))
    img_block.append(struct.pack('<HH', 0, 0))
    img_block.append(struct.pack('<HH', w16, h16))
    img_block.append(pixels)
    parts.append(b''.join(img_block))
    with open(filepath, 'wb') as f:
        for part in parts:
            f.write(part)

class Canvas(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.last_pos = None

    def mousePressEvent(self, event):
        if not self.pixmap(): return
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().on_canvas_mouse_press(event.pos())
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if not self.pixmap(): return
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.window().on_canvas_mouse_move(event.pos())
        self.last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if not self.pixmap(): return
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().on_canvas_mouse_release(event.pos())
        self.last_pos = None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ppainter-v1.0.1")
        app_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = resource_path("ico.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.image_info = None
        self.current_file = None
        self.palette_mode = False
        self.current_tool = 'brush'
        self.brush_color = QColor(0,0,0,255)
        self.eraser_color = QColor(0,0,0,0)
        self.brush_index = 0

        # NEW: config
        self.config = load_config()

        self.canvas = Canvas(self)
        app_dir = os.path.dirname(os.path.abspath(__file__))
        bg_path = resource_path("ico.png").replace("\\", "/")

        self.canvas.setStyleSheet(
            f"QLabel {{"
            f"background-image: url({bg_path});"
            f"background-repeat: no-repeat;"
            f"background-position: center;"
            f"background-color: #f0f0f0;"
            f"}}"
        )
        self.canvas.setBackgroundRole(QPalette.ColorRole.Base)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.canvas.setScaledContents(True)
        self.setCentralWidget(self.canvas)

        self.create_actions()
        self.create_toolbar()
        self.create_palette_editor()
        self.create_file_browser()

        # NEW: Ask once on first run to link GTVolTools
        if "voltools_path" not in self.config:
            reply = QMessageBox.question(
                self, "Link GTVolTools?",
                "Would you like to link GTVolTools so it can be launched from ppainter?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._prompt_and_save_voltools_path()

    def create_actions(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(app_dir, "icons")

        self.open_act = QAction(QIcon(os.path.join(icon_dir, "open.png")), "", self)
        self.open_act.setToolTip("Open File")
        self.open_act.triggered.connect(self.open_file)

        self.open_folder_act = QAction(QIcon(os.path.join(icon_dir, "folder.png")), "", self)
        self.open_folder_act.setToolTip("Open Folder")
        self.open_folder_act.triggered.connect(self.open_folder)

        self.save_act = QAction(QIcon(os.path.join(icon_dir, "save.png")), "", self)
        self.save_act.setToolTip("Save")
        self.save_act.triggered.connect(self.save_file)

        self.save_as_act = QAction(QIcon(os.path.join(icon_dir, "save_as.png")), "", self)
        self.save_as_act.setToolTip("Save As")
        self.save_as_act.triggered.connect(self.save_file_as)

        self.export_png_act = QAction(QIcon(os.path.join(icon_dir, "export.png")), "", self)
        self.export_png_act.setToolTip("Export to PNG")
        self.export_png_act.triggered.connect(self.export_png)
        
    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setIconSize(QSize(24, 24))   
        self.addToolBar(toolbar)

        toolbar.addAction(self.open_act)
        toolbar.addAction(self.open_folder_act)
        toolbar.addAction(self.save_act)
        toolbar.addAction(self.save_as_act)
        toolbar.addAction(self.export_png_act)

        # --- GTVolTools launcher: always present, icon changes ---
        self.voltools_act = QAction(self)
        self.voltools_act.setToolTip("Launch GTVolTools (click to link if unlinked)")
        self.voltools_act.triggered.connect(self.on_voltools_clicked)
        self._update_voltools_icon()  # NEW
        toolbar.addAction(self.voltools_act)

        app_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(app_dir, "icons")
        convert_icon_path = os.path.join(icon_dir, "save_as.png")
        convert_act = QAction(QIcon(convert_icon_path), "Convert PNG to TIM", self)
        convert_act.setToolTip("Convert PNG to TIM")
        convert_act.triggered.connect(self.convert_png_to_tim)
        toolbar.addAction(convert_act)

        # NEW
    def _voltools_path(self) -> str | None:
        path = self.config.get("voltools_path")
        if path and os.path.isfile(path):
            return path
        return None

    # NEW
    def _update_voltools_icon(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(app_dir, "icons")
        icon_name = "voltools_linked.png" if self._voltools_path() else "voltools_unlinked.png"
        self.voltools_act.setIcon(QIcon(os.path.join(icon_dir, icon_name)))

    # NEW
    def _prompt_and_save_voltools_path(self):
        # Default Windows filter first; still allow all files so users on other OSes can pick scripts if needed
        exe_path, _ = QFileDialog.getOpenFileName(
            self, "Select GTVolTools executable",
            "", "GTVolTools (GTVolToolGui.exe);;Executables (*.exe);;All Files (*)"
        )
        if exe_path:
            self.config["voltools_path"] = exe_path
            save_config(self.config)
            self._update_voltools_icon()

    # NEW
    def on_voltools_clicked(self):
        path = self._voltools_path()
        if not path:
            # Not linked yet → offer to link now
            reply = QMessageBox.question(
                self, "Link GTVolTools?",
                "GTVolTools is not linked. Would you like to select it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._prompt_and_save_voltools_path()
            return

        # Linked → launch
        try:
            subprocess.Popen([path])
        except Exception as e:
            QMessageBox.warning(self, "Failed to launch GTVolTools", f"{e}")

    
    def create_file_browser(self):
        self.file_dock = QDockWidget("Files", self)
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.open_file_from_list)
        self.file_dock.setWidget(self.file_list)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.file_dock)
        
    def launch_voltools(self):
        voltools_path = r"C:\Path\To\GTVolTools\GTVolToolGui.exe"
        try:
            subprocess.Popen([voltools_path])
        except Exception as e:
            print(f"Failed to launch GTVolTools: {e}")
        
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        self.file_list.clear()
        exts = (".tim", ".png", ".jpg", ".bmp")
        for name in sorted(os.listdir(folder)):
           if name.lower().endswith(exts):
                full_path = os.path.join(folder, name)
                item = QListWidgetItem(name)  # show only filename
                item.setData(Qt.ItemDataRole.UserRole, full_path)  # keep full path hidden
                self.file_list.addItem(item)
        if self.file_list.count() > 0:
            self.file_dock.show()

    def open_file_from_list(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.open_file_from_path(path)

    def open_file_from_path(self, path):
        if path.lower().endswith(".tim"):
            try:
                info = load_tim(path)
            except Exception as e:
                print("Error:", e); return
            self.image_info = info; self.current_file = path
            if info['clut'] is not None and info['bpp'] in (4, 8):
                self.palette_mode = True; self.brush_index = 0
                self.populate_palette_table(); self.palette_dock.show()
            else:
                self.palette_mode = False; self.palette_dock.hide()
            self.update_canvas()
        else:
            try:
                pil_img = Image.open(path).convert("RGBA")
            except Exception as e:
                print("Error:", e); return
            width, height = pil_img.size
            pixels = list(pil_img.getdata())
            rows = []
            for y in range(height):
                row = []
                for x in range(width):
                    r, g, b, a = pixels[y*width + x]
                    row.append((r, g, b))
                rows.append(row)
            self.image_info = {'bpp':24, 'clut':None, 'data':rows,
                               'width':width, 'height':height}
            self.current_file = path; self.palette_mode = False; self.palette_dock.hide()
            self.update_canvas()

    def convert_png_to_tim(self):
        if not self.image_info or self.image_info['bpp'] != 24 or self.image_info['clut'] is not None:
            return  # Only allow conversion for loaded PNGs (24bpp, no palette)
        path, _ = QFileDialog.getSaveFileName(self, "Save TIM", "", "TIM (*.tim)")
        if not path:
            return
        bpp = prompt_tim_bpp(self)
        if bpp is None:
            return
        pil_img = Image.new("RGB", (self.image_info['width'], self.image_info['height']))
        for y, row in enumerate(self.image_info['data']):
            for x, pix in enumerate(row):
                pil_img.putpixel((x, y), pix)
        if bpp == 4:
            pil_img = pil_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
            pal = pil_img.getpalette()[:48]
            clut = [(pal[i], pal[i+1], pal[i+2]) for i in range(0, 48, 3)]
            data = []
            for y in range(pil_img.height):
                row = []
                for x in range(pil_img.width):
                    row.append(pil_img.getpixel((x, y)))
                data.append(row)
            info = {'bpp': 4, 'clut': clut, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
        elif bpp == 8:
            pil_img = pil_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
            pal = pil_img.getpalette()[:768]
            clut = [(pal[i], pal[i+1], pal[i+2]) for i in range(0, 768, 3)]
            data = []
            for y in range(pil_img.height):
                row = []
                for x in range(pil_img.width):
                    row.append(pil_img.getpixel((x, y)))
                data.append(row)
            info = {'bpp': 8, 'clut': clut, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
        elif bpp == 16:
            data = []
            for y in range(pil_img.height):
                row = []
                for x in range(pil_img.width):
                    r, g, b = pil_img.getpixel((x, y))
                    row.append((r, g, b))
                data.append(row)
            info = {'bpp': 16, 'clut': None, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
        else:  # 24bpp
            data = []
            for y in range(pil_img.height):
                row = []
                for x in range(pil_img.width):
                    r, g, b = pil_img.getpixel((x, y))
                    row.append((r, g, b))
                data.append(row)
            info = {'bpp': 24, 'clut': None, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
        save_tim(path, info)    

    def create_palette_editor(self):
        self.palette_dock = QDockWidget("Palette", self)
        self.palette_table = QTableWidget()
        self.palette_table.setColumnCount(2)
        self.palette_table.setHorizontalHeaderLabels(["Index", "Color"])
        self.palette_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.palette_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.palette_table.cellDoubleClicked.connect(self.edit_palette_color)
        self.palette_table.cellClicked.connect(self.select_palette_color)
        self.palette_dock.setWidget(self.palette_table)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.palette_dock)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "",
                                              "TIM (*.tim);;Image Files (*.png *.jpg *.bmp)")
        if not path: return
        if path.lower().endswith(".tim"):
            try:
                info = load_tim(path)
            except Exception as e:
                print("Error:", e); return
            self.image_info = info; self.current_file = path
            if info['clut'] is not None and info['bpp'] in (4, 8):
                self.palette_mode = True; self.brush_index = 0
                self.populate_palette_table(); self.palette_dock.show()
            else:
                self.palette_mode = False; self.palette_dock.hide()
            self.update_canvas()
        else:
            try:
                pil_img = Image.open(path).convert("RGBA")
            except Exception as e:
                print("Error:", e); return
            width, height = pil_img.size
            pixels = list(pil_img.getdata())
            rows = []
            for y in range(height):
                row = []
                for x in range(width):
                    r, g, b, a = pixels[y*width + x]
                    row.append((r, g, b))
                rows.append(row)
            self.image_info = {'bpp':24, 'clut':None, 'data':rows, 'width':width, 'height':height}
            self.current_file = path; self.palette_mode = False; self.palette_dock.hide()
            self.update_canvas()

    def update_canvas(self):
        if not self.image_info: return
        w = self.image_info['width']; h = self.image_info['height']
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        if self.palette_mode and self.image_info['clut']:
            pal = self.image_info['clut']
            for y, row in enumerate(self.image_info['data']):
                for x, idx in enumerate(row):
                    if 0 <= idx < len(pal):
                        r, g, b = pal[idx]
                    else:
                        r, g, b = 0, 0, 0
                    img.setPixelColor(x, y, QColor(r, g, b, 255))
        else:
            for y, row in enumerate(self.image_info['data']):
                for x, pixel in enumerate(row):
                    if isinstance(pixel, tuple):
                        r, g, b = pixel
                    else:
                        r, g, b = pixel.red(), pixel.green(), pixel.blue()
                    img.setPixelColor(x, y, QColor(r, g, b, 255))
        self.canvas.setPixmap(QPixmap.fromImage(img))
        self.canvas.adjustSize()

    def set_tool(self, tool):
        self.current_tool = tool

    def choose_color(self):
        color = QColorDialog.getColor(self.brush_color, self, "Select Color")
        if color.isValid():
            self.brush_color = color
            if self.palette_mode and self.image_info['clut']:
                best_idx = 0; best_dist = float('inf')
                for i, (r, g, b) in enumerate(self.image_info['clut']):
                    dr = r-color.red(); dg = g-color.green(); db = b-color.blue()
                    dist = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist; best_idx = i
                self.brush_index = best_idx

    def populate_palette_table(self):
        pal = self.image_info['clut'] or []
        count = len(pal)
        self.palette_table.setRowCount(count)
        for i, (r, g, b) in enumerate(pal):
            idx_item = QTableWidgetItem(str(i))
            color_item = QTableWidgetItem()
            color_item.setBackground(QColor(r, g, b))
            self.palette_table.setItem(i, 0, idx_item)
            self.palette_table.setItem(i, 1, color_item)

    def select_palette_color(self, row, col):
        if col == 1:
            self.brush_index = row

    def edit_palette_color(self, row, col):
        if col == 1 and self.image_info.get('clut', None):
            old = self.image_info['clut'][row]
            initial = QColor(old[0], old[1], old[2])
            color = QColorDialog.getColor(initial, self, "Edit Palette Color")
            if color.isValid():
                self.image_info['clut'][row] = (color.red(), color.green(), color.blue())
                item = self.palette_table.item(row, 1)
                if item: item.setBackground(color)
                self.update_canvas()

    def on_canvas_mouse_press(self, pos):
        x, y = pos.x(), pos.y()
        if not self.image_info: return
        if self.current_tool == 'brush':
            if self.palette_mode:   self.set_index(x, y, self.brush_index)
            else:                  self.set_color(x, y, self.brush_color)
        elif self.current_tool == 'eraser':
            if self.palette_mode:   self.set_index(x, y, 0)
            else:                  self.set_color(x, y, self.eraser_color)
        elif self.current_tool == 'fill':
            if self.palette_mode:
                tgt = self.get_index(x, y)
                self.flood_fill_index(x, y, tgt, self.brush_index)
            else:
                tgt = self.get_color(x, y)
                self.flood_fill_color(x, y, tgt, self.brush_color)
        elif self.current_tool == 'picker':
            if self.palette_mode:   self.brush_index = self.get_index(x, y)
            else:                  self.brush_color = self.get_color(x, y)
        self.update_canvas()
        self.last_pos = (x, y)

    def on_canvas_mouse_move(self, pos):
        if not self.image_info or not self.last_pos: return
        x, y = pos.x(), pos.y()
        x0, y0 = self.last_pos
        dx = x - x0; dy = y - y0
        steps = max(abs(dx), abs(dy))
        for i in range(steps+1):
            xi = int(x0 + dx * i / steps) if steps else x
            yi = int(y0 + dy * i / steps) if steps else y
            if self.current_tool == 'brush':
                if self.palette_mode:   self.set_index(xi, yi, self.brush_index)
                else:                  self.set_color(xi, yi, self.brush_color)
            elif self.current_tool == 'eraser':
                if self.palette_mode:   self.set_index(xi, yi, 0)
                else:                  self.set_color(xi, yi, self.eraser_color)
        self.update_canvas()
        self.last_pos = (x, y)

    def on_canvas_mouse_release(self, pos):
        self.last_pos = None

    def set_color(self, x, y, color):
        if 0 <= x < self.image_info['width'] and 0 <= y < self.image_info['height']:
            self.image_info['data'][y][x] = (color.red(), color.green(), color.blue())

    def set_index(self, x, y, idx):
        if 0 <= x < self.image_info['width'] and 0 <= y < self.image_info['height']:
            self.image_info['data'][y][x] = idx

    def get_color(self, x, y):
        if not (0 <= x < self.image_info['width'] and 0 <= y < self.image_info['height']):
            return QColor(0,0,0,255)
        pix = self.image_info['data'][y][x]
        if isinstance(pix, tuple):
            r,g,b = pix
        else:
            r,g,b = pix.red(), pix.green(), pix.blue()
        return QColor(r,g,b,255)

    def get_index(self, x, y):
        if not (0 <= x < self.image_info['width'] and 0 <= y < self.image_info['height']):
            return 0
        return self.image_info['data'][y][x]

    def flood_fill_color(self, x, y, target_color, new_color):
        width = self.image_info['width']; height = self.image_info['height']
        tgt = (target_color.red(), target_color.green(), target_color.blue())
        rep = (new_color.red(), new_color.green(), new_color.blue())
        if tgt == rep: return
        visited = set(); stack = [(x,y)]
        while stack:
            px, py = stack.pop()
            if (px,py) in visited or not (0<=px<width and 0<=py<height): continue
            pix = self.image_info['data'][py][px]
            curr = pix if isinstance(pix, tuple) else (pix.red(), pix.green(), pix.blue())
            if curr == tgt:
                self.image_info['data'][py][px] = rep
                visited.add((px,py))
                stack.extend([(px+1,py),(px-1,py),(px,py+1),(px,py-1)])

    def flood_fill_index(self, x, y, target_idx, new_idx):
        width = self.image_info['width']; height = self.image_info['height']
        if target_idx == new_idx: return
        visited = set(); stack = [(x,y)]
        while stack:
            px, py = stack.pop()
            if (px,py) in visited or not (0<=px<width and 0<=py<height): continue
            if self.image_info['data'][py][px] == target_idx:
                self.image_info['data'][py][px] = new_idx
                visited.add((px,py))
                stack.extend([(px+1,py),(px-1,py),(px,py+1),(px,py-1)])

    def _get_rgb_from_pixel(self, pix):
        """Helper method to extract RGB values from pixel data"""
        if self.palette_mode and self.image_info.get('clut'):
            # For palette mode, pix is an index
            if isinstance(pix, int) and 0 <= pix < len(self.image_info['clut']):
                return self.image_info['clut'][pix]
            else:
                return (0, 0, 0)  # Default color for invalid index
        elif isinstance(pix, tuple):
            # Direct RGB tuple
            return pix
        elif hasattr(pix, 'red'):
            # QColor object
            return (pix.red(), pix.green(), pix.blue())
        else:
            # Fallback
            return (0, 0, 0)

    def save_file(self):
        if not self.current_file:
            self.save_file_as()
            return
        if self.current_file.lower().endswith(".tim"):
            save_tim(self.current_file, self.image_info)
        else:
            fmt = self.current_file.split('.')[-1].upper()
            img = QImage(self.image_info['width'], self.image_info['height'], QImage.Format.Format_ARGB32)
            for y,row in enumerate(self.image_info['data']):
                for x,pix in enumerate(row):
                    r, g, b = self._get_rgb_from_pixel(pix)
                    img.setPixelColor(x,y, QColor(r,g,b))
            img.save(self.current_file, fmt)

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", 
                                              "TIM (*.tim);;PNG (*.png);;BMP (*.bmp);;JPEG (*.jpg)")
        if not path: return
        if path.lower().endswith(".tim"):
            if self.image_info['clut'] is None and self.image_info['bpp'] == 24:
                bpp = prompt_tim_bpp(self)
                if bpp is None: return
                pil_img = Image.new("RGB", (self.image_info['width'], self.image_info['height']))
                for y, row in enumerate(self.image_info['data']):
                    for x, pix in enumerate(row):
                        pil_img.putpixel((x, y), pix)
                if bpp == 4:
                    pil_img = pil_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
                    pal = pil_img.getpalette()[:48]  # 16 colors * 3 channels
                    clut = [(pal[i], pal[i+1], pal[i+2]) for i in range(0, 48, 3)]
                    data = []
                    for y in range(pil_img.height):
                        row = []
                        for x in range(pil_img.width):
                            row.append(pil_img.getpixel((x, y)))
                        data.append(row)
                    info = {'bpp': 4, 'clut': clut, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
                elif bpp == 8:
                    pil_img = pil_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                    pal = pil_img.getpalette()[:768]  # 256 colors * 3 channels
                    clut = [(pal[i], pal[i+1], pal[i+2]) for i in range(0, 768, 3)]
                    data = []
                    for y in range(pil_img.height):
                        row = []
                        for x in range(pil_img.width):
                            row.append(pil_img.getpixel((x, y)))
                        data.append(row)
                    info = {'bpp': 8, 'clut': clut, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
                elif bpp == 16:
                    data = []
                    for y in range(pil_img.height):
                        row = []
                        for x in range(pil_img.width):
                            r, g, b = pil_img.getpixel((x, y))
                            row.append((r, g, b))
                        data.append(row)
                    info = {'bpp': 16, 'clut': None, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
                else: # 24bpp
                    data = []
                    for y in range(pil_img.height):
                        row = []
                        for x in range(pil_img.width):
                            r, g, b = pil_img.getpixel((x, y))
                            row.append((r, g, b))
                        data.append(row)
                    info = {'bpp': 24, 'clut': None, 'data': data, 'width': pil_img.width, 'height': pil_img.height}
                save_tim(path, info)
            else:
                save_tim(path, self.image_info)
        else:
            fmt = path.split('.')[-1].upper()
            img = QImage(self.image_info['width'], self.image_info['height'], QImage.Format.Format_ARGB32)
            for y,row in enumerate(self.image_info['data']):
                for x,pix in enumerate(row):
                    r, g, b = self._get_rgb_from_pixel(pix)
                    img.setPixelColor(x,y, QColor(r,g,b))
            img.save(path, fmt)
        self.current_file = path

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export to PNG", "", "PNG (*.png)")
        if not path: return
        img = QImage(self.image_info['width'], self.image_info['height'], QImage.Format.Format_ARGB32)
        for y,row in enumerate(self.image_info['data']):
            for x,pix in enumerate(row):
                r, g, b = self._get_rgb_from_pixel(pix)
                img.setPixelColor(x,y, QColor(r,g,b))
        img.save(path, "PNG")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1500,1000)
    win.show()
    sys.exit(app.exec())