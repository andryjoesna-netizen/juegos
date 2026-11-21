# -*- coding: utf-8 -*-
"""Fútbol 1 vs 1: Tú (azul) contra La Máquina (roja).
Usa solo tkinter (viene con Python). El cerebro viene de ia_futbol.py.

Controles: flechas o W A S D para moverte | R reiniciar | Esc salir
Gana el primero en llegar a 5 goles. Tú atacas la portería derecha."""
import math
import random
import tkinter as tk

# ---------- Cerebro (con respaldo por si algo falla) ----------
try:
    from ia_futbol import CerebroFutbol, DIRS
    CEREBRO = CerebroFutbol()
    print(f"[IA] Cerebro cargado (motor: {CEREBRO.motor})")
except Exception as e:  # sin sklearn, sin archivo, etc.
    print(f"[IA] No pude cargar ia_futbol.py ({e.__class__.__name__}: {e}).")
    print("[IA] Uso un respaldo simple para que puedas jugar igual.")
    CEREBRO = None
    DIRS = [(0.0, 0.0)] + [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4))
                           for k in range(8)]


def decidir(fx, fy):
    """Devuelve (vx, vy) unitario hacia el objetivo usando el cerebro."""
    if CEREBRO is not None:
        try:
            return DIRS[CEREBRO.decidir([fx, fy])]
        except Exception:
            pass
    dx, dy = fx * 600, fy * 400
    if math.hypot(dx, dy) < 15:
        return (0.0, 0.0)
    k = int(round(math.atan2(dy, dx) / (math.pi / 4))) % 8
    return DIRS[1 + k]


# ---------- Configuración ----------
W, H = 900, 560
GOAL_H = 190
GOAL_TOP, GOAL_BOT = (H - GOAL_H) / 2, (H + GOAL_H) / 2
R_JUG, R_BAL = 17, 10
VEL_JUG, VEL_IA = 4.3, 3.7
PATADA = 8.5
FRICCION = 0.985
META = 5
FPS_MS = 16


def limitar(v, a, b):
    return max(a, min(b, v))


