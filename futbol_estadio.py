# -*- coding: utf-8 -*-
"""SUPER FÚTBOL 3x3 - Estadio abierto
Tres chicas (rubia, morena y pelirroja) contra La Máquina (tres robots).
Solo usa librerías que vienen con Python (tkinter). El cerebro viene de ia_futbol.py.

Modos:  1) Invitado (1 jugador vs Máquina)
        2) Invitar amigo (2 jugadores en el mismo teclado, juntos vs Máquina)
        3) Duelo (tú vs tu amigo en el mismo teclado)
Controles:  P1 = W A S D + ESPACIO (tiro)   |   P2 = FLECHAS + ENTER (tiro)
            En modo 1 también puedes usar las flechas + ENTER.
            M = sonido on/off | R = repetir nivel | N = siguiente nivel | Esc = menú
"""
import array
import math
import os
import random
import sys
import tempfile
import time
import tkinter as tk
import wave

# ---------------------------------------------------------------- Cerebro IA
try:
    from ia_futbol import CerebroFutbol, DIRS
    CEREBRO = CerebroFutbol()
    print(f"[IA] Cerebro cargado (motor: {CEREBRO.motor})")
except Exception as e:
    print(f"[IA] No pude cargar ia_futbol.py ({e.__class__.__name__}: {e}).")
    print("[IA] Uso un respaldo simple para que puedas jugar igual.")
    CEREBRO = None
    DIRS = [(0.0, 0.0)] + [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4))
                           for k in range(8)]


def decidir(fx, fy):
    """Dirección unitaria (vx, vy) hacia el objetivo, elegida por el cerebro."""
    if CEREBRO is not None:
        try:
            return DIRS[CEREBRO.decidir([fx, fy])]
        except Exception:
            pass
    if math.hypot(fx * 600, fy * 400) < 15:
        return (0.0, 0.0)
    k = int(round(math.atan2(fy * 400, fx * 600) / (math.pi / 4))) % 8
    return DIRS[1 + k]


# ---------------------------------------------------------------- Constantes
W, H = 1100, 720
PL, PR, PT, PB = 90, 1010, 150, 590          # límites de la cancha
CX, CY = (PL + PR) // 2, (PT + PB) // 2
GOAL_H, GOAL_D = 130, 38
GY0, GY1 = CY - GOAL_H // 2, CY + GOAL_H // 2
R_P, R_B = 16, 9
VEL_H, VEL_AMIGO = 4.1, 3.2
FRICCION = 0.986
FPS = 60
TOTAL = 90 * FPS            # un partido dura 90 s reales (= 90 "minutos")
MITAD = TOTAL // 2

# (velocidad, frames entre decisiones, alcance de tiro, error de puntería)
NIVELES = [("Novato", (2.4, 7, 300, 0.35)), ("Aficionado", (2.9, 5, 340, 0.28)),
           ("Profesional", (3.4, 4, 380, 0.20)), ("Experto", (3.9, 3, 420, 0.12)),
           ("Leyenda", (4.2, 2, 460, 0.06))]
AMIGO = (VEL_AMIGO, 4, 350, 0.20)


def lim(v, a, b):
    return max(a, min(b, v))


# ---------------------------------------------------------------- Sonido
class Sonido:
    """Sonidos generados por código (sin archivos externos). Usa MCI de Windows."""
    SR = 16000

    def __init__(self):
        self.ok = False
        self.activo = True
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            self.winmm = ctypes.windll.winmm
            carpeta = os.path.join(tempfile.gettempdir(), "futbol3x3_sonidos_v1")
            os.makedirs(carpeta, exist_ok=True)
            nombres = ["pitido", "final", "gol", "patada", "tiro", "rebote", "ambiente", "clic"]
            faltan = any(not os.path.exists(os.path.join(carpeta, n + ".wav")) for n in nombres)
            sonidos = self.generar() if faltan else {n: None for n in nombres}
            for nombre, datos in sonidos.items():
                ruta = os.path.join(carpeta, nombre + ".wav")
                if datos is not None:
                    self.guardar(ruta, datos)
                self.cmd(f'close {nombre}')
                self.cmd(f'open "{ruta}" type waveaudio alias {nombre}')
            self.ok = True
        except Exception as e:
            print(f"[Sonido] desactivado ({e.__class__.__name__}: {e})")

    def cmd(self, texto):
        try:
            return self.winmm.mciSendStringW(texto, None, 0, None)
        except Exception:
            return -1

    def play(self, nombre, vol=800):
        if self.ok and self.activo:
            self.cmd(f"setaudio {nombre} volume to {vol}")
            self.cmd(f"play {nombre} from 0")

    def cerrar(self):
        if self.ok:
            self.cmd("close all")

    def guardar(self, ruta, muestras):
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.SR)
            w.writeframes(array.array("h", muestras).tobytes())

    # ---- síntesis
    def pitido(self, dur=0.55, f0=2900):
        n, fase, out = int(dur * self.SR), 0.0, []
        for i in range(n):
            t = i / self.SR
            f = f0 + 160 * math.sin(2 * math.pi * 26 * t)
            fase += 2 * math.pi * f / self.SR
            env = min(1, t / 0.02) * min(1, (dur - t) / 0.06)
            out.append(int(12000 * env * math.sin(fase)))
        return out

    def silencio(self, dur):
        return [0] * int(dur * self.SR)

    def golpe(self, dur, f_ini, f_fin, ruido, vol):
        n, fase, out = int(dur * self.SR), 0.0, []
        for i in range(n):
            t = i / self.SR
            f = f_fin + (f_ini - f_fin) * math.exp(-t * 25)
            fase += 2 * math.pi * f / self.SR
            env = math.exp(-t * (6 / dur))
            v = math.sin(fase) * (1 - ruido) + random.uniform(-1, 1) * ruido * math.exp(-t * 60)
            out.append(int(vol * env * v))
        return out

    def multitud(self, dur, vol, ola):
        n, y, out = int(dur * self.SR), 0.0, []
        for i in range(n):
            t = i / self.SR
            y += 0.12 * (random.uniform(-1, 1) - y)
            env = (0.55 + 0.45 * math.sin(math.pi * t / dur)) if ola else \
                  (0.6 + 0.4 * math.sin(2 * math.pi * t / 2.7))
            out.append(int(vol * env * y))
        return out

    def generar(self):
        p = self.pitido()
        final = p + self.silencio(0.12) + p + self.silencio(0.12) + self.pitido(0.9)
        gol = self.multitud(3.2, 20000, True)
        for i in range(int(0.5 * self.SR)):          # bocina corta al inicio del gol
            gol[i] = int(gol[i] * 0.5 + 6000 * math.sin(2 * math.pi * 440 * i / self.SR))
        return {"pitido": p, "final": final, "gol": gol,
                "patada": self.golpe(0.14, 200, 70, 0.4, 14000),
                "tiro": self.golpe(0.26, 260, 55, 0.5, 22000),
                "rebote": self.golpe(0.06, 700, 400, 0.2, 7000),
                "ambiente": self.multitud(8.0, 5200, False),
                "clic": self.golpe(0.07, 900, 880, 0.0, 9000)}


