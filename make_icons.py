"""Gera os ícones do Zenowing (PNG puro, sem dependências).

Desenho: um sigilo "primal" — losango prateado com núcleo vermelho,
sobre fundo escuro. Corre uma vez e escreve public/icon-192.png e
public/icon-512.png.
"""

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent / "public"

BG = (11, 13, 16)
SILVER_HI = (236, 240, 246)  # face iluminada
SILVER_LO = (138, 147, 160)  # face sombria
RED = (168, 35, 42)
RED_HI = (206, 74, 80)


def write_png(path: Path, size: int, rows: list[bytearray]) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def render_full(n: int) -> list[bytearray]:
    """Desenha em resolução n×n (com sobreamostragem feita fora)."""
    half = n / 2
    ring_out, ring_in = 0.74, 0.60
    core = 0.20
    tick_w, tick_from, tick_to = 0.022, 0.76, 0.90

    rows = []
    for y in range(n):
        row = bytearray()
        dy = y - half
        for x in range(n):
            dx = x - half
            d = (abs(dx) + abs(dy)) / half
            lit = (dx + dy) < 0  # face superior-esquerda iluminada
            col = BG

            if abs(dx) <= tick_w * half and tick_from <= abs(dy) / half <= tick_to:
                col = SILVER_HI if lit else SILVER_LO
            if ring_in <= d <= ring_out:
                col = SILVER_HI if lit else SILVER_LO
            if d <= core:
                col = RED_HI if lit else RED

            row += bytes(col)
        rows.append(row)
    return rows


def downsample(rows: list[bytearray]) -> list[bytearray]:
    n = len(rows)
    half = n // 2
    out = []
    for y in range(half):
        r0, r1 = rows[2 * y], rows[2 * y + 1]
        row = bytearray()
        for x in range(half):
            for c in range(3):
                row.append((r0[6 * x + c] + r0[6 * x + 3 + c] + r1[6 * x + c] + r1[6 * x + 3 + c]) // 4)
        out.append(row)
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for size in (192, 512):
        full = render_full(size * 2)
        write_png(OUT / f"icon-{size}.png", size, downsample(full))
        print(f"icon-{size}.png OK")


if __name__ == "__main__":
    main()
