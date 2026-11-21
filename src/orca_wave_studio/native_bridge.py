from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import threading

from .contracts import WaveError


def format_copydata_payload(path: Path) -> str:
    def escape(value: str) -> str:
        return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('\r','\\r').replace('\n','\\n')+'"'
    return ";".join(escape(value) for value in ("orca-slicer.exe",str(path.resolve())))


def open_in_current_orca(path: Path, *, sliced_only: bool = True) -> None:
    try:
        import orca
        orca.host.app_info()
    except (ImportError,RuntimeError) as exc:
        raise WaveError("A abertura do Preview deve ocorrer na thread principal do Orca.") from exc
    suffix = ".gcode.3mf" if sliced_only else ".3mf"
    if not path.is_file() or not path.name.lower().endswith(suffix):
        raise WaveError("O arquivo de estudo precisa ser um pacote "+suffix+" existente.")
    if sys.platform != "win32":
        raise WaveError("A abertura nativa desta versão foi implementada para Windows; macOS aguarda validação.")
    user32=ctypes.WinDLL("user32",use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextLengthW.argtypes=[wintypes.HWND]
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.IsWindowVisible.argtypes=[wintypes.HWND]
    candidates=[]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def inspect(hwnd,_):
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value==os.getpid() and user32.IsWindowVisible(hwnd):
            title=ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd)+1)
            user32.GetWindowTextW(hwnd,title,len(title))
            if "OrcaSlicer" in title.value:
                candidates.append(hwnd)
        return True
    user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user32.EnumWindows(callback_type(inspect),0)
    if len(candidates)!=1:
        raise WaveError("Não foi possível identificar uma única janela principal deste processo Orca.")
    class COPYDATASTRUCT(ctypes.Structure):
        _fields_=[("dwData",ctypes.c_size_t),("cbData",wintypes.DWORD),("lpData",ctypes.c_void_p)]
    payload=ctypes.create_unicode_buffer(format_copydata_payload(path))
    data=COPYDATASTRUCT(1,ctypes.sizeof(payload),ctypes.cast(payload,ctypes.c_void_p))
    result=ctypes.c_size_t()
    user32.SendMessageTimeoutW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,
                                        wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    user32.SendMessageTimeoutW.restype=ctypes.c_size_t
    sent=user32.SendMessageTimeoutW(candidates[0],0x004A,0,ctypes.cast(ctypes.byref(data),ctypes.c_void_p).value,
                                   0x0002,2000,ctypes.byref(result))
    if not sent:
        raise WaveError("O Orca não confirmou o recebimento do pedido de abertura.")