# ---------------------------------------------------------------- Dibujo
class Sprite:
    def __init__(self, c, tag):
        self.c, self.tag, self.x, self.y = c, tag, 0.0, 0.0

    def poner(self, x, y):
        self.c.move(self.tag, x - self.x, y - self.y)
        self.x, self.y = x, y


PIEL = "#ffdcb8"
# estilo: (vestido, pelo, iris)
ESTILOS = {0: ("#3fa9f5", "#ffd33d", "#2b7bff"),    # rubia con colitas
           1: ("#3ddc84", "#1d1d1d", "#1fae4b"),    # morena de pelo negro
           2: ("#ff6f91", "#ff8a1f", "#e8336d"),    # pelirroja con moño
           3: ("#7b2cbf", "#5a189a", "#00e5ff"),    # robots
           4: ("#4361ee", "#3a0ca3", "#00e5ff"),
           5: ("#c9184a", "#800f2f", "#00e5ff")}


def dibujar_jugador(c, tag, estilo):
    t = (tag,)
    vestido, pelo, iris = ESTILOS[estilo]
    c.create_oval(-16, 8, 16, 20, fill="#16511f", outline="", tags=t)        # sombra
    if estilo <= 2:
        if estilo == 0:                                                     # colitas
            c.create_oval(-27, -38, -9, -18, fill=pelo, outline="#b38f00", tags=t)
            c.create_oval(9, -38, 27, -18, fill=pelo, outline="#b38f00", tags=t)
        if estilo == 2:                                                     # pelo largo
            c.create_oval(-18, -44, 18, -8, fill=pelo, outline="#b35a00", tags=t)
        c.create_rectangle(-7, 8, -2, 17, fill=PIEL, outline="", tags=t)    # piernas
        c.create_rectangle(2, 8, 7, 17, fill=PIEL, outline="", tags=t)
        c.create_rectangle(-9, 15, -1, 20, fill="white", outline="black", tags=t)
        c.create_rectangle(1, 15, 9, 20, fill="white", outline="black", tags=t)
        c.create_polygon(-11, -14, 11, -14, 16, 9, -16, 9, fill=vestido,
                         outline="white", width=2, tags=t)                  # vestido
        c.create_oval(-15, -42, 15, -12, fill=PIEL, outline="#7a4b2a", tags=t)  # cabeza
        c.create_arc(-15, -42, 15, -12, start=0, extent=180, fill=pelo,
                     outline=pelo, style="chord", tags=t)
        if estilo == 1:
            c.create_oval(-17, -34, -9, -20, fill=pelo, outline=pelo, tags=t)
            c.create_oval(9, -34, 17, -20, fill=pelo, outline=pelo, tags=t)
        if estilo == 2:                                                     # moño rojo
            c.create_polygon(0, -42, -20, -54, -20, -34, fill="#e5183b", outline="#7a0a1f", tags=t)
            c.create_polygon(0, -42, 20, -54, 20, -34, fill="#e5183b", outline="#7a0a1f", tags=t)
            c.create_oval(-4, -46, 4, -38, fill="#b01028", outline="", tags=t)
        for ex in (-6, 6):                                                  # ojos grandes
            c.create_oval(ex - 6, -33, ex + 6, -19, fill="white", outline="black", tags=t)
            c.create_oval(ex - 4.5, -31, ex + 4.5, -21, fill=iris, outline="", tags=t)
        c.create_arc(-5, -20, 5, -12, start=200, extent=140, style="arc",
                     outline="#a03030", width=2, tags=t)                    # sonrisa
    else:                                                                   # robots
        c.create_rectangle(-8, 8, -3, 18, fill="#444", outline="", tags=t)
        c.create_rectangle(3, 8, 8, 18, fill="#444", outline="", tags=t)
        c.create_rectangle(-12, -16, 12, 9, fill=vestido, outline="white", width=2, tags=t)
        c.create_rectangle(-14, -42, 14, -16, fill=pelo, outline="white", width=2, tags=t)
        c.create_rectangle(-11, -36, 11, -22, fill="#0b0b12", outline="", tags=t)
        c.create_line(0, -42, 0, -52, fill="white", width=2, tags=t)
        c.create_oval(-4, -57, 4, -49, fill="#ff3b3b", outline="", tags=t)