class Juego:
    def __init__(self, root):
        self.root = root
        root.title("Fútbol - Tú vs La Máquina")
        root.resizable(False, False)
        self.c = tk.Canvas(root, width=W, height=H, bg="#2e8b3d", highlightthickness=0)
        self.c.pack()

        self.teclas = set()
        self.pendientes = {}
        root.bind("<KeyPress>", self.tecla_abajo)
        root.bind("<KeyRelease>", self.tecla_arriba)
        root.bind("<Escape>", lambda e: root.destroy())
        root.bind("r", lambda e: self.reiniciar())
        root.bind("R", lambda e: self.reiniciar())
        root.focus_force()

        self.dibujar_cancha()
        self.j = self.c.create_oval(0, 0, 0, 0, fill="#1e6bff", outline="white", width=3)
        self.m = self.c.create_oval(0, 0, 0, 0, fill="#e03131", outline="white", width=3)
        self.b = self.c.create_oval(0, 0, 0, 0, fill="white", outline="black", width=2)
        self.t_marcador = self.c.create_text(W / 2, 22, text="", fill="white",
                                             font=("Arial", 22, "bold"))
        self.t_msg = self.c.create_text(W / 2, H / 2, text="", fill="yellow",
                                        font=("Arial", 34, "bold"))
        self.reiniciar()
        self.bucle()

    # ----- dibujo -----
    def dibujar_cancha(self):
        c = self.c
        c.create_rectangle(4, 4, W - 4, H - 4, outline="white", width=3)
        c.create_line(W / 2, 4, W / 2, H - 4, fill="white", width=3)
        c.create_oval(W / 2 - 70, H / 2 - 70, W / 2 + 70, H / 2 + 70, outline="white", width=3)
        c.create_rectangle(0, GOAL_TOP, 8, GOAL_BOT, fill="#1e6bff", outline="white", width=2)
        c.create_rectangle(W - 8, GOAL_TOP, W, GOAL_BOT, fill="#e03131", outline="white", width=2)

    def pintar(self, item, x, y, r):
        self.c.coords(item, x - r, y - r, x + r, y + r)

    # ----- teclado -----
    def tecla_abajo(self, e):
        k = e.keysym.lower()
        if k in self.pendientes:
            self.root.after_cancel(self.pendientes.pop(k))
        self.teclas.add(k)

    def tecla_arriba(self, e):
        k = e.keysym.lower()
        # Retraso corto: evita que Windows "corte" la tecla por la repetición automática
        self.pendientes[k] = self.root.after(25, lambda: self.soltar(k))

    def soltar(self, k):
        self.teclas.discard(k)
        self.pendientes.pop(k, None)

    # ----- estado -----
    def reiniciar(self):
        self.gj = 0
        self.gm = 0
        self.fin = False
        self.sacar(1)

    def sacar(self, _quien=1):
        self.px, self.py = W * 0.25, H / 2
        self.mx, self.my = W * 0.75, H / 2
        self.pvx = self.pvy = self.mvx = self.mvy = 0.0
        self.bx, self.by = W / 2, H / 2
        self.bvx = self.bvy = 0.0
        self.espera = 60  # ~1 segundo congelado
        self.cuenta = 0
        self.dir_ia = (0.0, 0.0)
        self.c.itemconfig(self.t_msg, text="")
        self.actualizar_marcador()

    def actualizar_marcador(self):
        self.c.itemconfig(self.t_marcador,
                          text=f"Tú {self.gj}  -  {self.gm} La Máquina")

    def gol(self, para_jugador):
        if para_jugador:
            self.gj += 1
        else:
            self.gm += 1
        self.actualizar_marcador()
        if self.gj >= META or self.gm >= META:
            self.fin = True
            ganador = "¡GANASTE!" if self.gj > self.gm else "Ganó La Máquina"
            self.c.itemconfig(self.t_msg, text=f"{ganador}\nR para reiniciar")
        else:
            self.c.itemconfig(self.t_msg, text="¡GOOOL!")
            self.sacar()
            self.espera = 90
            self.c.itemconfig(self.t_msg, text="¡GOOOL!")

    # ----- lógica -----
    def mover_jugador(self):
        t = self.teclas
        ax = (1 if ("right" in t or "d" in t) else 0) - (1 if ("left" in t or "a" in t) else 0)
        ay = (1 if ("down" in t or "s" in t) else 0) - (1 if ("up" in t or "w" in t) else 0)
        n = math.hypot(ax, ay) or 1
        self.pvx, self.pvy = ax / n * VEL_JUG, ay / n * VEL_JUG
        self.px = limitar(self.px + self.pvx, R_JUG, W - R_JUG)
        self.py = limitar(self.py + self.pvy, R_JUG, H - R_JUG)

    def mover_ia(self):
        # Objetivo: ponerse detrás del balón (del lado contrario a la portería que ataca)
        gx, gy = 0, H / 2  # La Máquina ataca la portería izquierda
        ox, oy = self.bx - gx, self.by - gy
        n = math.hypot(ox, oy) or 1
        tx = self.bx + ox / n * (R_BAL + R_JUG - 4)
        ty = self.by + oy / n * (R_BAL + R_JUG - 4)
        tx, ty = limitar(tx, R_JUG, W - R_JUG), limitar(ty, R_JUG, H - R_JUG)

        # El cerebro decide la dirección (cada 3 cuadros para ir fluido)
        if self.cuenta % 3 == 0:
            fx = limitar((tx - self.mx) / 600, -1, 1)
            fy = limitar((ty - self.my) / 400, -1, 1)
            self.dir_ia = decidir(fx, fy)
        self.cuenta += 1

        self.mvx, self.mvy = self.dir_ia[0] * VEL_IA, self.dir_ia[1] * VEL_IA
        self.mx = limitar(self.mx + self.mvx, R_JUG, W - R_JUG)
        self.my = limitar(self.my + self.mvy, R_JUG, H - R_JUG)

    def choque(self, x, y, vx, vy):
        dx, dy = self.bx - x, self.by - y
        d = math.hypot(dx, dy)
        if d < R_JUG + R_BAL:
            if d == 0:
                dx, dy, d = 1.0, 0.0, 1.0
            nx, ny = dx / d, dy / d
            self.bx = x + nx * (R_JUG + R_BAL + 0.5)
            self.by = y + ny * (R_JUG + R_BAL + 0.5)
            self.bvx = nx * PATADA + vx * 0.6
            self.bvy = ny * PATADA + vy * 0.6

    def mover_balon(self):
        self.bx += self.bvx
        self.by += self.bvy
        self.bvx *= FRICCION
        self.bvy *= FRICCION

        # Rebote arriba / abajo
        if self.by < R_BAL:
            self.by, self.bvy = R_BAL, abs(self.bvy)
        elif self.by > H - R_BAL:
            self.by, self.bvy = H - R_BAL, -abs(self.bvy)

        en_porteria = GOAL_TOP < self.by < GOAL_BOT
        if self.bx < R_BAL:
            if en_porteria:
                if self.bx < -R_BAL:
                    self.gol(False)
                return
            self.bx, self.bvx = R_BAL, abs(self.bvx)
        elif self.bx > W - R_BAL:
            if en_porteria:
                if self.bx > W + R_BAL:
                    self.gol(True)
                return
            self.bx, self.bvx = W - R_BAL, -abs(self.bvx)

    def paso(self):
        if self.fin:
            return
        if self.espera > 0:
            self.espera -= 1
            if self.espera == 0:
                self.c.itemconfig(self.t_msg, text="")
            return
        self.mover_jugador()
        self.mover_ia()
        self.choque(self.px, self.py, self.pvx, self.pvy)
        self.choque(self.mx, self.my, self.mvx, self.mvy)
        self.mover_balon()

    def bucle(self):
        self.paso()
        self.pintar(self.j, self.px, self.py, R_JUG)
        self.pintar(self.m, self.mx, self.my, R_JUG)
        self.pintar(self.b, self.bx, self.by, R_BAL)
        self.root.after(FPS_MS, self.bucle)


if __name__ == "__main__":
    root = tk.Tk()
    Juego(root)
    root.mainloop()
