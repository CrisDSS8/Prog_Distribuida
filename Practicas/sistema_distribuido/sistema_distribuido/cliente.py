import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import socket
import json
import uuid
import time
import os
import threading
from protocolo import crear_paquete, desempaquetar, BUFFER_SIZE

# ★ cargar la clave Fernet generada por el servidor local
try:
    from componentes import encriptador as _enc
except ImportError:
    try:
        import encriptador as _enc
    except ImportError:
        _enc = None

# ★ importar comunicacion para usar recibir_fragmentado y enviar_fragmentado
try:
    from componentes import comunicacion as _com
except ImportError:
    try:
        import comunicacion as _com
    except ImportError:
        _com = None

SERVER_IPS  = ["172.26.161.173", "172.26.160.188", "172.26.166.23", "172.26.166.207"]
SERVER_PORT = 12000
CACHE_DIR   = "cache_local"


def obtener_mi_ip() -> str:
    """Obtiene la IP real de red de esta maquina."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


MI_IP = obtener_mi_ip()

if _enc is not None:
    _enc.cargar_para_cliente()


def log_cliente(mensaje: str, trace_id: str = "SYSTEM"):
    ts   = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{trace_id}] {mensaje}\n"
    with open("cliente.log", "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
    print(line.strip())


def enviar_y_recibir(paquete: bytes, ip: str, timeout: float = 5.0):
    """
    Envia un paquete UDP y espera la respuesta.
    ★ Usa recibir_fragmentado para soportar respuestas grandes.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(paquete, (ip, SERVER_PORT))
        if _com is not None:
            return _com.recibir_fragmentado(s, timeout=timeout)
        # Fallback si comunicacion no esta disponible
        data, _ = s.recvfrom(BUFFER_SIZE)
        return desempaquetar(data)
    except socket.timeout:
        return None
    finally:
        s.close()


def enviar_fragmentado_cliente(ip: str, flags: str,
                                data: str, trace: str) -> None:
    """
    Envia data al servidor fragmentando si es necesario.
    ★ Usado para SYNC_BACK y compartir archivos grandes.
    """
    if _com is not None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            _com.enviar_fragmentado(s, (ip, SERVER_PORT), flags, data, trace)
        finally:
            s.close()
    else:
        # Fallback: envio directo (puede fallar con archivos grandes)
        pkt = crear_paquete(0, 0, flags, data, trace)
        s   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pkt, (ip, SERVER_PORT))
        s.close()


def notificar_stale(ip_servidor: str, nombre: str, trace: str):
    pkt = crear_paquete(0, 0, "STALE_RECORD", nombre, trace)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pkt, (ip_servidor, SERVER_PORT))
        s.close()
    except Exception:
        pass


def enviar_unlock(ip_servidor: str, nombre: str, trace: str = "UNLOCK"):
    """
    Notifica al servidor que ya no usamos el archivo.
    Usa MI_IP para que coincida con el bloqueo registrado en directorio.bloquear().
    """
    try:
        payload = json.dumps({"nombre": nombre, "ip_usuario": MI_IP})
        pkt     = crear_paquete(0, 0, "FILE_UNLOCK", payload, trace)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pkt, (ip_servidor, SERVER_PORT))
        s.close()
        log_cliente(f"FILE_UNLOCK enviado a {ip_servidor}: {nombre} (ip={MI_IP})", trace)
    except Exception as e:
        log_cliente(f"FILE_UNLOCK error: {e}", trace)


def _ruta_cache(nombre: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, nombre)


def guardar_copia_local(nombre: str, contenido: str) -> None:
    with open(_ruta_cache(nombre), "w", encoding="utf-8") as f:
        f.write(contenido)
    log_cliente(f"CACHE: copia local guardada -> {_ruta_cache(nombre)}")


def eliminar_copia_local(nombre: str) -> None:
    if not nombre:
        return
    ruta = _ruta_cache(nombre)
    if os.path.exists(ruta):
        os.remove(ruta)
        log_cliente(f"CACHE: copia local eliminada -> {ruta}")


def limpiar_toda_la_cache() -> None:
    if not os.path.isdir(CACHE_DIR):
        return
    for archivo in os.listdir(CACHE_DIR):
        try:
            os.remove(os.path.join(CACHE_DIR, archivo))
        except Exception:
            pass