def dibujar_arbitro(c, tag, bandera):
    t = (tag,)
    c.create_oval(-14, 8, 14, 18, fill="#16511f", outline="", tags=t)
    c.create_rectangle(-6, 6, -1, 16, fill=PIEL, outline="", tags=t)
    c.create_rectangle(1, 6, 6, 16, fill=PIEL, outline="", tags=t)
    c.create_rectangle(-10, -16, 10, 0, fill="#ffe14a", outline="black", tags=t)
    c.create_rectangle(-10, 0, 10, 8, fill="#111", outline="", tags=t)
    c.create_line(-10, -14, -18, -3, fill=PIEL, width=3, tags=t)
    c.create_line(10, -14, 18, -3, fill=PIEL, width=3, tags=t)
    c.create_oval(-9, -34, 9, -16, fill=PIEL, outline="#7a4b2a", tags=t)
    c.create_arc(-9, -34, 9, -16, start=0, extent=180, fill="#222", outline="#222",
                 style="chord", tags=t)
    c.create_oval(-2, -12, 2, -8, fill="silver", outline="black", tags=t)    # silbato
    if bandera:
        c.create_line(18, -3, 18, -30, fill="black", width=2, tags=t)
        c.create_rectangle(18, -30, 30, -20, fill="#ffd400", outline="red", tags=t)


class Jug:
    def __init__(self, c, n, eq, rol, estilo):
        self.eq, self.rol, self.estilo = eq, rol, estilo
        self.x = self.y = self.vx = self.vy = 0.0
        self.fx, self.fy = (1.0, 0.0) if eq == 0 else (-1.0, 0.0)
        self.cd, self.tdec, self.dir = 0, random.randint(0, 5), (0.0, 0.0)
        self.ctrl = None
        self.sp = Sprite(c, f"j{n}")
        dibujar_jugador(c, self.sp.tag, estilo)
        col = "#111" if estilo <= 2 else "#00e5ff"
        self.pup = [c.create_oval(0, 0, 0, 0, fill=col, outline="") for _ in range(2)]

    def casa(self):
        hx, hy = {0: (PL + 60, CY), 1: (PL + 250, CY - 85), 2: (CX - 60, CY + 60)}[self.rol]
        return (hx, hy) if self.eq == 0 else (PL + PR - hx, hy)


