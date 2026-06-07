"""
Abre-Cursos Pro - Automatizador de clases por horario
- Modo Vacaciones
- Notificaciones configurables con sonido personalizado
- Evasión de pestañas basura de Zoom y MS Teams
- Tarjetas interactivas con botones legibles y Tooltips
- Actualizaciones automáticas y manuales integradas
- Hilos seguros y soporte total de temas dinámicos (Tuplas de color)
- Bandeja del sistema dinámica con acceso rápido
- Historial persistente con tarjetas estadísticas
- Detector de conflictos de horario
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from datetime import datetime, timedelta
from pathlib import Path
from winotify import Notification, audio
import pystray
import subprocess

# Versión del programa y repositorio
VERSION = "2.2.0"
GITHUB_USER = "Francoisxd"
GITHUB_REPO = "abre-cursos"

# Rutas
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    ICON_FILE = Path(sys._MEIPASS) / "icono.ico"
else:
    BASE_DIR = Path(__file__).parent
    ICON_FILE = BASE_DIR / "icono.ico"
    
DATA_FILE = BASE_DIR / "cursos.json"
LOG_FILE  = BASE_DIR / "historial.log"

DIAS      = ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"]
DIAS_FULL = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

data_lock = threading.RLock()

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)
        
    def show(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        bg = "#2d2d2d" if ctk.get_appearance_mode() == "Dark" else "#ffffff"
        fg = "#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000"
        border = "#444444" if ctk.get_appearance_mode() == "Dark" else "#cccccc"
        
        label = tk.Label(tw, text=self.text, justify="left",
                         background=bg, foreground=fg,
                         highlightbackground=border, highlightcolor=border,
                         highlightthickness=1,
                         font=("Segoe UI", 9), padx=6, pady=3)
        label.pack()
        
    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

def cargar_datos():
    with data_lock:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        data = {"version": 2, "settings": {"vacaciones": False, "tolerancia_min": 30, "notif_anticipacion": 5, "notif_sonido": "Reminder"}, "cursos": data}
                    if "settings" not in data:
                        data["settings"] = {"vacaciones": False, "tolerancia_min": 30, "notif_anticipacion": 5, "notif_sonido": "Reminder"}
                    else:
                        if "tolerancia_min" not in data["settings"]:
                            data["settings"]["tolerancia_min"] = 30
                        if "notif_anticipacion" not in data["settings"]:
                            data["settings"]["notif_anticipacion"] = 5
                        if "notif_sonido" not in data["settings"]:
                            data["settings"]["notif_sonido"] = "Reminder"
                    return data
            except Exception:
                pass
        return {"version": 2, "settings": {"vacaciones": False, "tolerancia_min": 30, "notif_anticipacion": 5, "notif_sonido": "Reminder"}, "cursos": []}

def guardar_datos(datos):
    with data_lock:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

def optimizar_url(url):
    if "zoom.us/j/" in url:
        try:
            path = urllib.parse.urlparse(url).path
            confno = path.split("/j/")[-1]
            query = urllib.parse.urlparse(url).query
            pwd = urllib.parse.parse_qs(query).get("pwd", [""])[0]
            
            zoom_url = f"zoommtg://zoom.us/join?action=join&confno={confno}"
            if pwd: zoom_url += f"&pwd={pwd}"
            return zoom_url
        except: return url
    elif "teams.microsoft.com/l/meetup-join/" in url:
        try:
            teams_url = url.replace("https://", "msteams://").replace("http://", "msteams://")
            return teams_url
        except: return url
    return url

def abrir_en_navegador(url, app=None):
    if app:
        browser_choice = app.datos.get("settings", {}).get("browser", "Predeterminado")
    else:
        browser_choice = "Predeterminado"

    if url.startswith(("zoommtg://", "msteams://")):
        webbrowser.open(url)
        return

    if browser_choice == "Predeterminado":
        webbrowser.open(url)
    elif browser_choice == "Chrome":
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "chrome", url], creationflags=0x08000000)
        except Exception:
            webbrowser.open(url)
    elif browser_choice == "Edge":
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "msedge", url], creationflags=0x08000000)
        except Exception:
            webbrowser.open(url)
    elif browser_choice == "Firefox":
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "firefox", url], creationflags=0x08000000)
        except Exception:
            webbrowser.open(url)
    elif browser_choice == "Brave":
        try:
            import winreg
            brave_path = None
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe") as key:
                        brave_path = winreg.QueryValue(key, None)
                        break
                except FileNotFoundError:
                    continue
            if brave_path:
                subprocess.Popen([brave_path, url])
            else:
                subprocess.Popen(["cmd.exe", "/c", "start", "brave", url], creationflags=0x08000000)
        except Exception:
            webbrowser.open(url)

fired_today = {}
notified_today = {}

def scheduler_loop(app):
    while True:
        now = datetime.now()
        day_app = (now.weekday() + 1) % 7
        fecha = now.strftime("%Y-%m-%d")
        now_min = now.hour * 60 + now.minute
        
        with data_lock:
            vacaciones = app.datos.get("settings", {}).get("vacaciones", False)
            tolerancia = app.datos.get("settings", {}).get("tolerancia_min", 30)
            anticipacion = app.datos.get("settings", {}).get("notif_anticipacion", 5)
            sound_type = app.datos.get("settings", {}).get("notif_sonido", "Reminder")
            cursos = [dict(c) for c in app.datos.get("cursos", [])]

        for curso in cursos:
            if not curso.get("activo", True): continue
            if day_app not in curso.get("dias", []): continue

            curso_min = int(curso["hora"]) * 60 + int(curso["minuto"])
            diff = now_min - curso_min
            key = f"{curso['id']}-{fecha}-{curso['hora']}:{curso['minuto']}"

            if anticipacion > 0 and diff == -anticipacion and key not in notified_today and not vacaciones:
                notified_today[key] = True
                try:
                    toast = Notification(app_id="AbreCursos", title=f"Clase en {anticipacion} minutos", msg=f"Prepárate, tu curso '{curso['nombre']}' empezará pronto.", duration="short")
                    
                    # Map sound settings
                    if sound_type == "Alarm":
                        toast.set_audio(audio.LoopingAlarm, loop=False)
                    elif sound_type == "SMS":
                        toast.set_audio(audio.SMS, loop=False)
                    elif sound_type == "Mail":
                        toast.set_audio(audio.Mail, loop=False)
                    elif sound_type == "Silencioso":
                        toast.set_audio(audio.Silent, loop=False)
                    else:
                        toast.set_audio(audio.Reminder, loop=False)
                        
                    toast.show()
                except Exception as e:
                    print(f"Error notification: {e}")

            if 0 <= diff <= tolerancia:
                if key in fired_today: continue
                fired_today[key] = True
                
                if vacaciones:
                    app.agregar_log(f"Omitido (Modo Vacaciones): {curso['nombre']} ({now.strftime('%d/%m/%Y %H:%M')})")
                    continue
                    
                final_url = optimizar_url(curso["url"])
                abrir_en_navegador(final_url, app)
                extra = f" (con {diff} min de retraso)" if diff > 0 else ""
                app.agregar_log(f"Abierto: {curso['nombre']}{extra} ({now.strftime('%d/%m/%Y %H:%M')})")
        time.sleep(15)

def check_for_updates(quiet=True, app=None):
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/update.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        latest_version = data.get("version", "")
        download_url = data.get("url", "")
        changelog = data.get("changelog", "Sin descripción de cambios.")
        
        if latest_version and latest_version != VERSION:
            if app:
                app.root.after(0, lambda: app.mostrar_ventana_actualizacion(latest_version, download_url, changelog))
        else:
            if not quiet and app:
                app.root.after(0, lambda: messagebox.showinfo("Actualización", "¡Ya tienes la última versión instalada!"))
    except Exception as e:
        if not quiet and app:
            app.root.after(0, lambda: messagebox.showerror("Actualización", f"No se pudo verificar actualizaciones:\nEl repositorio aún no existe o está inaccesible."))

class AbreCursosApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Abre-Cursos Pro")
        self.root.geometry("880x730")
        self.root.minsize(850, 650)
        self.root.protocol("WM_DELETE_WINDOW", self.ocultar)
        self.datos = cargar_datos()
        self.log_lines = []
        self.editing_id = None
        self._build_ui()
        threading.Thread(target=scheduler_loop, args=(self,), daemon=True).start()
        threading.Thread(target=check_for_updates, args=(True, self), daemon=True).start()
        self._tick()

    def _build_ui(self):
        # Configurar colores oscuros globales para estética premium de Abre-Cursos Pro
        self.root.configure(fg_color="#121212")

        # 1. Top Bar: Título y versión
        title_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(15, 0))
        
        lbl_title = ctk.CTkLabel(title_frame, text="Abre-Cursos Pro", font=ctk.CTkFont(size=20, weight="bold"), text_color="white")
        lbl_title.pack(side="left")
        
        lbl_version = ctk.CTkLabel(
            title_frame, 
            text=f"v{VERSION}", 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563eb",
            text_color="white",
            corner_radius=6,
            height=18
        )
        lbl_version.pack(side="left", padx=10)
        
        # Modo vacaciones
        self.lbl_vacaciones = ctk.CTkLabel(title_frame, text="🏖️ MODO VACACIONES ACTIVO", text_color="#d97706", font=ctk.CTkFont(weight="bold", size=12))
        if self.datos.get("settings", {}).get("vacaciones", False):
            self.lbl_vacaciones.pack(side="left", padx=20)
            
        # Próxima clase
        self.lbl_proxima = ctk.CTkLabel(title_frame, text="", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray")
        self.lbl_proxima.pack(side="right", padx=15)

        # Tabview principal
        self.tabview = ctk.CTkTabview(self.root, fg_color="transparent")
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        try:
            self.tabview._segmented_button.configure(
                selected_color="#2563eb",
                unselected_color="#1c1c1e"
            )
        except Exception:
            pass

        # Reloj estilo cápsula superpuesto en la esquina superior derecha alineado con las pestañas
        self.reloj_container = ctk.CTkFrame(
            self.root,
            fg_color="#121212",
            border_color="#2563eb",
            border_width=2,
            corner_radius=15,
            height=30
        )
        self.reloj_container.place(relx=1.0, x=-20, y=52, anchor="ne")
        self.reloj_container.pack_propagate(False)
        
        self.lbl_reloj = ctk.CTkLabel(
            self.reloj_container,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#60a5fa"
        )
        self.lbl_reloj.pack(expand=True, padx=15)

        self._tab_horario(self.tabview.add("Horario"))
        self._tab_historial(self.tabview.add("Historial"))
        self._tab_ajustes(self.tabview.add("Ajustes"))

    def _tab_horario(self, parent):
        # Contenedor del Formulario
        frm = ctk.CTkFrame(parent, fg_color="#1c1c1e", corner_radius=12)
        frm.pack(fill="x", padx=10, pady=(10, 10))

        self.v_nombre = tk.StringVar()
        self.v_url    = tk.StringVar()
        self.v_hora   = tk.StringVar(value="08")
        self.v_min    = tk.StringVar(value="00")
        self.v_dias   = [tk.BooleanVar() for _ in range(7)]

        # Fila 0: Nombre de Asignatura
        r0 = ctk.CTkFrame(frm, fg_color="transparent")
        r0.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(r0, text="Nombre de Asignatura", font=ctk.CTkFont(size=12, weight="bold"), text_color="white").pack(anchor="w")
        entry_nombre = ctk.CTkEntry(r0, textvariable=self.v_nombre, placeholder_text="Ej: Cálculo 2", fg_color="#121212", border_color="#2d2d30", height=35)
        entry_nombre.pack(fill="x", pady=(5, 0))

        # Fila 1: Enlace de Clase (URL)
        r1 = ctk.CTkFrame(frm, fg_color="transparent")
        r1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(r1, text="Enlace de Clase (URL)", font=ctk.CTkFont(size=12, weight="bold"), text_color="white").pack(anchor="w")
        entry_url = ctk.CTkEntry(r1, textvariable=self.v_url, placeholder_text="https://zoom.us/j/... o link de Teams", fg_color="#121212", border_color="#2d2d30", height=35)
        entry_url.pack(fill="x", pady=(5, 0))

        # Fila 2: Hora, Días y Botón
        r2 = ctk.CTkFrame(frm, fg_color="transparent")
        r2.pack(fill="x", padx=20, pady=(10, 15))
        
        # Columna 1: Hora de Programación
        time_frm = ctk.CTkFrame(r2, fg_color="transparent")
        time_frm.pack(side="left", fill="y")
        ctk.CTkLabel(time_frm, text="Hora de Programación (24h)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w", pady=(0, 5))
        
        time_inputs = ctk.CTkFrame(time_frm, fg_color="transparent")
        time_inputs.pack(anchor="w")
        cb_hora = ctk.CTkComboBox(time_inputs, variable=self.v_hora, values=[str(h).zfill(2) for h in range(24)], width=60, height=28, fg_color="#121212", border_color="#2d2d30")
        cb_hora.pack(side="left")
        ctk.CTkLabel(time_inputs, text=" : ", font=ctk.CTkFont(weight="bold"), text_color="white").pack(side="left", padx=2)
        cb_min = ctk.CTkComboBox(time_inputs, variable=self.v_min, values=[str(m).zfill(2) for m in range(0, 60, 5)], width=60, height=28, fg_color="#121212", border_color="#2d2d30")
        cb_min.pack(side="left")
        
        # Columna 2: Días de Clase
        dias_frm = ctk.CTkFrame(r2, fg_color="transparent")
        dias_frm.pack(side="left", fill="y", padx=(40, 0))
        ctk.CTkLabel(dias_frm, text="Días de Clase", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w", pady=(0, 5))
        
        dias_checks = ctk.CTkFrame(dias_frm, fg_color="transparent")
        dias_checks.pack(anchor="w")
        order_indices = [1, 2, 3, 4, 5, 6, 0] # Lun, Mar, Mie, Jue, Vie, Sab, Dom
        for idx in order_indices:
            ctk.CTkCheckBox(dias_checks, text=DIAS[idx], variable=self.v_dias[idx], width=50, height=20, font=ctk.CTkFont(size=11), fg_color="#2563eb").pack(side="left", padx=2)

        # Botón Agregar Curso (Derecha)
        self.btn_guardar = ctk.CTkButton(
            r2, 
            text="Agregar Curso", 
            command=self.guardar_curso, 
            fg_color="#1e7e34", 
            hover_color="#155724", 
            font=ctk.CTkFont(weight="bold", size=12),
            height=32,
            corner_radius=8
        )
        self.btn_guardar.pack(side="right", anchor="se", pady=(10, 0))
        
        self.btn_cancelar = ctk.CTkButton(
            r2, 
            text="Cancelar", 
            command=self.cancelar_edicion, 
            fg_color="gray", 
            hover_color="#555555", 
            font=ctk.CTkFont(weight="bold", size=12),
            height=32,
            corner_radius=8
        )

        # Contenedor para la lista de tarjetas
        lf = ctk.CTkFrame(parent, fg_color="transparent")
        lf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Fila de cabecera de la lista
        list_hdr = ctk.CTkFrame(lf, fg_color="transparent")
        list_hdr.pack(fill="x", padx=(10, 25), pady=(5, 5))
        ctk.CTkLabel(list_hdr, text="Cursos Programados", font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(side="left")
        ctk.CTkLabel(list_hdr, text="Estado / Acciones", font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(side="right")
        
        # Buscador
        sf = ctk.CTkFrame(lf, fg_color="transparent")
        sf.pack(fill="x", padx=5, pady=(5, 0))
        self.ent_search = ctk.CTkEntry(sf, placeholder_text="🔍 Buscar curso por nombre...", font=ctk.CTkFont(size=13), fg_color="#1c1c1e", border_color="#2d2d30")
        self.ent_search.pack(fill="x")
        self.ent_search.bind("<KeyRelease>", lambda e: self.refrescar_lista())
        
        self.scroll_frame = ctk.CTkScrollableFrame(lf, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.refrescar_lista()

    def _create_course_card(self, parent, c):
        is_active = c.get("activo", True)
        
        # Tarjeta compacta estilo premium
        card = ctk.CTkFrame(
            parent, 
            fg_color="#1c1c1e" if is_active else "#161618", 
            border_color="#2d2d30", 
            border_width=1, 
            corner_radius=8
        )
        
        # Details container (slim padded)
        details_frame = ctk.CTkFrame(card, fg_color="transparent")
        details_frame.pack(side="left", fill="both", expand=True, padx=15, pady=8)
        
        top_line = ctk.CTkFrame(details_frame, fg_color="transparent")
        top_line.pack(fill="x", anchor="w")
        
        lbl_nombre = ctk.CTkLabel(
            top_line, 
            text=c["nombre"].upper(), 
            font=ctk.CTkFont(size=13, weight="bold"), 
            text_color="white" if is_active else "gray", 
            anchor="w"
        )
        lbl_nombre.pack(side="left")
        
        # Cápsula de hora azul (con borde azul y fondo oscuro)
        time_frame = ctk.CTkFrame(
            top_line,
            fg_color="#121212" if is_active else "#27272a",
            border_color="#2563eb" if is_active else "gray",
            border_width=1,
            corner_radius=6
        )
        time_frame.pack(side="left", padx=10)
        
        lbl_hora = ctk.CTkLabel(
            time_frame,
            text=f"{c['hora']}:{c['minuto']}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#3b82f6" if is_active else "gray",
            fg_color="transparent"
        )
        lbl_hora.pack(padx=8, pady=1)
        
        # Fila inferior de detalles: Días • Plataforma • URL
        bottom_line = ctk.CTkFrame(details_frame, fg_color="transparent")
        bottom_line.pack(fill="x", anchor="w", pady=(3, 0))
        
        dias_str = ", ".join(DIAS[d] for d in sorted(c.get("dias", [])))
        lbl_dias = ctk.CTkLabel(bottom_line, text=dias_str, font=ctk.CTkFont(size=11), text_color="gray")
        lbl_dias.pack(side="left")
        
        ctk.CTkLabel(bottom_line, text=" • ", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
        
        # Determinar plataforma y estilo del badge
        url_lower = c["url"].lower()
        if "zoom" in url_lower:
            plat_text = " Zoom "
            plat_bg = "#1e7e34" if is_active else "#27272a"
            plat_fg = "white" if is_active else "gray"
        elif "teams" in url_lower:
            plat_text = " Teams "
            plat_bg = "#d9534f" if is_active else "#27272a"
            plat_fg = "white" if is_active else "gray"
        else:
            plat_text = " Web "
            plat_bg = "#0275d8" if is_active else "#27272a"
            plat_fg = "white" if is_active else "gray"
            
        lbl_platform = ctk.CTkLabel(
            bottom_line,
            text=plat_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=plat_bg,
            text_color=plat_fg,
            corner_radius=6
        )
        lbl_platform.pack(side="left")
        
        ctk.CTkLabel(bottom_line, text=" • ", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
        
        url_text = c["url"]
        if len(url_text) > 50:
            url_text = url_text[:47] + "..."
            
        # URL link packed horizontally in bottom_line
        lbl_url = ctk.CTkLabel(
            bottom_line, 
            text=url_text, 
            font=ctk.CTkFont(size=11), 
            text_color="#3b82f6" if is_active else "gray", 
            anchor="w", 
            cursor="hand2"
        )
        lbl_url.pack(side="left")
        lbl_url.bind("<Button-1>", lambda e, u=c["url"]: abrir_en_navegador(optimizar_url(u), self))
        ToolTip(lbl_url, "Hacer clic para abrir este enlace directamente en tu navegador.")

        # Actions (slim layout)
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.pack(side="right", fill="y", padx=15, pady=4)
        
        sw_var = tk.BooleanVar(value=is_active)
        sw = ctk.CTkSwitch(actions_frame, text="", variable=sw_var, width=40, command=lambda c_id=c["id"]: self._toggle_activo_by_id(c_id), fg_color="#2d2d30", progress_color="#2563eb")
        sw.pack(side="left", padx=8)
        ToolTip(sw, "Activar o desactivar temporalmente este curso del planificador.")
        
        btn_run = ctk.CTkButton(actions_frame, text="Abrir", font=ctk.CTkFont(size=11, weight="bold"), width=50, height=26, fg_color="#218838", hover_color="#1e7e34", text_color="white", command=lambda url=c["url"], nom=c["nombre"]: self._abrir_manualmente(url, nom))
        btn_run.pack(side="left", padx=2)
        ToolTip(btn_run, "Abre este curso de inmediato sin esperar al horario.")
        
        btn_edit = ctk.CTkButton(actions_frame, text="Editar", font=ctk.CTkFont(size=11, weight="bold"), width=50, height=26, fg_color="#d97706", hover_color="#b45309", text_color="white", command=lambda c_id=c["id"]: self._editar_by_id(c_id))
        btn_edit.pack(side="left", padx=2)
        ToolTip(btn_edit, "Carga los datos de este curso arriba para modificarlos.")
        
        btn_del = ctk.CTkButton(actions_frame, text="Borrar", font=ctk.CTkFont(size=11, weight="bold"), width=50, height=26, fg_color="#c82333", hover_color="#bd2130", text_color="white", command=lambda c_id=c["id"], nom=c["nombre"]: self._eliminar_by_id(c_id, nom))
        btn_del.pack(side="left", padx=2)
        ToolTip(btn_del, "Eliminar permanentemente este curso.")
        
        return card

    def _toggle_activo_by_id(self, c_id):
        with data_lock:
            c = next((x for x in self.datos.get("cursos", []) if x["id"] == c_id), None)
            if c:
                c["activo"] = not c.get("activo", True)
                guardar_datos(self.datos)
        self.refrescar_lista()

    def _abrir_manualmente(self, url, nombre):
        final_url = optimizar_url(url)
        abrir_en_navegador(final_url, self)
        self.agregar_log(f"Abierto manualmente: {nombre} ({datetime.now().strftime('%d/%m/%Y %H:%M')})")

    def _editar_by_id(self, c_id):
        with data_lock:
            c = next((x for x in self.datos.get("cursos", []) if x["id"] == c_id), None)
        if not c: return
        self.editing_id = c["id"]
        self.v_nombre.set(c["nombre"])
        self.v_url.set(c["url"])
        self.v_hora.set(c["hora"])
        self.v_min.set(c["minuto"])
        for i, v in enumerate(self.v_dias):
            v.set(i in c.get("dias", []))
        self.btn_guardar.configure(text="Guardar cambios")
        self.btn_cancelar.pack(side="right", padx=(0,8))

    def _eliminar_by_id(self, c_id, nombre):
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{nombre}'?"):
            with data_lock:
                self.datos["cursos"] = [x for x in self.datos["cursos"] if x["id"] != c_id]
                guardar_datos(self.datos)
            self.refrescar_lista()

    def _cargar_estadisticas(self):
        asistencias = 0
        retrasos = 0
        omitidos = 0
        
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        l = line.strip()
                        if l.startswith("Abierto:") or l.startswith("Abierto manualmente:"):
                            asistencias += 1
                        if "retraso" in l:
                            retrasos += 1
                        if "Omitido (Modo Vacaciones)" in l:
                            omitidos += 1
            except Exception as e:
                print(f"Error loading stats: {e}")
                
        self.lbl_stat_asis.configure(text=f"Asistencias\n{asistencias}")
        self.lbl_stat_retr.configure(text=f"Retrasos\n{retrasos}")
        self.lbl_stat_omit.configure(text=f"Omitidos\n{omitidos}")

    def _tab_historial(self, parent):
        # Stats container
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        row_colors = ("#eaeaea", "#262626")
        
        # Card 1: Asistencias
        c1 = ctk.CTkFrame(stats_frame, fg_color=row_colors, border_color=("#10b981", "#059669"), border_width=1, corner_radius=8, height=65)
        c1.pack(side="left", fill="both", expand=True, padx=5)
        c1.pack_propagate(False)
        self.lbl_stat_asis = ctk.CTkLabel(c1, text="Asistencias\n0", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#047857", "#10b981"))
        self.lbl_stat_asis.pack(expand=True)
        
        # Card 2: Retrasos
        c2 = ctk.CTkFrame(stats_frame, fg_color=row_colors, border_color=("#3b82f6", "#2563eb"), border_width=1, corner_radius=8, height=65)
        c2.pack(side="left", fill="both", expand=True, padx=5)
        c2.pack_propagate(False)
        self.lbl_stat_retr = ctk.CTkLabel(c2, text="Retrasos\n0", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#1d4ed8", "#3b82f6"))
        self.lbl_stat_retr.pack(expand=True)
        
        # Card 3: Omitidos
        c3 = ctk.CTkFrame(stats_frame, fg_color=row_colors, border_color=("#f59e0b", "#d97706"), border_width=1, corner_radius=8, height=65)
        c3.pack(side="left", fill="both", expand=True, padx=5)
        c3.pack_propagate(False)
        self.lbl_stat_omit = ctk.CTkLabel(c3, text="Omitidos\n0", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#b45309", "#f59e0b"))
        self.lbl_stat_omit.pack(expand=True)
        
        # Log Text Box
        self.txt_log = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_log.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        self.txt_log.configure(state="disabled")
        
        # Load physical log file if exists
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                self.txt_log.configure(state="normal")
                self.txt_log.insert("end", content)
                self.txt_log.see("end")
                self.txt_log.configure(state="disabled")
            except Exception as e:
                print(f"Error loading log file: {e}")
                
        self._cargar_estadisticas()
        
        ctk.CTkButton(parent, text="Borrar historial", command=self.limpiar_log, fg_color="#dc2626", hover_color="#b91c1c").pack(pady=(0,15))

    def _tab_ajustes(self, parent):
        ctk.CTkLabel(parent, text="Ajustes del programa", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 10))

        # Config frame scrollable for adjustments
        adj_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        adj_scroll.pack(fill="both", expand=True, padx=20, pady=5)

        row_colors = ("#eaeaea", "#262626")
        
        # 1. Modo vacaciones
        v_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        v_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(v_frm, text="🏖️ Modo Vacaciones:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        self.sw_vacaciones = ctk.CTkSwitch(v_frm, text="Desactivar cursos temporalmente", command=self.toggle_vacaciones, font=ctk.CTkFont(size=13))
        self.sw_vacaciones.pack(side="right", padx=20)
        if self.datos.get("settings", {}).get("vacaciones", False): self.sw_vacaciones.select()
        ToolTip(self.sw_vacaciones, "Habilita este modo para pausar temporalmente todas las clases automáticas (ej: vacaciones).")

        # 2. Tolerancia
        t_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        t_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(t_frm, text="⏳ Tolerancia de retraso:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        
        self.lbl_t_info = ctk.CTkLabel(t_frm, text="Permitir abrir hasta X min tarde", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray")
        self.lbl_t_info.pack(side="left", padx=10)
        
        tol_min = self.datos.get("settings", {}).get("tolerancia_min", 30)
        self.opt_tolerancia = ctk.CTkOptionMenu(t_frm, values=["5", "10", "15", "30", "45", "60"], command=self.cambiar_tolerancia)
        self.opt_tolerancia.pack(side="right", padx=20)
        self.opt_tolerancia.set(str(tol_min))
        ToolTip(self.opt_tolerancia, "Configura cuántos minutos después de la hora programada se puede seguir abriendo la clase.")

        # 3. Notificaciones anticipación
        n_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        n_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(n_frm, text="🔔 Notificar antes de empezar:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        
        notif_ant = self.datos.get("settings", {}).get("notif_anticipacion", 5)
        notif_str = "Desactivado" if notif_ant == 0 else f"{notif_ant} min"
        self.opt_notif = ctk.CTkOptionMenu(n_frm, values=["Desactivado", "1 min", "5 min", "10 min", "15 min"], command=self.cambiar_anticipacion)
        self.opt_notif.pack(side="right", padx=20)
        self.opt_notif.set(notif_str)
        ToolTip(self.opt_notif, "Establece el tiempo de antelación para recibir la notificación de Windows.")

        # 4. Sonido de Notificación
        s_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        s_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(s_frm, text="🎵 Sonido de Alerta:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        
        sound_sel = self.datos.get("settings", {}).get("notif_sonido", "Reminder")
        self.opt_sonido = ctk.CTkOptionMenu(s_frm, values=["Reminder", "Alarm", "SMS", "Mail", "Silencioso"], command=self.cambiar_sonido)
        self.opt_sonido.pack(side="right", padx=20)
        self.opt_sonido.set(sound_sel)
        ToolTip(self.opt_sonido, "Personaliza el tono de Windows que se reproduce al avisarte de la clase.")

        # 5. Auto-inicio con Windows
        a_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        a_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(a_frm, text="⚙️ Auto-inicio con Windows:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        self.sw_autostart = ctk.CTkSwitch(a_frm, text="Ejecutar al encender el PC", command=self.toggle_autostart, font=ctk.CTkFont(size=13))
        self.sw_autostart.pack(side="right", padx=20)
        if self._is_startup_enabled():
            self.sw_autostart.select()
        ToolTip(self.sw_autostart, "Hacer que Abre-Cursos Pro inicie automáticamente en segundo plano cuando Windows inicie.")

        # 6. Apariencia
        c_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        c_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(c_frm, text="🎨 Apariencia de Interfaz:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        def change_appearance(mode): ctk.set_appearance_mode(mode); self.refrescar_lista()
        theme_menu = ctk.CTkOptionMenu(c_frm, values=["System", "Dark", "Light"], command=change_appearance)
        theme_menu.pack(side="right", padx=20)
        theme_menu.set("System")
        ToolTip(theme_menu, "Alterna entre el tema del sistema, modo oscuro o modo claro.")

        # 7. Navegador para clases
        b_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        b_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(b_frm, text="🌐 Navegador para clases:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        browser_sel = self.datos.get("settings", {}).get("browser", "Predeterminado")
        self.opt_browser = ctk.CTkOptionMenu(b_frm, values=["Predeterminado", "Chrome", "Edge", "Firefox", "Brave"], command=self.cambiar_navegador)
        self.opt_browser.pack(side="right", padx=20)
        self.opt_browser.set(browser_sel)
        ToolTip(self.opt_browser, "Selecciona el navegador web en el que se abrirán los enlaces de tus clases.")

        # 8. Actualizaciones
        up_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        up_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(up_frm, text="🔄 Actualizaciones de Software:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        btn_update = ctk.CTkButton(up_frm, text="Buscar Actualización", fg_color="#7c3aed", hover_color="#6d28d9", font=ctk.CTkFont(size=12, weight="bold"), width=150, command=self.buscar_actualizacion_manual)
        btn_update.pack(side="right", padx=20)
        ToolTip(btn_update, "Busca nuevas versiones en el servidor/repositorio remoto e instala la actualización si está disponible.")

        # 9. Importar / Exportar
        ie_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        ie_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(ie_frm, text="📁 Copia de Seguridad:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        
        btn_exp = ctk.CTkButton(ie_frm, text="Exportar Horarios", fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"), width=130, command=self.exportar_cursos)
        btn_exp.pack(side="right", padx=20)
        ToolTip(btn_exp, "Exporta todos tus cursos y configuraciones a un archivo JSON externo.")
        
        btn_imp = ctk.CTkButton(ie_frm, text="Importar Horarios", fg_color="#3b82f6", hover_color="#2563eb", font=ctk.CTkFont(size=12, weight="bold"), width=130, command=self.importar_cursos)
        btn_imp.pack(side="right", padx=5)
        ToolTip(btn_imp, "Importa una base de datos de horarios JSON externa, reemplazando la actual.")

        # 10. Desinstalación
        u_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        u_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(u_frm, text="❌ Desinstalación completa:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        btn_un = ctk.CTkButton(u_frm, text="Desinstalar Programa", fg_color="#dc2626", hover_color="#b91c1c", command=self.desinstalar)
        btn_un.pack(side="right", padx=20)
        ToolTip(btn_un, "Elimina la aplicación, tus cursos guardados y los accesos directos de tu equipo.")

    def cambiar_sonido(self, val):
        with data_lock:
            if "settings" not in self.datos: self.datos["settings"] = {}
            self.datos["settings"]["notif_sonido"] = val
            guardar_datos(self.datos)
        self.agregar_log(f"Sonido de notificaciones actualizado a {val}.")

    def cambiar_navegador(self, val):
        with data_lock:
            if "settings" not in self.datos: self.datos["settings"] = {}
            self.datos["settings"]["browser"] = val
            guardar_datos(self.datos)
        self.agregar_log(f"Navegador de clases actualizado a {val}.")

    def buscar_actualizacion_manual(self):
        threading.Thread(target=check_for_updates, args=(False, self), daemon=True).start()

    def mostrar_ventana_actualizacion(self, latest_version, download_url, changelog):
        up_win = ctk.CTkToplevel(self.root)
        up_win.title("Actualización disponible")
        up_win.geometry("500x380")
        up_win.grab_set()
        up_win.after(200, lambda: up_win.focus_force())
        
        # Center window
        up_win.update_idletasks()
        width = up_win.winfo_width()
        height = up_win.winfo_height()
        x = (up_win.winfo_screenwidth() // 2) - (width // 2)
        y = (up_win.winfo_screenheight() // 2) - (height // 2)
        up_win.geometry(f'{width}x{height}+{x}+{y}')
        
        # UI Elements
        ctk.CTkLabel(up_win, text="🚀 ¡Nueva versión disponible!", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))
        
        info_text = f"Tu versión actual: v{VERSION}\nÚltima versión disponible: v{latest_version}"
        ctk.CTkLabel(up_win, text=info_text, font=ctk.CTkFont(size=12)).pack(pady=2)
        
        ctk.CTkLabel(up_win, text="Cambios en esta versión:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        
        txt_changelog = ctk.CTkTextbox(up_win, height=100)
        txt_changelog.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        txt_changelog.insert("1.0", changelog)
        txt_changelog.configure(state="disabled")
        
        # Progress Bar and Status Label (hidden initially)
        progress_frame = ctk.CTkFrame(up_win, fg_color="transparent")
        progress_bar = ctk.CTkProgressBar(progress_frame, width=350)
        progress_bar.set(0)
        lbl_status_download = ctk.CTkLabel(progress_frame, text="Descargando actualización: 0%", font=ctk.CTkFont(size=11, slant="italic"))
        
        btn_frame = ctk.CTkFrame(up_win, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 15))
        
        def iniciar_actualizacion():
            if not getattr(sys, 'frozen', False):
                messagebox.showinfo("Aviso", "Estás ejecutando desde el script de Python. Para actualizar de forma automática, debes usar el ejecutable compilado (.exe).")
                up_win.destroy()
                return
                
            btn_actualizar.configure(state="disabled")
            btn_omitir.configure(state="disabled")
            
            # Show progress UI
            btn_frame.pack_forget()
            progress_frame.pack(fill="x", pady=(5, 15))
            lbl_status_download.pack(pady=2)
            progress_bar.pack(pady=5)
            
            def run_download():
                try:
                    import tempfile
                    import subprocess
                    import urllib.request
                    
                    exe_actual = Path(sys.executable)
                    dest_dir = exe_actual.parent
                    zip_temp = Path(tempfile.gettempdir()) / "AbreCursos_update.zip"
                    
                    req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=30) as response:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        block_size = 1024 * 64
                        
                        with open(zip_temp, "wb") as out_file:
                            while True:
                                chunk = response.read(block_size)
                                if not chunk:
                                    break
                                out_file.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = downloaded / total_size
                                    up_win.after(0, lambda p=percent: progress_bar.set(p))
                                    up_win.after(0, lambda p=percent: lbl_status_download.configure(text=f"Descargando actualización: {int(p * 100)}%"))
                                    
                    up_win.after(0, lambda: lbl_status_download.configure(text="Extrayendo y reiniciando..."))
                    
                    bat_path = Path(tempfile.gettempdir()) / "update_abrecursos.bat"
                    script = f"""@echo off
