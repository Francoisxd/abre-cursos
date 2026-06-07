import os
import sys
import shutil
import subprocess
from pathlib import Path
import customtkinter as ctk
import time
import threading

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Instalador Abre-Cursos Pro")
        self.geometry("500x350")
        self.resizable(False, False)

        self.lbl_title = ctk.CTkLabel(self, text="Instalación de Abre-Cursos Pro", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.pack(pady=(30, 10))

        self.lbl_desc = ctk.CTkLabel(self, text="Este asistente instalará Abre-Cursos en tu sistema.\nSe creará un acceso directo en tu escritorio\ny se migrarán tus cursos guardados.", justify="center")
        self.lbl_desc.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self, width=350)
        self.progress.pack(pady=20)
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(self, text="Listo para instalar.", text_color="gray")
        self.lbl_status.pack(pady=5)

        self.btn_install = ctk.CTkButton(self, text="Instalar Ahora", command=self.start_install)
        self.btn_install.pack(pady=20)

    def start_install(self):
        self.btn_install.configure(state="disabled")
        self.progress.set(0.1)
        threading.Thread(target=self.install_process, daemon=True).start()

    def update_status(self, text, prog):
        self.lbl_status.configure(text=text)
        self.progress.set(prog)

    def install_process(self):
        try:
            # Rutas
            appdata = Path(os.environ["APPDATA"]) / "AbreCursos"
            desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
            start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            startup = start_menu / "Startup"
            
            # 1. Crear directorio
            self.update_status("Creando directorios...", 0.3)
            time.sleep(0.5)
            appdata.mkdir(exist_ok=True)
            
            # 2. Copiar EXE
            self.update_status("Copiando programa principal...", 0.5)
            
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys._MEIPASS)
                origen_json_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent
                origen_json_dir = base_dir
                
            exe_origen = base_dir / "AbreCursos.exe"
            exe_destino = appdata / "AbreCursos.exe"
            
            if exe_origen.exists():
                shutil.copy2(exe_origen, exe_destino)
            else:
                self.update_status("Error: No se encontró AbreCursos.exe", 0)
                return

            # 3. Migrar cursos.json
            self.update_status("Migrando tus cursos guardados...", 0.7)
            time.sleep(0.5)
            json_origen = origen_json_dir / "cursos.json"
            if json_origen.exists():
                shutil.copy2(json_origen, appdata / "cursos.json")
                
            # 4. Crear accesos directos reales (.lnk)
            self.update_status("Creando accesos directos...", 0.9)
            time.sleep(0.5)
            
            ps_script = f'''
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{desktop}\\Abre-Cursos Pro.lnk")
            $Shortcut.TargetPath = "{exe_destino}"
            $Shortcut.WorkingDirectory = "{appdata}"
            $Shortcut.Save()
            
            $Shortcut2 = $WshShell.CreateShortcut("{startup}\\Abre-Cursos.lnk")
            $Shortcut2.TargetPath = "{exe_destino}"
            $Shortcut2.WorkingDirectory = "{appdata}"
            $Shortcut2.Save()
            '''
            
            subprocess.run(["powershell", "-Command", ps_script], creationflags=0x08000000)
            
            # Finish
            self.update_status("¡Instalación Completada!", 1.0)
            self.btn_install.configure(text="Finalizar y Abrir", state="normal", command=lambda: self.finish(exe_destino))
            
        except Exception as e:
            self.update_status(f"Error: {e}", 0)
            self.btn_install.configure(state="normal", text="Reintentar")

    def finish(self, exe_path):
        subprocess.Popen([str(exe_path)], creationflags=0x00000008)
        self.destroy()

if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