# ---------------------------------------------------------------- Juego
class Juego:
    def __init__(self, root):
        self.root = root
        root.title("SUPER FÚTBOL 3x3 - Estadio abierto")
        root.resizable(False, False)
        self.c = tk.Canvas(root, width=W, height=H, bg="#222", highlightthickness=0)
        self.c.pack()
        self.son = Sonido()
        self.nivel, self.modo, self.nombre = 0, "solo", "Invitado"
        self.estado = "menu"
        self.teclas, self.pend, self.nuevas = set(), {}, set()
        self.entry = tk.Entry(root, font=("Arial", 14), width=16, justify="center")
        self.entry.insert(0, "Invitado")
        self.cheer, self.pausa, self.pausa_fin = 0, 0, None
        self.msg_t, self.cuenta_son = 0, 0
        self.frames, self.ya_desc = 0, False
        self.gol = [0, 0]
        self.ctrls, self.equipos = [], [[], []]
        self.bx, self.by, self.bvx, self.bvy = CX, CY, 0.0, 0.0
        self.sonido_cd = 0

        root.bind("<KeyPress>", self.tecla_abajo)
        root.bind("<KeyRelease>", self.tecla_arriba)
        root.protocol("WM_DELETE_WINDOW", self.salir)

        self.dibujar_estadio()
        self.crear_entidades()
        self.mostrar_menu()
        self.ultimo, self.acum = time.perf_counter(), 0.0
        self.son.play("ambiente", 300)
        self.ambiente_t = 0
        self.bucle()

    # ------------------------------------------------------------ estadio
    def dibujar_estadio(self):
        c = self.c
        for i in range(8):                                         # cielo degradado
            g = 150 + i * 12
            c.create_rectangle(0, i * 5, W, i * 5 + 5, fill=f"#4a{g:02x}ff"[:7], outline="")
        c.create_rectangle(0, 40, W, H, fill="#5b5f66", outline="")  # concreto
        self.nubes = []
        for nx, ny in ((120, 12), (420, 22), (700, 8), (960, 20)):
            for dx, dy, r in ((0, 0, 16), (18, -5, 20), (38, 0, 15), (16, 6, 14)):
                c.create_oval(nx + dx - r, ny + dy - r // 2, nx + dx + r, ny + dy + r // 2,
                              fill="white", outline="", tags=("nube",))
        self.nube_x = 0.0
        for sx in (14, 1066):                                      # torres de luz
            c.create_rectangle(sx + 8, 20, sx + 14, 150, fill="#444", outline="")
            c.create_rectangle(sx - 6, 10, sx + 28, 32, fill="#fff6b0", outline="#999")
        # pasto
        c.create_rectangle(40, PT - 24, W - 40, PB + 24, fill="#256f2c", outline="")
        ancho = (PR - PL) / 14
        for i in range(14):
            col = "#2f8f38" if i % 2 == 0 else "#2a8032"
            c.create_rectangle(PL + i * ancho, PT, PL + (i + 1) * ancho, PB, fill=col, outline="")
        # publico
        pal = ["#ff4d4d", "#4da3ff", "#ffd84a", "#ffffff", "#3ddc84", "#b36bff", "#ff9f43", "#222"]
        self.pal, self.publico = pal, []
        filas = [(y, 0) for y in range(44, 118, 12)] + [(y, 0) for y in range(630, 700, 12)]
        for fila, (y, _) in enumerate(filas):
            for x in range(8 + (fila % 2) * 7, W, 14):
                self.publico.append(c.create_oval(x - 5, y - 5, x + 5, y + 5,
                                                  fill=random.choice(pal), outline=""))
        # vallas publicitarias
        textos = ["SUPER GOL", "FÚTBOL 3x3", "LA MÁQUINA", "ENERGÍA+", "CHICAS FC", "MEGA PASTO"]
        cols = ["#d62828", "#1d3557", "#f77f00", "#2a9d8f", "#6a4c93", "#e9c46a"]
        for lado, y in ((0, PT - 24), (1, PB + 8)):
            for i in range(6):
                x0 = 40 + i * (W - 80) / 6
                k = (i + lado * 3) % 6
                c.create_rectangle(x0, y, x0 + (W - 80) / 6, y + 16, fill=cols[k], outline="white")
                c.create_text(x0 + (W - 80) / 12, y + 8, text=textos[k], fill="white",
                              font=("Arial", 9, "bold"))
        # lineas de la cancha
        L = dict(outline="white", width=3)
        c.create_rectangle(PL, PT, PR, PB, **L)
        c.create_line(CX, PT, CX, PB, fill="white", width=3)
        c.create_oval(CX - 62, CY - 62, CX + 62, CY + 62, **L)
        c.create_oval(CX - 4, CY - 4, CX + 4, CY + 4, fill="white", outline="")
        for lado in (0, 1):
            s = 1 if lado == 0 else -1
            x0 = PL if lado == 0 else PR
            c.create_rectangle(x0, CY - 120, x0 + s * 115, CY + 120, **L)
            c.create_rectangle(x0, CY - 65, x0 + s * 42, CY + 65, **L)
            c.create_oval(x0 + s * 84 - 3, CY - 3, x0 + s * 84 + 3, CY + 3, fill="white", outline="")
            c.create_arc(x0 + s * 115 - 40, CY - 40, x0 + s * 115 + 40, CY + 40,
                         start=-53 if lado == 0 else 127, extent=106, style="arc",
                         outline="white", width=3)
            gx0, gx1 = (PL - GOAL_D, PL) if lado == 0 else (PR, PR + GOAL_D)
            c.create_rectangle(gx0, GY0, gx1, GY1, fill="#d9e8d9", outline="white", width=3,
                               stipple="gray50")
            for k in range(1, 7):
                c.create_line(gx0, GY0 + k * GOAL_H / 7, gx1, GY0 + k * GOAL_H / 7, fill="#bbb")
            for k in range(1, 4):
                xx = gx0 + k * GOAL_D / 4
                c.create_line(xx, GY0, xx, GY1, fill="#bbb")
            c.create_oval(x0 - 4, GY0 - 4, x0 + 4, GY0 + 4, fill="white", outline="")
            c.create_oval(x0 - 4, GY1 - 4, x0 + 4, GY1 + 4, fill="white", outline="")
        for cx_, cy_ in ((PL, PT), (PR, PT), (PL, PB), (PR, PB)):
            c.create_oval(cx_ - 4, cy_ - 4, cx_ + 4, cy_ + 4, fill="#ffd400", outline="")

    def crear_entidades(self):
        c = self.c
        self.jug = []
        estilos = {0: (0, 1, 2), 1: (3, 4, 5)}
        n = 0
        for eq in (0, 1):
            for rol in (0, 1, 2):
                j = Jug(c, n, eq, rol, estilos[eq][rol])
                self.equipos[eq].append(j)
                self.jug.append(j)
                n += 1
        self.arb = Sprite(c, "arb")
        dibujar_arbitro(c, "arb", False)
        self.lin = [Sprite(c, "lin0"), Sprite(c, "lin1")]
        dibujar_arbitro(c, "lin0", True)
        dibujar_arbitro(c, "lin1", True)
        self.b_sombra = c.create_oval(0, 0, 0, 0, fill="#16511f", outline="")
        self.b_bola = c.create_oval(0, 0, 0, 0, fill="white", outline="black", width=2)
        self.b_mancha = c.create_oval(0, 0, 0, 0, fill="#222", outline="")
        self.marcas = []
        for col in ("#ffffff", "#ffe14a"):
            ring = c.create_oval(0, 0, 0, 0, outline=col, width=3)
            txt = c.create_text(0, 0, text="", fill=col, font=("Arial", 11, "bold"))
            self.marcas.append((ring, txt))
        # HUD
        c.create_rectangle(CX - 250, 46, CX + 250, 104, fill="#0b1020", outline="white",
                           width=2, tags=("hud",))
        self.t_marc = c.create_text(CX, 66, text="", fill="white", font=("Arial", 20, "bold"),
                                    tags=("hud",))
        self.t_info = c.create_text(CX, 91, text="", fill="#ffd84a", font=("Arial", 11, "bold"),
                                    tags=("hud",))
        c.create_rectangle(0, H - 20, W, H, fill="#0b1020", outline="", tags=("hud",))
        c.create_text(CX, H - 10, fill="white", font=("Arial", 9, "bold"), tags=("hud",),
                      text="P1: W A S D + ESPACIO    P2: FLECHAS + ENTER    M sonido    "
                           "R repetir    Esc menú")
        self.t_msg_s = c.create_text(CX + 3, CY + 3, text="", fill="black",
                                     font=("Arial", 44, "bold"), justify="center", tags=("msg",))
        self.t_msg = c.create_text(CX, CY, text="", fill="#ffe14a",
                                   font=("Arial", 44, "bold"), justify="center", tags=("msg",))

    # ------------------------------------------------------------ teclado
    def tecla_abajo(self, e):
        k = e.keysym.lower()
        if k in self.pend:
            self.root.after_cancel(self.pend.pop(k))
        if k not in self.teclas:
            self.nuevas.add(k)
        self.teclas.add(k)
        if k == "m" and self.root.focus_get() is not self.entry:
            self.son.activo = not self.son.activo
            if not self.son.activo:
                self.son.cmd("stop ambiente")
        if k == "escape":
            if self.estado == "menu":
                self.salir()
            else:
                self.mostrar_menu()
        elif self.estado in ("juego", "fin"):
            if k == "r":
                self.iniciar(self.modo)
            elif k == "n" and self.estado == "fin" and self.gol[0] > self.gol[1] \
                    and self.nivel < len(NIVELES) - 1:
                self.nivel += 1
                self.iniciar(self.modo)

    def tecla_arriba(self, e):
        k = e.keysym.lower()
        self.pend[k] = self.root.after(25, lambda: self.soltar(k))

    def soltar(self, k):
        self.teclas.discard(k)
        self.pend.pop(k, None)

    def salir(self):
        self.son.cerrar()
        self.root.destroy()

    # ------------------------------------------------------------ menu
    def boton(self, y, texto, cmd, color, ancho=560):
        c, tag = self.c, f"b{y}"
        c.create_rectangle(CX - ancho / 2, y - 22, CX + ancho / 2, y + 22, fill=color,
                           outline="white", width=2, tags=("menu", tag))
        c.create_text(CX, y, text=texto, fill="white", font=("Arial", 14, "bold"),
                      tags=("menu", tag))
        c.tag_bind(tag, "<Button-1>", lambda e: (self.son.play("clic"), cmd()))

    def mostrar_menu(self):
        self.estado = "menu"
        c = self.c
        c.delete("menu")
        c.delete("fin")
        c.itemconfig("msg", text="")
        c.create_rectangle(CX - 340, 150, CX + 340, 660, fill="#10213f", outline="white",
                           width=3, tags=("menu",))
        c.create_text(CX, 195, text="SUPER FÚTBOL 3x3", fill="#ffe14a",
                      font=("Arial", 36, "bold"), tags=("menu",))
        c.create_text(CX, 232, text="Tres chicas contra La Máquina  -  ¡estadio abierto!",
                      fill="white", font=("Arial", 13), tags=("menu",))
        c.create_text(CX - 150, 275, text="Tu nombre:", fill="white",
                      font=("Arial", 14, "bold"), tags=("menu",))
        c.create_window(CX + 40, 275, window=self.entry, tags=("menu",))
        self.boton(335, "JUGAR COMO INVITADO   (1 jugador vs Máquina)",
                   lambda: self.iniciar("solo"), "#2b7bff")
        self.boton(395, "INVITAR AMIGO   (2 jugadores juntos vs Máquina)",
                   lambda: self.iniciar("coop"), "#1fae4b")
        self.boton(455, "DUELO   (tú vs tu amigo)", lambda: self.iniciar("duelo"), "#e5183b")
        self.boton(520, "", lambda: None, "#10213f", 360)
        self.t_nivel = c.create_text(CX, 520, text="", fill="#ffe14a",
                                     font=("Arial", 15, "bold"), tags=("menu",))
        self.boton_pequeno(CX - 215, 520, "◀", -1)
        self.boton_pequeno(CX + 215, 520, "▶", 1)
        self.refrescar_nivel()
        c.create_text(CX, 585, fill="#cfd8ff", font=("Arial", 11), tags=("menu",), justify="center",
                      text="P1: W A S D + ESPACIO (tiro)      P2: FLECHAS + ENTER (tiro)\n"
                           "Ganando un partido pasas al siguiente nivel.  M: sonido")
        c.create_text(CX, 635, text="Esc para salir", fill="#8899cc", font=("Arial", 10),
                      tags=("menu",))
        c.tag_raise("menu")

    def boton_pequeno(self, x, y, txt, d):
        tag = f"bp{d}"
        self.c.create_rectangle(x - 22, y - 20, x + 22, y + 20, fill="#3a4a7a", outline="white",
                                width=2, tags=("menu", tag))
        self.c.create_text(x, y, text=txt, fill="white", font=("Arial", 14, "bold"),
                           tags=("menu", tag))
        self.c.tag_bind(tag, "<Button-1>", lambda e: self.cambiar_nivel(d))

    def cambiar_nivel(self, d):
        self.nivel = (self.nivel + d) % len(NIVELES)
        self.son.play("clic")
        self.refrescar_nivel()

    def refrescar_nivel(self):
        self.c.itemconfig(self.t_nivel, text=f"NIVEL {self.nivel + 1}: {NIVELES[self.nivel][0]}")

    # ------------------------------------------------------------ partido
    def iniciar(self, modo):
        nombre = self.entry.get().strip()[:14] if self.estado == "menu" else self.nombre
        self.nombre = nombre or "Invitado"
        self.modo = modo
        self.c.delete("menu")
        self.c.delete("fin")
        self.nuevas.clear()
        self.c.focus_set()
        wasd = {"up": ("w",), "down": ("s",), "left": ("a",), "right": ("d",)}
        flechas = {"up": ("up",), "down": ("down",), "left": ("left",), "right": ("right",)}
        mix = {k: wasd[k] + flechas[k] for k in wasd}
        if modo == "solo":
            self.ctrls = [dict(eq=0, mov=mix, tiro=("space", "return"), n="P1", col=0)]
            self.nom = [self.nombre, "Máquina"]
        elif modo == "coop":
            self.ctrls = [dict(eq=0, mov=wasd, tiro=("space",), n="P1", col=0),
                          dict(eq=0, mov=flechas, tiro=("return",), n="P2", col=1)]
            self.nom = [self.nombre + " + Amigo", "Máquina"]
        else:
            self.ctrls = [dict(eq=0, mov=wasd, tiro=("space",), n="P1", col=0),
                          dict(eq=1, mov=flechas, tiro=("return",), n="P2", col=1)]
            self.nom = [self.nombre, "Amigo"]
        for ct in self.ctrls:
            ct["act"] = None
        self.gol = [0, 0]
        self.frames, self.ya_desc = 0, False
        self.estado = "juego"
        self.c.itemconfig("msg", text="")
        self.actualizar_hud()
        self.kickoff()

    def parametros(self, eq):
        if eq == 1 and self.modo != "duelo":
            return NIVELES[self.nivel][1]
        return AMIGO

    def kickoff(self):
        for j in self.jug:
            j.x, j.y = j.casa()
            j.vx = j.vy = 0.0
            j.cd = 0
            j.dir = (0.0, 0.0)
            j.fx, j.fy = (1.0, 0.0) if j.eq == 0 else (-1.0, 0.0)
        self.bx, self.by, self.bvx, self.bvy = CX, CY, 0.0, 0.0
        self.set_msg("¡A JUGAR!")
        self.pausa, self.pausa_fin, self.pausa_tipo = 75, self.arrancar, "inicio"

    def arrancar(self):
        self.set_msg("")
        self.son.play("pitido")

    def set_msg(self, texto):
        self.c.itemconfig(self.t_msg, text=texto)
        self.c.itemconfig(self.t_msg_s, text=texto)

    def actualizar_hud(self):
        self.c.itemconfig(self.t_marc, text=f"{self.nom[0]}  {self.gol[0]} - {self.gol[1]}  {self.nom[1]}")
        minuto = int(self.frames / TOTAL * 90)
        parte = "1T" if self.frames < MITAD else "2T"
        self.c.itemconfig(self.t_info, text=f"{minuto}'  {parte}   |   Nivel {self.nivel + 1}: "
                                            f"{NIVELES[self.nivel][0]}")

    # ------------------------------------------------------------ lógica
    def dist_balon(self, p):
        return math.hypot(self.bx - p.x, self.by - p.y)

    def elegir_activos(self):
        tomados = set()
        for p in self.jug:
            p.ctrl = None
        for ct in self.ctrls:
            cand = [p for p in self.equipos[ct["eq"]] if p.rol != 0 and id(p) not in tomados]
            mejor = min(cand, key=self.dist_balon)
            act = ct["act"]
            if act is None or act not in cand or self.dist_balon(mejor) + 35 < self.dist_balon(act):
                ct["act"] = mejor
            tomados.add(id(ct["act"]))
            ct["act"].ctrl = ct

    def mover_humano(self, p, ct):
        t = self.teclas
        ax = (any(k in t for k in ct["mov"]["right"])) - (any(k in t for k in ct["mov"]["left"]))
        ay = (any(k in t for k in ct["mov"]["down"])) - (any(k in t for k in ct["mov"]["up"]))
        n = math.hypot(ax, ay) or 1
        p.vx, p.vy = ax / n * VEL_H, ay / n * VEL_H
        if ax or ay:
            p.fx, p.fy = ax / n, ay / n
        if any(k in self.nuevas for k in ct["tiro"]) and self.dist_balon(p) < R_P + R_B + 16:
            gx = PR if p.eq == 0 else PL
            gdx, gdy = gx - self.bx, CY - self.by
            gn = math.hypot(gdx, gdy) or 1
            self.tirar(p, p.fx * 0.75 + gdx / gn * 0.35, p.fy * 0.75 + gdy / gn * 0.35, 12.5)

    def tirar(self, p, dx, dy, pot):
        n = math.hypot(dx, dy) or 1
        self.bvx, self.bvy = dx / n * pot, dy / n * pot
        p.cd = 30
        self.son.play("tiro", 900)

    def objetivo_chaser(self, p):
        gx = PR if p.eq == 0 else PL
        gdx, gdy = gx - self.bx, CY - self.by
        gn = math.hypot(gdx, gdy) or 1
        gdx, gdy = gdx / gn, gdy / gn
        rx, ry = p.x - self.bx, p.y - self.by
        if rx * gdx + ry * gdy > -4 and math.hypot(rx, ry) < 110:      # rodear el balón
            lado = 1 if (-gdy * rx + gdx * ry) >= 0 else -1
            return (self.bx - gdx * 45 - gdy * lado * 55, self.by - gdy * 45 + gdx * lado * 55)
        d = R_P + R_B - 5
        return self.bx - gdx * d, self.by - gdy * d

    def mover_ia(self, p, chaser):
        vel, react, alcance, err = self.parametros(p.eq)
        gx = PR if p.eq == 0 else PL
        hx, hy = p.casa()
        if p is chaser:
            tx, ty = self.objetivo_chaser(p)
        elif p.rol == 0:
            tx, ty = hx, CY + lim(self.by - CY, -55, 55)
        else:
            k = 0.5 if p.rol == 1 else 0.7
            tx, ty = hx + (self.bx - hx) * k, hy + (self.by - hy) * 0.4
        tx, ty = lim(tx, PL + R_P, PR - R_P), lim(ty, PT + R_P, PB - R_P)
        p.tdec -= 1
        if p.tdec <= 0:
            p.tdec = react
            p.dir = decidir(lim((tx - p.x) / 600, -1, 1), lim((ty - p.y) / 400, -1, 1))
        p.vx, p.vy = p.dir[0] * vel, p.dir[1] * vel
        if p.dir != (0.0, 0.0):
            p.fx, p.fy = p.dir
        if p.cd == 0 and self.dist_balon(p) < R_P + R_B + 6:
            if p.rol == 0 or abs(p.x - gx) > 800:                       # despejar
                if random.random() < 0.25:
                    self.tirar(p, CX - p.x, random.uniform(-150, 150), 11)
            elif abs(p.x - gx) < alcance and random.random() < 0.15:    # disparar
                self.tirar(p, gx - self.bx,
                           CY + random.uniform(-45, 45) + random.uniform(-1, 1) * err * 200 - self.by, 11.5)

    def separar(self):
        for i, a in enumerate(self.jug):
            for b in self.jug[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if 0 < d < 2 * R_P:
                    push = (2 * R_P - d) / 2
                    a.x -= dx / d * push
                    a.y -= dy / d * push
                    b.x += dx / d * push
                    b.y += dy / d * push

    def toque(self, p):
        dx, dy = self.bx - p.x, self.by - p.y
        d = math.hypot(dx, dy)
        mind = R_P + R_B
        if d < mind:
            if d < 0.001:
                dx, dy, d = p.fx, p.fy, 1.0
            nx, ny = dx / d, dy / d
            self.bx, self.by = p.x + nx * (mind + 0.5), p.y + ny * (mind + 0.5)
            self.bvx = nx * 4.2 + p.vx * 0.9
            self.bvy = ny * 4.2 + p.vy * 0.9
            if self.sonido_cd <= 0 and math.hypot(self.bvx, self.bvy) > 5.5:
                self.son.play("patada", 650)
                self.sonido_cd = 10

    def mover_balon(self, libre=False):
        self.bx += self.bvx
        self.by += self.bvy
        self.bvx *= FRICCION
        self.bvy *= FRICCION
        v = math.hypot(self.bvx, self.bvy)
        if v > 17:
            self.bvx, self.bvy = self.bvx / v * 17, self.bvy / v * 17
        rebote = False
        if self.by < PT + R_B:
            self.by, self.bvy, rebote = PT + R_B, abs(self.bvy), True
        elif self.by > PB - R_B:
            self.by, self.bvy, rebote = PB - R_B, -abs(self.bvy), True
        en_porteria = GY0 + R_B < self.by < GY1 - R_B
        if self.bx < PL + R_B and (en_porteria or self.bx < PL):
            if not libre and self.bx < PL - R_B:
                self.marcar(1)
                return
            if self.bx < PL - GOAL_D + R_B:
                self.bx, self.bvx = PL - GOAL_D + R_B, abs(self.bvx) * 0.3
            self.by = lim(self.by, GY0 + R_B, GY1 - R_B)
        elif self.bx > PR - R_B and (en_porteria or self.bx > PR):
            if not libre and self.bx > PR + R_B:
                self.marcar(0)
                return
            if self.bx > PR + GOAL_D - R_B:
                self.bx, self.bvx = PR + GOAL_D - R_B, -abs(self.bvx) * 0.3
            self.by = lim(self.by, GY0 + R_B, GY1 - R_B)
        elif self.bx < PL + R_B:
            self.bx, self.bvx, rebote = PL + R_B, abs(self.bvx), True
        elif self.bx > PR - R_B:
            self.bx, self.bvx, rebote = PR - R_B, -abs(self.bvx), True
        if rebote and v > 4 and self.sonido_cd <= 0:
            self.son.play("rebote", 500)
            self.sonido_cd = 8

    def marcar(self, eq):
        self.gol[eq] += 1
        self.cheer = 260
        self.son.play("gol", 1000)
        self.set_msg("¡GOOOOL!")
        self.actualizar_hud()
        self.pausa, self.pausa_fin, self.pausa_tipo = 170, self.kickoff, "gol"

    def mover_arbitros(self):
        tx = lim(self.bx - 70 * (1 if self.bx > CX else -1) * 0.8, PL + 20, PR - 20)
        ty = lim(self.by + 75 if self.by < CY + 40 else self.by - 75, PT + 20, PB - 20)
        d = math.hypot(tx - self.arb.x, ty - self.arb.y)
        if d > 1:
            k = min(2.6, d) / d
            self.arb.x += (tx - self.arb.x) * k
            self.arb.y += (ty - self.arb.y) * k
        for i, ln in enumerate(self.lin):
            ln.x += (lim(self.bx, PL, PR) - ln.x) * 0.06
            ln.y = PT + 12 if i == 0 else PB - 4

    def paso(self):
        self.sonido_cd -= 1
        self.animar_publico()
        if self.estado != "juego":
            return
        if self.pausa > 0:
            self.pausa -= 1
            self.nuevas.clear()
            if self.pausa_tipo == "gol":
                self.mover_balon(libre=True)
            if self.pausa == 0 and self.pausa_fin:
                f, self.pausa_fin = self.pausa_fin, None
                f()
            return
        self.elegir_activos()
        chasers = {}
        for eq in (0, 1):
            cand = [p for p in self.equipos[eq] if p.ctrl is None and
                    (p.rol != 0 or abs(self.bx - p.casa()[0]) < 230)]
            chasers[eq] = min(cand, key=self.dist_balon) if cand else None
        for p in self.jug:
            if p.ctrl is not None:
                self.mover_humano(p, p.ctrl)
            else:
                self.mover_ia(p, chasers[p.eq])
            p.x = lim(p.x + p.vx, PL + R_P, PR - R_P)
            p.y = lim(p.y + p.vy, PT + R_P, PB - R_P)
            if p.cd > 0:
                p.cd -= 1
        self.nuevas.clear()
        self.separar()
        for p in self.jug:
            if p.cd < 24:
                self.toque(p)
        self.mover_balon()
        self.mover_arbitros()
        self.frames += 1
        if self.frames % 30 == 0:
            self.actualizar_hud()
        if self.frames >= MITAD and not self.ya_desc:
            self.ya_desc = True
            self.son.play("pitido")
            self.set_msg("DESCANSO")
            self.pausa, self.pausa_fin, self.pausa_tipo = 150, self.kickoff, "descanso"
        elif self.frames >= TOTAL:
            self.terminar()

    def terminar(self):
        self.estado = "fin"
        self.actualizar_hud()
        self.son.play("final")
        a, b = self.gol
        if a > b:
            txt = "¡GANASTE!" if self.modo != "duelo" else f"¡Gana {self.nom[0]}!"
            self.cheer = 400
            extra = "N: siguiente nivel   R: repetir   Esc: menú" if self.nivel < len(NIVELES) - 1 \
                else "¡ERES CAMPEÓN DE LA LEYENDA!   R: repetir   Esc: menú"
        elif a < b:
            txt = "Perdiste..." if self.modo != "duelo" else f"¡Gana {self.nom[1]}!"
            extra = "R: intentar de nuevo   Esc: menú"
        else:
            txt, extra = "¡Empate!", "R: jugar de nuevo   Esc: menú"
        self.set_msg(f"{txt}\n")
        self.c.itemconfig(self.t_msg, font=("Arial", 44, "bold"))
        self.c.delete("fin")
        self.c.create_text(CX, CY + 55, text=extra, fill="white", font=("Arial", 16, "bold"),
                           tags=("fin",))

    # ------------------------------------------------------------ animación
    def animar_publico(self):
        n = len(self.publico)
        if self.cheer > 0:
            self.cheer -= 1
            if self.cheer % 4 == 0:
                for _ in range(120):
                    self.c.itemconfig(self.publico[random.randrange(n)],
                                      fill=random.choice(self.pal))
        elif random.random() < 0.3:
            for _ in range(6):
                self.c.itemconfig(self.publico[random.randrange(n)], fill=random.choice(self.pal))
        self.c.move("nube", 0.2, 0)
        self.nube_x += 0.2
        if self.nube_x > 1300:
            self.c.move("nube", -1500, 0)
            self.nube_x -= 1500
        self.ambiente_t += 1
        if self.ambiente_t >= 8 * FPS - 10:
            self.ambiente_t = 0
            self.son.play("ambiente", 250)

    def pintar(self):
        c = self.c
        items = list(self.jug)
        for p in items:
            p.sp.poner(p.x, p.y - 10)
            for k, ex in enumerate((-6, 6)):
                px = p.x + ex + p.fx * 2.2
                py = p.y - 10 - 26 + p.fy * 2.2
                c.coords(p.pup[k], px - 2.2, py - 2.2, px + 2.2, py + 2.2)
        self.arb.poner(self.arb.x, self.arb.y)
        for ln in self.lin:
            ln.poner(ln.x, ln.y)
        for s in [self.arb] + self.lin:
            c.tag_raise(s.tag)
        for p in sorted(items, key=lambda q: q.y):
            c.tag_raise(p.sp.tag)
            for pid in p.pup:
                c.tag_raise(pid)
        bx, by = self.bx, self.by
        c.coords(self.b_sombra, bx - 8, by + 4, bx + 9, by + 11)
        c.coords(self.b_bola, bx - R_B, by - R_B - 2, bx + R_B, by + R_B - 2)
        c.coords(self.b_mancha, bx - 3, by - 5, bx + 3, by + 1)
        for it in (self.b_sombra, self.b_bola, self.b_mancha):
            c.tag_raise(it)
        for i, (ring, txt) in enumerate(self.marcas):
            ct = self.ctrls[i] if i < len(self.ctrls) and self.estado == "juego" else None
            if ct and ct["act"] is not None:
                a = ct["act"]
                c.coords(ring, a.x - 20, a.y - 2, a.x + 20, a.y + 14)
                c.coords(txt, a.x, a.y - 68)
                c.itemconfig(txt, text="▼ " + ct["n"])
                c.tag_raise(ring)
                c.tag_raise(txt)
            else:
                c.coords(ring, 0, 0, 0, 0)
                c.itemconfig(txt, text="")
        c.tag_raise("hud")
        c.tag_raise("msg")
        c.tag_raise("fin")
        c.tag_raise("menu")

    def bucle(self):
        ahora = time.perf_counter()
        self.acum += min(ahora - self.ultimo, 0.1)
        self.ultimo = ahora
        n = 0
        while self.acum >= 1 / FPS and n < 4:
            self.paso()
            self.acum -= 1 / FPS
            n += 1
        self.pintar()
        self.root.after(8, self.bucle)


if __name__ == "__main__":
    root = tk.Tk()
    Juego(root)
    root.mainloop()
    