ping 127.0.0.1 -n 3 > nul
:loop
del /f /q "{exe_actual}" 2>nul
if exist "{exe_actual}" (
    ping 127.0.0.1 -n 2 > nul
    goto loop
)
powershell -Command "Expand-Archive -Path '{zip_temp}' -DestinationPath '{dest_dir}' -Force"
del /f /q "{zip_temp}"
set _MEIPASS=
set _MEIPASS2=
start "" "{exe_actual}"
(goto) 2>nul & del "%~f0"
"""
                    bat_path.write_text(script, encoding="utf-8")
                    subprocess.Popen(str(bat_path), shell=True, creationflags=0x08000000)
                    os._exit(0)
                    
                except Exception as e:
                    up_win.after(0, lambda: messagebox.showerror("Error de actualización", f"No se pudo descargar la nueva versión. Verifica tu conexión a internet.\n\nError: {e}"))
                    up_win.after(0, lambda: progress_frame.pack_forget())
                    up_win.after(0, lambda: btn_frame.pack(fill="x", pady=(5, 15)))
                    up_win.after(0, lambda: btn_actualizar.configure(state="normal"))
                    up_win.after(0, lambda: btn_omitir.configure(state="normal"))
            
            threading.Thread(target=run_download, daemon=True).start()

        btn_omitir = ctk.CTkButton(btn_frame, text="Más tarde", fg_color="gray", hover_color="#555555", width=120, command=up_win.destroy)
        btn_omitir.pack(side="left", padx=(50, 10), expand=True)
        
        btn_actualizar = ctk.CTkButton(btn_frame, text="Actualizar ahora", fg_color="#7c3aed", hover_color="#6d28d9", width=120, command=iniciar_actualizacion)
        btn_actualizar.pack(side="right", padx=(10, 50), expand=True)

    def desinstalar(self):
        if not messagebox.askyesno("Confirmar Desinstalación", "Estás a punto de desinstalar el programa por completo.\nEsto borrará tus horarios y eliminará la aplicación de tu PC.\n\n¿Estás seguro de continuar?"):
            return
            
        import tempfile
        import subprocess
        appdata = Path(os.environ["APPDATA"]) / "AbreCursos"
        desktop = Path(os.environ["USERPROFILE"]) / "Desktop" / "Abre-Cursos Pro.lnk"
        startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Abre-Cursos.lnk"
        
        script = f"""@echo off
