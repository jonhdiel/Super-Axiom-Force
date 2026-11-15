"""Dump the decrypted CrimsonDesert.exe image from the running game.

The exe on disk is packed (its code is encrypted), so patch values must be read
from memory while the game is running. Run this while you are loaded into a
save, after using Axiom Force at least once.

Usage:  py dump_game.py <output.bin>
"""
import ctypes as C
import ctypes.wintypes as W
import struct
import subprocess
import sys

IMAGE_BASE = 0x140000000  # the game always loads here (the mod also requires it)


class MBI(C.Structure):
    _fields_ = [("BaseAddress", C.c_uint64), ("AllocationBase", C.c_uint64),
                ("AllocationProtect", W.DWORD), ("PartitionId", W.WORD),
                ("RegionSize", C.c_uint64), ("State", W.DWORD),
                ("Protect", W.DWORD), ("Type", W.DWORD)]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = sys.argv[1]

    k = C.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = W.HANDLE
    k.VirtualQueryEx.argtypes = [W.HANDLE, C.c_uint64, C.POINTER(MBI), C.c_size_t]
    k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_uint64, C.c_void_p, C.c_size_t,
                                    C.POINTER(C.c_size_t)]

    listing = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV", "/NH"]
    ).decode(errors="ignore")
    if "CrimsonDesert.exe" not in listing:
        sys.exit("CrimsonDesert.exe is not running. Start the game and load a save first.")
    pid = int(listing.split('","')[1])

    h = k.OpenProcess(0x0410, False, pid)  # QUERY_INFORMATION | VM_READ
    if not h:
        sys.exit(f"OpenProcess failed (error {C.get_last_error()}). Try an admin terminal.")

    hdr = C.create_string_buffer(0x1000)
    n = C.c_size_t()
    if not k.ReadProcessMemory(h, IMAGE_BASE, hdr, 0x1000, C.byref(n)):
        sys.exit("Could not read the game header at 0x140000000.")
    pe = struct.unpack_from("<I", hdr.raw, 0x3C)[0]
    size = struct.unpack_from("<I", hdr.raw, pe + 0x50)[0]

    img = bytearray(size)
    addr = IMAGE_BASE
    while addr < IMAGE_BASE + size:
        m = MBI()
        if not k.VirtualQueryEx(h, addr, C.byref(m), C.sizeof(m)):
            break
        end = min(m.BaseAddress + m.RegionSize, IMAGE_BASE + size)
        if m.State == 0x1000 and not (m.Protect & 0x101):  # committed, not NOACCESS/GUARD
            ln = end - addr
            buf = (C.c_char * ln)()
            if k.ReadProcessMemory(h, addr, buf, ln, C.byref(n)):
                img[addr - IMAGE_BASE:addr - IMAGE_BASE + n.value] = buf.raw[:n.value]
        addr = end

    open(out, "wb").write(img)
    ts = struct.unpack_from("<I", img, pe + 8)[0]
    print(f"Wrote {out} ({size / 2**20:.0f} MB). Game exe timestamp=0x{ts:08x} "
          f"size_of_image=0x{size:08x}")


if __name__ == "__main__":
    main()