class AppDistribuida:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sistema Distribuido FCC-BUAP")
        self.root.geometry("960x700")
        self.root.resizable(True, True)

        self.archivo_actual    = None
        self.contenido_orig    = ""
        self.server_actual     = SERVER_IPS[0]
        self.archivo_es_propio = False
        self.log_auto_refresh  = True
        self.cache_local: dict = {}

        if _enc is not None:
            estado = "Fernet/AES activo" if _enc.esta_activo() else "SIN CIFRADO (clave.key no encontrada)"
            log_cliente(f"Estado de cifrado del cliente: {estado}")

        self._build_ui()
        threading.Thread(target=self._hilo_refresh_logs, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar_app)

    def _build_ui(self):
        tabs = ttk.Notebook(self.root)
        self.tab_editor = ttk.Frame(tabs)
        self.tab_logs   = ttk.Frame(tabs)
        tabs.add(self.tab_editor, text="  Editor de Archivos  ")
        tabs.add(self.tab_logs,   text="  Rastreador de Trazas  ")
        tabs.pack(expand=True, fill="both")
        self._build_editor()
        self._build_logs()

    def _build_editor(self):
        top = tk.Frame(self.tab_editor, bg="#2c3e50", pady=6)
        top.pack(fill="x")
        tk.Label(top, text="Directorio Distribuido", font=("Arial", 13, "bold"),
                 bg="#2c3e50", fg="white").pack(side=tk.LEFT, padx=12)
        self.lbl_servidores = tk.Label(top, text="Servidores: verificando...",
                                        bg="#2c3e50", fg="#f39c12", font=("Arial", 9))
        self.lbl_servidores.pack(side=tk.LEFT, padx=16)

        cifrado_ok  = _enc is not None and _enc.esta_activo()
        cifrado_txt = "🔐 Cifrado activo" if cifrado_ok else "⚠ Sin cifrado"
        cifrado_col = "#2ecc71" if cifrado_ok else "#e74c3c"
        tk.Label(top, text=cifrado_txt, bg="#2c3e50", fg=cifrado_col,
                 font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=8)

        tk.Button(top, text="Actualizar Lista", command=self._actualizar_lista,
                  bg="#3498db", fg="white", relief="flat", padx=8).pack(side=tk.RIGHT, padx=10)
        tk.Button(top, text="Compartir Archivo", command=self._compartir_archivo,
                  bg="#9b59b6", fg="white", relief="flat", padx=8).pack(side=tk.RIGHT, padx=4)

        frame_tabla = tk.Frame(self.tab_editor)
        frame_tabla.pack(fill="x", padx=10, pady=(6, 2))
        cols = ("Nombre", "Dueno (IP)", "Tamano (B)", "Ultima modificacion", "TTL", "En uso")
        self.tree = ttk.Treeview(frame_tabla, columns=cols, show="headings",
                                  height=7, selectmode="browse")
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column("Nombre",             width=200)
        self.tree.column("Dueno (IP)",          width=120)
        self.tree.column("Tamano (B)",          width=85,  anchor="e")
        self.tree.column("Ultima modificacion", width=155)
        self.tree.column("TTL",                 width=45,  anchor="center")
        self.tree.column("En uso",              width=55,  anchor="center")
        self.tree.tag_configure("bloqueado", foreground="#e74c3c")
        self.tree.tag_configure("propio",    foreground="#2ecc71")

        sb = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill="x", expand=True)
        sb.pack(side=tk.RIGHT, fill="y")

        frame_acciones = tk.Frame(self.tab_editor, pady=4)
        frame_acciones.pack(fill="x", padx=10)
        tk.Button(frame_acciones, text="Abrir Seleccionado", command=self._abrir_desde_boton,
                  bg="#e67e22", fg="white", relief="flat", padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(frame_acciones, text="Eliminar Archivo", command=self._eliminar_archivo,
                  bg="#c0392b", fg="white", relief="flat", padx=8).pack(side=tk.LEFT, padx=4)
        tk.Label(frame_acciones, text=f"Tu IP: {MI_IP}",
                 fg="#7f8c8d", font=("Arial", 9)).pack(side=tk.RIGHT, padx=8)

        self.frame_bar = tk.Frame(self.tab_editor, pady=4)
        self.frame_bar.pack(fill="x", padx=10)
        tk.Label(self.frame_bar, text="Archivo:").pack(side=tk.LEFT)
        self.lbl_archivo = tk.Label(self.frame_bar, text="(ninguno)", fg="#7f8c8d",
                                     font=("Arial", 10, "italic"))
        self.lbl_archivo.pack(side=tk.LEFT, padx=6)
        tk.Button(self.frame_bar, text="Guardar Cambios", command=self._guardar_archivo,
                  bg="#27ae60", fg="white", relief="flat", padx=8).pack(side=tk.RIGHT, padx=4)
        tk.Button(self.frame_bar, text="Cerrar Archivo", command=self._cerrar_archivo,
                  bg="#7f8c8d", fg="white", relief="flat", padx=8).pack(side=tk.RIGHT, padx=4)

        self.txt_editor = scrolledtext.ScrolledText(
            self.tab_editor, height=15, font=("Courier New", 11),
            bg="#1e1e1e", fg="#dcdcdc", insertbackground="white"
        )

    def _build_logs(self):
        top = tk.Frame(self.tab_logs, bg="#2c3e50", pady=6)
        top.pack(fill="x")
        tk.Label(top, text="Trace ID:", bg="#2c3e50", fg="white").pack(side=tk.LEFT, padx=10)
        self.ent_trace = tk.Entry(top, width=18, font=("Courier New", 11))
        self.ent_trace.pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Rastrear Operacion", command=self._rastrear_log,
                  bg="#e74c3c", fg="white", relief="flat", padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Obtener Logs Remotos", command=self._obtener_logs_remotos,
                  bg="#16a085", fg="white", relief="flat", padx=8).pack(side=tk.LEFT, padx=4)
        self.var_autorefresh = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="Auto-refresh", variable=self.var_autorefresh,
                       bg="#2c3e50", fg="white", selectcolor="#2c3e50",
                       command=self._toggle_autorefresh).pack(side=tk.LEFT, padx=6)
        tk.Button(top, text="Limpiar Vista", command=self._limpiar_logs,
                  bg="#7f8c8d", fg="white", relief="flat", padx=8).pack(side=tk.RIGHT, padx=10)
        self.txt_logs = scrolledtext.ScrolledText(
            self.tab_logs, font=("Courier New", 10),
            bg="#1a1a2e", fg="#00ff88", insertbackground="white"
        )
        self.txt_logs.pack(padx=10, pady=(6, 10), fill=tk.BOTH, expand=True)
        self.txt_logs.tag_config("cliente",  foreground="#00bfff")
        self.txt_logs.tag_config("servidor", foreground="#00ff88")
        self.txt_logs.tag_config("remoto",   foreground="#ff9f43")
        self.txt_logs.tag_config("match",    foreground="#ffff00",
                                              font=("Courier New", 10, "bold"))

    # ─────────────────────────────────────────
    #  LOGICA: EDITOR DE ARCHIVOS
    # ─────────────────────────────────────────

    def _actualizar_lista(self):
        trace = str(uuid.uuid4())[:8]
        todos_archivos = {}
        servidores_ok  = []
        servidores_err = []

        for ip in SERVER_IPS:
            pkt  = crear_paquete(0, 0, "REQ_LIST", "", trace)
            resp = enviar_y_recibir(pkt, ip)
            if not resp or resp.get("flags") != "RES_LIST":
                servidores_err.append(ip)
                continue
            servidores_ok.append(ip)
            archivos = json.loads(resp["data"])
            for a in archivos:
                nombre = a["nombre"]
                if nombre not in todos_archivos or a.get("ttl", 0) == 0:
                    todos_archivos[nombre] = a

        estado = f"Servidores OK: {len(servidores_ok)}/{len(SERVER_IPS)}"
        if servidores_err:
            estado += f"  |  Sin resp: {', '.join(servidores_err)}"
        color = "#2ecc71" if not servidores_err else "#e67e22"
        self.lbl_servidores.config(text=estado, fg=color)

        for nombre, info in todos_archivos.items():
            self.cache_local[nombre] = info

        for row in self.tree.get_children():
            self.tree.delete(row)

        for a in todos_archivos.values():
            mtime_fmt  = time.strftime("%Y-%m-%d %H:%M:%S",
                                        time.localtime(a.get("mtime", 0)))
            en_uso     = "🔒" if a.get("en_uso") else ""
            es_propio  = a["dueno"] == MI_IP

            if a.get("en_uso"):
                tag = ("bloqueado",)
            elif es_propio:
                tag = ("propio",)
            else:
                tag = ()

            self.tree.insert("", tk.END, tags=tag, values=(
                a["nombre"], a["dueno"], a["size"], mtime_fmt,
                a.get("ttl", 0), en_uso
            ))

        log_cliente(f"Lista actualizada: {len(todos_archivos)} archivos", trace)

    def _abrir_desde_boton(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecciona un archivo de la lista primero.")
            return
        nombre = self.tree.item(sel[0])["values"][0]
        if self.archivo_actual and self.archivo_actual != nombre:
            self._cerrar_archivo(silencioso=True)
        self._abrir_archivo(nombre)

    def _eliminar_archivo(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecciona un archivo de la lista primero.")
            return

        valores  = self.tree.item(sel[0])["values"]
        nombre   = valores[0]
        ip_dueno = valores[1]

        if ip_dueno != MI_IP:
            messagebox.showerror("Acceso denegado",
                                  f"'{nombre}' pertenece a {ip_dueno}.\n"
                                  f"Solo puedes eliminar tus propios archivos.")
            return

        if not messagebox.askyesno("Confirmar eliminacion",
                                    f"¿Eliminar '{nombre}'?\n\nEsta accion no se puede deshacer."):
            return

        trace = str(uuid.uuid4())[:8]
        pkt   = crear_paquete(0, 0, "REQ_DELETE", nombre, trace)
        resp  = enviar_y_recibir(pkt, ip_dueno, timeout=5.0)

        if not resp:
            messagebox.showerror("Error", f"Sin respuesta del servidor {ip_dueno}.")
            return

        if resp.get("flags") == "ACK":
            messagebox.showinfo("Eliminado", f"'{nombre}' eliminado correctamente.")
            log_cliente(f"REQ_DELETE OK: {nombre}", trace)
            if self.archivo_actual == nombre:
                self._cerrar_archivo(silencioso=True)
            self.cache_local.pop(nombre, None)
            self.root.after(300, self._actualizar_lista)

        elif resp.get("flags") == "NACK":
            razon = resp.get("data", "Sin detalle")
            messagebox.showerror("No se puede eliminar", f"El servidor respondio:\n{razon}")
            log_cliente(f"REQ_DELETE NACK: {nombre} — {razon}", trace)

    def _cerrar_archivo(self, silencioso: bool = False):
        if not self.archivo_actual:
            return

        nombre   = self.archivo_actual
        servidor = self.server_actual

        if not self.archivo_es_propio:
            enviar_unlock(servidor, nombre)

        eliminar_copia_local(nombre)
        self.archivo_actual    = None
        self.contenido_orig    = ""
        self.archivo_es_propio = False
        self.txt_editor.delete(1.0, tk.END)
        self.txt_editor.pack_forget()
        self.lbl_archivo.config(text="(ninguno)", fg="#7f8c8d")

        if not silencioso:
            log_cliente(f"Editor cerrado: {nombre}")

    def _abrir_archivo(self, nombre: str):
        trace = str(uuid.uuid4())[:8]
        log_cliente(f"REQ_USE iniciado: {nombre}", trace)

        servidores_intentados = list(SERVER_IPS)
        intentados_set        = set()
        i = 0
        while i < len(servidores_intentados):
            ip = servidores_intentados[i]
            i += 1
            if ip in intentados_set:
                continue
            intentados_set.add(ip)

            pkt  = crear_paquete(0, 0, "REQ_USE", nombre, trace)
            # ★ timeout ampliado a 15 s para dar tiempo a recibir todos los fragmentos
            resp = enviar_y_recibir(pkt, ip, timeout=15.0)
            if not resp:
                log_cliente(f"Timeout en {ip}", trace)
                continue

            flags = resp.get("flags")

            if flags == "RES_AUTH":
                datos      = json.loads(resp["data"])
                contenido  = datos.get("contenido", "")
                attrs      = datos.get("attrs", {})
                es_propio  = (ip == MI_IP)

                self.cache_local[nombre] = {"nombre": nombre, "dueno": ip,
                    "size": attrs.get("size", 0), "mtime": attrs.get("mtime", 0),
                    "ttl": attrs.get("ttl", 0)}

                if not es_propio:
                    guardar_copia_local(nombre, contenido)
                else:
                    log_cliente(f"Archivo propio, sin copia local: {nombre}", trace)

                self.txt_editor.pack(padx=10, pady=(4, 10), fill=tk.BOTH, expand=True)
                self.txt_editor.delete(1.0, tk.END)
                self.txt_editor.insert(tk.END, contenido)
                self.archivo_actual    = nombre
                self.contenido_orig    = contenido
                self.server_actual     = ip
                self.archivo_es_propio = es_propio

                color = "#2ecc71" if es_propio else "#f39c12"
                sufijo = "  [PROPIO]" if es_propio else f"  (via {ip})"
                self.lbl_archivo.config(
                    text=f"{nombre}  [trace={trace}]{sufijo}", fg=color)
                log_cliente(f"Archivo abierto desde {ip}: {nombre} "
                            f"({'propio' if es_propio else 'ajeno'})", trace)
                return

            elif flags == "RES_NON_AUTH":
                ip_dueno = resp.get("data", "").strip()
                if not ip_dueno or ip_dueno in intentados_set:
                    continue
                resp2 = enviar_y_recibir(
                    crear_paquete(0, 0, "REQ_USE", nombre, trace),
                    ip_dueno, timeout=15.0)   # ★ timeout ampliado
                if resp2 and resp2.get("flags") == "RES_AUTH":
                    datos      = json.loads(resp2["data"])
                    contenido  = datos.get("contenido", "")
                    attrs      = datos.get("attrs", {})
                    es_propio  = (ip_dueno == MI_IP)

                    self.cache_local[nombre] = {"nombre": nombre, "dueno": ip_dueno,
                        "size": attrs.get("size", 0), "mtime": attrs.get("mtime", 0),
                        "ttl": attrs.get("ttl", 0)}

                    if not es_propio:
                        guardar_copia_local(nombre, contenido)
                    else:
                        log_cliente(f"Archivo propio, sin copia local: {nombre}", trace)

                    self.txt_editor.pack(padx=10, pady=(4, 10), fill=tk.BOTH, expand=True)
                    self.txt_editor.delete(1.0, tk.END)
                    self.txt_editor.insert(tk.END, contenido)
                    self.archivo_actual    = nombre
                    self.contenido_orig    = contenido
                    self.server_actual     = ip_dueno
                    self.archivo_es_propio = es_propio

                    color = "#2ecc71" if es_propio else "#f39c12"
                    sufijo = "  [PROPIO]" if es_propio else f"  (via dueno {ip_dueno})"
                    self.lbl_archivo.config(
                        text=f"{nombre}  [trace={trace}]{sufijo}", fg=color)
                    log_cliente(f"Archivo abierto via {ip_dueno}: {nombre} "
                                f"({'propio' if es_propio else 'ajeno'})", trace)
                    return
                else:
                    notificar_stale(ip, nombre, trace)
                    intentados_set.add(ip_dueno)
                    continue

            elif flags == "NACK":
                continue

        messagebox.showerror("No encontrado",
                              f"'{nombre}' no esta disponible en ningun servidor.")
        log_cliente(f"FALLO: {nombre} no encontrado", trace)

    def _guardar_archivo(self):
        if not self.archivo_actual:
            messagebox.showwarning("Aviso", "No hay archivo abierto.")
            return
        contenido_nuevo = self.txt_editor.get(1.0, tk.END).rstrip("\n")
        if contenido_nuevo == self.contenido_orig.rstrip("\n"):
            messagebox.showinfo("Sin cambios", "El archivo no fue modificado.")
            return

        trace     = str(uuid.uuid4())[:8]
        sync_data = {"nombre": self.archivo_actual, "mtime": time.time(),
                     "contenido": contenido_nuevo, "nuevo": False}

        # ★ usar enviar_fragmentado para soportar archivos grandes al guardar
        enviar_fragmentado_cliente(
            self.server_actual, "SYNC_BACK", json.dumps(sync_data), trace
        )

        if self.archivo_actual in self.cache_local:
            self.cache_local[self.archivo_actual]["mtime"] = sync_data["mtime"]
        log_cliente(f"SYNC_BACK enviado a {self.server_actual}: {self.archivo_actual}", trace)

        if not self.archivo_es_propio:
            enviar_unlock(self.server_actual, self.archivo_actual, trace)
            eliminar_copia_local(self.archivo_actual)

        self.archivo_actual    = None
        self.contenido_orig    = ""
        self.archivo_es_propio = False
        self.txt_editor.delete(1.0, tk.END)
        self.txt_editor.pack_forget()
        self.lbl_archivo.config(text="(ninguno)", fg="#7f8c8d")
        messagebox.showinfo("Sincronizacion",
                             f"Cambios enviados a {self.server_actual}.\nTrace ID: {trace}")

    def _compartir_archivo(self):
        ruta = filedialog.askopenfilename(title="Selecciona archivo a compartir",
                                           filetypes=[("Texto plano", "*.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        nombre = os.path.basename(ruta)
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()

        destino = None
        for ip in SERVER_IPS:
            resp = enviar_y_recibir(
                crear_paquete(0, 0, "REQ_LIST", "", "probe"), ip, timeout=2.0)
            if resp:
                destino = ip
                break
        if not destino:
            messagebox.showerror("Error", "Ningun servidor disponible.")
            return

        trace   = str(uuid.uuid4())[:8]
        mtime   = time.time()
        payload = {"nombre": nombre, "contenido": contenido, "mtime": mtime, "nuevo": True}

        # ★ usar enviar_fragmentado para soportar archivos grandes al compartir
        enviar_fragmentado_cliente(destino, "SYNC_BACK", json.dumps(payload), trace)

        self.cache_local[nombre] = {"nombre": nombre, "dueno": destino,
            "size": len(contenido.encode("utf-8")), "mtime": mtime, "ttl": 0}
        log_cliente(f"Archivo compartido: {nombre} -> {destino}", trace)
        messagebox.showinfo("Compartido",
                             f"'{nombre}' enviado a {destino}.\nTrace ID: {trace}")
        self.root.after(800, self._actualizar_lista)

    def _al_cerrar_app(self):
        if self.archivo_actual:
            self._cerrar_archivo(silencioso=True)
        limpiar_toda_la_cache()
        self.root.destroy()

    def _cargar_logs_completos(self):
        self.txt_logs.delete(1.0, tk.END)
        for log_file, tag in [("cliente.log", "cliente"), ("servidor.log", "servidor")]:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="latin-1") as f:
                    for linea in f:
                        self.txt_logs.insert(tk.END, f"[{log_file}] {linea}", tag)

    def _obtener_logs_remotos(self):
        trace = str(uuid.uuid4())[:8]
        self.txt_logs.delete(1.0, tk.END)
        for log_file, tag in [("cliente.log", "cliente"), ("servidor.log", "servidor")]:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="latin-1") as f:
                    for linea in f:
                        self.txt_logs.insert(tk.END, f"[LOCAL/{log_file}] {linea}", tag)
        for ip in SERVER_IPS:
            pkt  = crear_paquete(0, 0, "REQ_LOG", "", trace)
            resp = enviar_y_recibir(pkt, ip, timeout=5.0)
            if resp and resp.get("flags") == "RES_LOG":
                self.txt_logs.insert(
                    tk.END, f"\n{'='*60}\n[REMOTO servidor={ip}]\n{'='*60}\n", "remoto")
                for linea in resp.get("data", "").splitlines(keepends=True):
                    self.txt_logs.insert(tk.END, f"[{ip}] {linea}", "remoto")
            else:
                self.txt_logs.insert(tk.END, f"\n[REMOTO {ip}] Sin respuesta\n", "remoto")

    def _rastrear_log(self):
        tid = self.ent_trace.get().strip()
        if not tid:
            messagebox.showwarning("Aviso", "Escribe un Trace ID para rastrear.")
            return
        trace = str(uuid.uuid4())[:8]
        self.txt_logs.delete(1.0, tk.END)
        encontrados = 0
        for log_file in ["cliente.log", "servidor.log"]:
            if not os.path.exists(log_file):
                continue
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for linea in f:
                    if tid in linea:
                        self.txt_logs.insert(tk.END, f"[LOCAL/{log_file}] {linea}", "match")
                        encontrados += 1
        for ip in SERVER_IPS:
            pkt  = crear_paquete(0, 0, "REQ_LOG", "", trace)
            resp = enviar_y_recibir(pkt, ip, timeout=5.0)
            if resp and resp.get("flags") == "RES_LOG":
                for linea in resp.get("data", "").splitlines():
                    if tid in linea:
                        self.txt_logs.insert(tk.END, f"[REMOTO/{ip}] {linea}\n", "match")
                        encontrados += 1
            else:
                self.txt_logs.insert(tk.END, f"[REMOTO/{ip}] No se pudo obtener log\n", "remoto")
        if encontrados == 0:
            self.txt_logs.insert(tk.END, f"No se encontraron entradas para '{tid}'\n", "match")
        else:
            self.txt_logs.insert(
                tk.END, f"\n--- {encontrados} entradas para '{tid}' ---\n", "match")

    def _limpiar_logs(self):
        self.txt_logs.delete(1.0, tk.END)

    def _toggle_autorefresh(self):
        self.log_auto_refresh = self.var_autorefresh.get()

    def _hilo_refresh_logs(self):
        while True:
            time.sleep(2)
            if self.log_auto_refresh:
                try:
                    self.root.after(0, self._cargar_logs_completos)
                except Exception:
                    pass


if __name__ == "__main__":
    root = tk.Tk()
    app  = AppDistribuida(root)
    root.mainloop()