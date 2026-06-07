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

# Versión del programa y repositorio
VERSION = "2.1.5"
GITHUB_USER = "Francoisxd"
GITHUB_REPO = "abre-cursos"

# Rutas
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
    
DATA_FILE = BASE_DIR / "cursos.json"
ICON_FILE = BASE_DIR / "icono.ico"
LOG_FILE  = BASE_DIR / "historial.log"

DIAS      = ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"]
DIAS_FULL = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

data_lock = threading.Lock()

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
                        toast.set_audio(audio.Alarm, loop=False)
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
                webbrowser.open(final_url)
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
        hdr = ctk.CTkFrame(self.root, height=85, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        
        lbl_title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        lbl_title_frame.pack(side="left", padx=20, pady=10)
        
        ctk.CTkLabel(lbl_title_frame, text=f"Abre-Cursos Pro (v{VERSION})", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        self.lbl_vacaciones = ctk.CTkLabel(lbl_title_frame, text="🏖️ MODO VACACIONES ACTIVO", text_color="#d97706", font=ctk.CTkFont(weight="bold", size=12))
        if self.datos.get("settings", {}).get("vacaciones", False):
            self.lbl_vacaciones.pack(anchor="w")
            
        self.lbl_reloj = ctk.CTkLabel(hdr, text="", font=ctk.CTkFont(size=13, weight="bold"), justify="right")
        self.lbl_reloj.pack(side="right", padx=20)

        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        self._tab_horario(self.tabview.add("Horario"))
        self._tab_historial(self.tabview.add("Historial"))
        self._tab_ajustes(self.tabview.add("Ajustes"))

    def _tab_horario(self, parent):
        # Formulary
        frm = ctk.CTkFrame(parent)
        frm.pack(fill="x", padx=10, pady=(10, 10))

        self.v_nombre = tk.StringVar()
        self.v_url    = tk.StringVar()
        self.v_hora   = tk.StringVar(value="08")
        self.v_min    = tk.StringVar(value="00")
        self.v_dias   = [tk.BooleanVar() for _ in range(7)]

        r0 = ctk.CTkFrame(frm, fg_color="transparent")
        r0.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(r0, text="Nombre:").pack(side="left", padx=(0,5))
        ctk.CTkEntry(r0, textvariable=self.v_nombre, width=200, placeholder_text="Ej: Programación").pack(side="left", padx=(0,20))
        ctk.CTkLabel(r0, text="Link (URL):").pack(side="left", padx=(0,5))
        ctk.CTkEntry(r0, textvariable=self.v_url, width=300, placeholder_text="https://zoom.us/j/... o teams link").pack(side="left", fill="x", expand=True)

        r1 = ctk.CTkFrame(frm, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(r1, text="Hora:").pack(side="left", padx=(0,5))
        ctk.CTkComboBox(r1, variable=self.v_hora, values=[str(h).zfill(2) for h in range(24)], width=70).pack(side="left")
        ctk.CTkLabel(r1, text=":", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkComboBox(r1, variable=self.v_min, values=[str(m).zfill(2) for m in range(0, 60, 5)], width=70).pack(side="left", padx=(0,20))
        ctk.CTkLabel(r1, text="Días:").pack(side="left", padx=(0,10))
        for i, d in enumerate(DIAS): ctk.CTkCheckBox(r1, text=d, variable=self.v_dias[i], width=60).pack(side="left", padx=2)

        r2 = ctk.CTkFrame(frm, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=(5, 10))
        
        tol = self.datos.get("settings", {}).get("tolerancia_min", 30)
        self.lbl_nota = ctk.CTkLabel(r2, text=f"Nota: Apertura automática con tolerancia de {tol} min.", text_color="gray")
        self.lbl_nota.pack(side="left")
        
        self.btn_guardar = ctk.CTkButton(r2, text="Agregar curso", command=self.guardar_curso, fg_color="#059669", hover_color="#047857")
        self.btn_guardar.pack(side="right")
        self.btn_cancelar = ctk.CTkButton(r2, text="Cancelar", command=self.cancelar_edicion, fg_color="gray", hover_color="#555555")

        # Container for Scrollable Card Frame
        lf = ctk.CTkFrame(parent)
        lf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.scroll_frame = ctk.CTkScrollableFrame(lf, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.refrescar_lista()

    def _create_course_card(self, parent, c):
        is_active = c.get("activo", True)
        
        card = ctk.CTkFrame(parent, fg_color=("#f5f5f5", "#262626"), border_color=("#e5e5e5", "#404040"), border_width=1, corner_radius=10)
        
        # Details container
        details_frame = ctk.CTkFrame(card, fg_color="transparent")
        details_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        top_line = ctk.CTkFrame(details_frame, fg_color="transparent")
        top_line.pack(fill="x", anchor="w")
        
        lbl_nombre = ctk.CTkLabel(top_line, text=c["nombre"], font=ctk.CTkFont(size=14, weight="bold"), text_color=("#171717", "#ffffff") if is_active else "gray", anchor="w")
        lbl_nombre.pack(side="left")
        
        lbl_hora = ctk.CTkLabel(top_line, text=f" ⏰ {c['hora']}:{c['minuto']} ", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#3b82f6" if is_active else "gray", text_color="white", corner_radius=6)
        lbl_hora.pack(side="left", padx=10)
        
        dias_str = ", ".join(DIAS[d] for d in sorted(c.get("dias", [])))
        lbl_dias = ctk.CTkLabel(details_frame, text=f"Días: {dias_str}", font=ctk.CTkFont(size=11), text_color="gray", anchor="w")
        lbl_dias.pack(fill="x", pady=(2, 0))
        
        url_text = c["url"]
        if len(url_text) > 50:
            url_text = url_text[:47] + "..."
            
        is_zoom_or_teams = "zoom" in c["url"].lower() or "teams" in c["url"].lower()
        lbl_url = ctk.CTkLabel(details_frame, text=f"🔗 {url_text}", font=ctk.CTkFont(size=11), text_color="#10b981" if is_zoom_or_teams else "gray", anchor="w", cursor="hand2")
        lbl_url.pack(fill="x", pady=(2, 0))
        lbl_url.bind("<Button-1>", lambda e, u=c["url"]: webbrowser.open(optimizar_url(u)))
        ToolTip(lbl_url, "Hacer clic para abrir este enlace directamente en tu navegador.")

        # Actions
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.pack(side="right", fill="y", padx=15)
        
        sw_var = tk.BooleanVar(value=is_active)
        sw = ctk.CTkSwitch(actions_frame, text="", variable=sw_var, width=40, command=lambda c_id=c["id"]: self._toggle_activo_by_id(c_id))
        sw.pack(side="left", padx=10)
        ToolTip(sw, "Activar o desactivar temporalmente este curso del planificador.")
        
        btn_run = ctk.CTkButton(actions_frame, text="Abrir", font=ctk.CTkFont(size=12, weight="bold"), width=60, height=30, fg_color="#059669", hover_color="#047857", command=lambda url=c["url"], nom=c["nombre"]: self._abrir_manualmente(url, nom))
        btn_run.pack(side="left", padx=3)
        ToolTip(btn_run, "Abre este curso de inmediato sin esperar al horario.")
        
        btn_edit = ctk.CTkButton(actions_frame, text="Editar", font=ctk.CTkFont(size=12, weight="bold"), width=60, height=30, fg_color="#d97706", hover_color="#b45309", command=lambda c_id=c["id"]: self._editar_by_id(c_id))
        btn_edit.pack(side="left", padx=3)
        ToolTip(btn_edit, "Carga los datos de este curso arriba para modificarlos.")
        
        btn_del = ctk.CTkButton(actions_frame, text="Borrar", font=ctk.CTkFont(size=12, weight="bold"), width=60, height=30, fg_color="#dc2626", hover_color="#b91c1c", command=lambda c_id=c["id"], nom=c["nombre"]: self._eliminar_by_id(c_id, nom))
        btn_del.pack(side="left", padx=3)
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
        webbrowser.open(final_url)
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

        # 7. Actualizaciones
        up_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        up_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(up_frm, text="🔄 Actualizaciones de Software:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        btn_update = ctk.CTkButton(up_frm, text="Buscar Actualización", fg_color="#7c3aed", hover_color="#6d28d9", font=ctk.CTkFont(size=12, weight="bold"), width=150, command=self.buscar_actualizacion_manual)
        btn_update.pack(side="right", padx=20)
        ToolTip(btn_update, "Busca nuevas versiones en el servidor/repositorio remoto e instala la actualización si está disponible.")

        # 8. Importar / Exportar
        ie_frm = ctk.CTkFrame(adj_scroll, fg_color=row_colors, corner_radius=8)
        ie_frm.pack(fill="x", pady=6, ipady=4)
        ctk.CTkLabel(ie_frm, text="📁 Copia de Seguridad:", font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=20, pady=10)
        
        btn_exp = ctk.CTkButton(ie_frm, text="Exportar Horarios", fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"), width=130, command=self.exportar_cursos)
        btn_exp.pack(side="right", padx=20)
        ToolTip(btn_exp, "Exporta todos tus cursos y configuraciones a un archivo JSON externo.")
        
        btn_imp = ctk.CTkButton(ie_frm, text="Importar Horarios", fg_color="#3b82f6", hover_color="#2563eb", font=ctk.CTkFont(size=12, weight="bold"), width=130, command=self.importar_cursos)
        btn_imp.pack(side="right", padx=5)
        ToolTip(btn_imp, "Importa una base de datos de horarios JSON externa, reemplazando la actual.")

        # 9. Desinstalación
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

        for c in cursos:
            card = self._create_course_card(self.scroll_frame, c)
            card.pack(fill="x", padx=10, pady=5)

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
        self.lbl_reloj.configure(text=f"{now.strftime('%H:%M:%S')}  {DIAS_FULL[dia_idx]}\n{next_lbl}")
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
    except ImportError: pass

if __name__ == "__main__":
    root = ctk.CTk()
    app = AbreCursosApp(root)
    threading.Thread(target=run_tray, args=(app,), daemon=True).start()
    root.mainloop()
