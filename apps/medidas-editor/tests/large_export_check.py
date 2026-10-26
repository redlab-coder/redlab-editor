"""Real 212 MP output; inspect raster edges through libvips without full decode."""
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import export_jpeg


def resident_bytes():
    if os.name=='nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                      *[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
                          'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage',
                          'PagefileUsage','PeakPagefileUsage','PrivateUsage')]]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
        function=ctypes.WinDLL('psapi').GetProcessMemoryInfo
        function.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),wintypes.DWORD]
        if not function(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):raise ctypes.WinError()
        return counters.PeakWorkingSetSize
    import resource
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform=='darwin' else value*1024


def run():
    start=time.monotonic();peak=0;stop=threading.Event()
    def monitor():
        nonlocal peak
        while not stop.wait(.025):peak=max(peak,resident_bytes())
    thread=threading.Thread(target=monitor);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='MedidasEditor-large-test-') as temporary:
            root=Path(temporary);source=root/'source.png';result=root/'61x250.jpg'
            Image.new('RGB',(1220,5000),(150,70,30)).save(source)
            export_jpeg(source,dict(width_cm='61',height_cm='250'),result)
            # Header inspection only: Pillow's decompression-bomb input safeguard
            # remains active elsewhere, while output is inspected in bounded tiles.
            import pyvips
            image=pyvips.Image.new_from_file(str(result),access='random')
            assert [image.width,image.height]==[7205,29528]
            assert abs(image.xres*25.4-300)<.01 and abs(image.yres*25.4-300)<.01
            center=image.crop(3500,14000,16,16).avg()
            assert center<240
            peak=max(peak,resident_bytes())
            assert peak<650*1024**2,f'Peak memory {peak/1024**2:.1f} MiB exceeds the export budget'
            report=dict(output_px=[image.width,image.height],dpi=300,peak_rss_mib=round(peak/1024**2,1),
                        seconds=round(time.monotonic()-start,2),jpeg_bytes=result.stat().st_size)
            image=None
        (ROOT/'tests/artifacts').mkdir(exist_ok=True)
        (ROOT/'tests/artifacts/large-export.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
    finally:
        stop.set();thread.join()


if __name__=='__main__':run()