ping 127.0.0.1 -n 3 > nul
del /f /q "{desktop}"
del /f /q "{startup}"
rmdir /s /q "{appdata}"
(goto) 2>nul & del "%~f0"
"""
        bat_path = Path(tempfile.gettempdir()) / "uninstall_abrecursos.bat"
        bat_path.write_text(script, encoding="utf-8")
        
        subprocess.Popen(str(bat_path), shell=True, creationflags=0x08000000)
        os._exit(0)

    def toggle_vacaciones(self):
        estado = self.sw_vacaciones.get()
        with data_lock:
            if "settings" not in self.datos: self.datos["settings"] = {}
            self.datos["settings"]["vacaciones"] = bool(estado)
            guardar_datos(self.datos)
        if estado:
            self.lbl_vacaciones.pack(anchor="w")
            self.agregar_log("Modo Vacaciones ACTIVADO. No se abrirá ningún curso.")
        else:
            self.lbl_vacaciones.pack_forget()
            self.agregar_log("Modo Vacaciones DESACTIVADO. Los cursos se abrirán normalmente.")

    def toggle_vacaciones_tray(self):
        current = self.datos.get("settings", {}).get("vacaciones", False)
        new_state = not current
        with data_lock:
            if "settings" not in self.datos: self.datos["settings"] = {}
            self.datos["settings"]["vacaciones"] = new_state
            guardar_datos(self.datos)
        
        if new_state:
            self.sw_vacaciones.select()
            self.lbl_vacaciones.pack(anchor="w")
            self.agregar_log("Modo Vacaciones ACTIVADO (desde la bandeja).")
        else:
            self.sw_vacaciones.deselect()
            self.lbl_vacaciones.pack_forget()
            self.agregar_log("Modo Vacaciones DESACTIVADO (desde la bandeja).")

    def cambiar_tolerancia(self, val):
        with data_lock:
            if "settings" not in self.datos: self.datos["settings"] = {}
            self.datos["settings"]["tolerancia_min"] = int(val)
            guardar_datos(self.datos)
        self.lbl_nota.configure(text=f"Nota: Apertura automática con tolerancia de {val} min.")
        self.agregar_log(f"Tolerancia de retraso actualizada a {val} minutos.")

    def cambiar_anticipacion(self, val):
        minutos = 0 if val == "Desactivado" else int(val.split(" ")[0])
        with data_lock:
            if "settings" not in self.datos: self.datos["settings"] = {}
            self.datos["settings"]["notif_anticipacion"] = minutos
            guardar_datos(self.datos)
        self.agregar_log(f"Anticipación de notificaciones actualizada a {val}.")

    def _is_startup_enabled(self):
        startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Abre-Cursos.lnk"
        return startup.exists()

    def toggle_autostart(self):
        enable = self.sw_autostart.get()
        appdata = Path(os.environ["APPDATA"]) / "AbreCursos"
        exe_destino = appdata / "AbreCursos.exe"
        startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Abre-Cursos.lnk"
        
        if enable:
            if not exe_destino.exists() and getattr(sys, 'frozen', False):
                exe_destino = Path(sys.executable)
            
            ps_script = f'''
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{startup}")
            $Shortcut.TargetPath = "{exe_destino}"
            $Shortcut.WorkingDirectory = "{exe_destino.parent}"
            $Shortcut.Save()
            '''
            try:
                import subprocess
                subprocess.run(["powershell", "-Command", ps_script], creationflags=0x08000000)
                self.agregar_log("Auto-inicio con Windows ACTIVADO.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo configurar el auto-inicio: {e}")
                self.sw_autostart.deselect()
        else:
            try:
                if startup.exists():
                    os.remove(startup)
                self.agregar_log("Auto-inicio con Windows DESACTIVADO.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar de auto-inicio: {e}")
                self.sw_autostart.select()

    def exportar_cursos(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")], initialfile="cursos_backup.json")
        if path:
            try:
                with data_lock:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(self.datos, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("Éxito", "Cursos exportados correctamente.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar: {e}")

    def importar_cursos(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if not isinstance(data, dict) or "cursos" not in data:
                    if isinstance(data, list):
                        data = {"version": 2, "settings": {"vacaciones": False, "tolerancia_min": 30, "notif_anticipacion": 5, "notif_sonido": "Reminder"}, "cursos": data}
                    else:
                        raise ValueError("Formato JSON no válido.")
                
                if messagebox.askyesno("Confirmar", "Esto reemplazará todos tus horarios actuales. ¿Deseas continuar?"):
                    with data_lock:
                        self.datos = data
                        guardar_datos(self.datos)
                    self.refrescar_lista()
                    
                    vac = self.datos.get("settings", {}).get("vacaciones", False)
                    if vac: self.sw_vacaciones.select()
                    else: self.sw_vacaciones.deselect()
                    
                    tol = self.datos.get("settings", {}).get("tolerancia_min", 30)
                    self.opt_tolerancia.set(str(tol))
                    self.lbl_nota.configure(text=f"Nota: Apertura automática con tolerancia de {tol} min.")
                    
                    ant = self.datos.get("settings", {}).get("notif_anticipacion", 5)
                    self.opt_notif.set("Desactivado" if ant == 0 else f"{ant} min")
                    
                    sonido = self.datos.get("settings", {}).get("notif_sonido", "Reminder")
                    self.opt_sonido.set(sonido)
                    
                    browser = self.datos.get("settings", {}).get("browser", "Predeterminado")
                    self.opt_browser.set(browser)
                    
                    messagebox.showinfo("Éxito", "Cursos importados correctamente.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo importar: {e}")

    def refrescar_lista(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        with data_lock:
            cursos = list(self.datos.get("cursos", []))
            
        if not cursos:
            lbl = ctk.CTkLabel(self.scroll_frame, text="No tienes cursos registrados. ¡Agrega uno arriba!", font=ctk.CTkFont(size=13, slant="italic"), text_color="gray")
            lbl.pack(pady=40)
            return

        query = ""
        if hasattr(self, 'ent_search'):
            query = self.ent_search.get().lower().strip()

        filtered_cursos = []
        for c in cursos:
            if query and query not in c["nombre"].lower():
                continue
            filtered_cursos.append(c)

        if not filtered_cursos:
            lbl = ctk.CTkLabel(self.scroll_frame, text="No se encontraron cursos que coincidan con la búsqueda.", font=ctk.CTkFont(size=13, slant="italic"), text_color="gray")
            lbl.pack(pady=40)
            return

        for c in filtered_cursos:
            card = self._create_course_card(self.scroll_frame, c)
            card.pack(fill="x", padx=(10, 25), pady=5)

    def guardar_curso(self):
        nombre, url, dias = self.v_nombre.get().strip(), self.v_url.get().strip(), [i for i, v in enumerate(self.v_dias) if v.get()]
        if not nombre or not url or not dias: messagebox.showwarning("Faltan datos", "Completa nombre, URL y al menos un día."); return
        if not url.startswith("http") and not url.startswith("zoommtg") and not url.startswith("msteams"): 
            url = "https://" + url

        # Conflict check
        hora_str = self.v_hora.get()
        min_str = self.v_min.get()
        conflictos = []
        with data_lock:
            for c in self.datos.get("cursos", []):
                if self.editing_id and c["id"] == self.editing_id:
                    continue
                if c["hora"] == hora_str and c["minuto"] == min_str:
                    common_days = set(dias).intersection(c.get("dias", []))
                    if common_days:
                        conflictos.append(c["nombre"])
                        
        if conflictos:
            conf_names = ", ".join(conflictos)
            if not messagebox.askyesno("Conflicto de Horario", 
                                       f"Atención: Ya tienes programado el curso '{conf_names}' en ese mismo horario y día.\n\n"
                                       f"¿Deseas guardar de todas formas?"):
                return

        with data_lock:
            if self.editing_id:
                for c in self.datos.get("cursos", []):
                    if c["id"] == self.editing_id:
                        c.update(nombre=nombre, url=url, hora=self.v_hora.get(), minuto=self.v_min.get(), dias=dias)
                        break
                self.editing_id = None
                self.btn_guardar.configure(text="Agregar curso")
                self.btn_cancelar.pack_forget()
            else:
                import uuid
                self.datos["cursos"].append({"id": str(uuid.uuid4())[:8], "nombre": nombre, "url": url, "hora": self.v_hora.get(), "minuto": self.v_min.get(), "dias": dias, "activo": True})
            guardar_datos(self.datos)
            
        self.refrescar_lista()
        self.v_nombre.set(""); self.v_url.set(""); self.v_hora.set("08"); self.v_min.set("00")
        for v in self.v_dias: v.set(False)

    def cancelar_edicion(self):
        self.editing_id = None
        self.btn_guardar.configure(text="Agregar curso")
        self.btn_cancelar.pack_forget()
        self.v_nombre.set(""); self.v_url.set(""); self.v_hora.set("08"); self.v_min.set("00")
        for v in self.v_dias: v.set(False)

    def agregar_log(self, texto):
        # Write to physical file log
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(texto + "\n")
        except Exception as e:
            print(f"Error writing to log file: {e}")
            
        self.log_lines.append(texto)
        self.root.after(0, self._flush_log)

    def _flush_log(self):
        if not self.log_lines: return
        self.txt_log.configure(state="normal")
        for l in self.log_lines: self.txt_log.insert("end", l + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        self.log_lines.clear()
        self._cargar_estadisticas()

    def limpiar_log(self):
        if messagebox.askyesno("Confirmar", "¿Estás seguro de borrar todo el historial y reiniciar las estadísticas?"):
            if LOG_FILE.exists():
                try:
                    os.remove(LOG_FILE)
                except Exception as e:
                    print(f"Error removing log file: {e}")
            self.txt_log.configure(state="normal")
            self.txt_log.delete("1.0", "end")
            self.txt_log.configure(state="disabled")
            self._cargar_estadisticas()

    def ocultar(self): self.root.withdraw()
    def mostrar(self): self.root.deiconify(); self.root.lift()

    def _get_next_class_info(self):
        now = datetime.now()
        current_day_idx = (now.weekday() + 1) % 7
        current_time_min = now.hour * 60 + now.minute
        
        next_class = None
        min_diff_seconds = float('inf')
        
        with data_lock:
            cursos = [dict(c) for c in self.datos.get("cursos", []) if c.get("activo", True)]
            
        if not cursos:
            return "No hay cursos programados"
            
        for c in cursos:
            hora = int(c["hora"])
            minuto = int(c["minuto"])
            
            for day_offset in range(8):
                target_day = (current_day_idx + day_offset) % 7
                if target_day in c.get("dias", []):
                    target_date = now.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                    if day_offset > 0:
                        target_date += timedelta(days=day_offset)
                    elif day_offset == 0 and (hora * 60 + minuto) <= current_time_min:
                        target_date += timedelta(days=7)
                    
                    diff = (target_date - now).total_seconds()
                    if diff < min_diff_seconds:
                        min_diff_seconds = diff
                        next_class = (c["nombre"], target_date)
                    break
                    
        if next_class:
            c_nombre, t_date = next_class
            diff_sec = int(min_diff_seconds)
            hours = diff_sec // 3600
            minutes = (diff_sec % 3600) // 60
            
            if hours > 24:
                days = hours // 24
                h_remain = hours % 24
                return f"Próxima: {c_nombre} (en {days}d {h_remain}h)"
            elif hours > 0:
                return f"Próxima: {c_nombre} (en {hours}h {minutes}m)"
            else:
                return f"Próxima: {c_nombre} (en {minutes}m)"
        return "No hay cursos programados"

    def _tick(self):
        now = datetime.now()
        dia_idx = (now.weekday() + 1) % 7
        next_lbl = self._get_next_class_info()
        self.lbl_reloj.configure(text=f"{DIAS_FULL[dia_idx]} {now.strftime('%H:%M:%S')}")
        self.lbl_proxima.configure(text=next_lbl)
        self.root.after(1000, self._tick)

def get_menu_items(app):
    items = []
    items.append(pystray.MenuItem("Abrir ventana", lambda icon, item: app.root.after(0, app.mostrar), default=True))
    
    # Toggle Vacaciones
    vac_text = "🏖️ Desactivar Vacaciones" if app.datos.get("settings", {}).get("vacaciones", False) else "🏖️ Activar Vacaciones"
    items.append(pystray.MenuItem(vac_text, lambda icon, item: app.root.after(0, app.toggle_vacaciones_tray)))
    
    items.append(pystray.Menu.SEPARATOR)
    
    # Next class info
    next_lbl = app._get_next_class_info()
    items.append(pystray.MenuItem(next_lbl, lambda icon, item: None, enabled=False))
    
    items.append(pystray.Menu.SEPARATOR)
    
    # Today's courses list
    now = datetime.now()
    day_idx = (now.weekday() + 1) % 7
    with data_lock:
        cursos_hoy = [c for c in app.datos.get("cursos", []) if day_idx in c.get("dias", [])]
        
    if cursos_hoy:
        items.append(pystray.MenuItem("Clases de hoy:", lambda icon, item: None, enabled=False))
        for c in sorted(cursos_hoy, key=lambda x: (x["hora"], x["minuto"])):
            status = "⏰" if c.get("activo", True) else "⏸️"
            c_text = f"  {status} {c['hora']}:{c['minuto']} - {c['nombre']}"
            items.append(pystray.MenuItem(
                c_text, 
                lambda icon, item, url=c["url"], nom=c["nombre"]: app.root.after(0, lambda: app._abrir_manualmente(url, nom))
            ))
    else:
        items.append(pystray.MenuItem("No hay clases hoy", lambda icon, item: None, enabled=False))
        
    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem("Salir", lambda icon, item: on_quit(icon, app)))
    return items

def on_quit(icon, app):
    icon.stop()
    app.root.after(0, app.root.destroy)

def run_tray(app):
    try:
        import pystray
        from PIL import Image, ImageDraw
        
        img = None
        if ICON_FILE.exists():
            try:
                img = Image.open(str(ICON_FILE))
            except Exception:
                img = None
                
        if img is None:
            img = Image.new("RGB", (64, 64), color="#1f538d")
            d = ImageDraw.Draw(img)
            d.rectangle([8,8,56,56], fill="#14375e")
            d.text((16, 20), "AC", fill="white")
            
        icon = pystray.Icon("AbreCursos", img, "Abre-Cursos", menu=pystray.Menu(lambda: get_menu_items(app)))
        icon.run()
    except ImportError:
        pass
    except Exception as e:
        try:
            app.agregar_log(f"Error en bandeja del sistema: {e}")
        except:
            pass

if __name__ == "__main__":
    root = ctk.CTk()
    app = AbreCursosApp(root)
    threading.Thread(target=run_tray, args=(app,), daemon=True).start()
    root.mainloop()
