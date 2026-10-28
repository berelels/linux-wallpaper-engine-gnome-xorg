#!/usr/bin/env python3
"""Retest red/yellow browser entries in small windows; preserve browser ratings."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from wallpaper_content import prepare_arguments
from capture_x11 import capture_window


def check(item, backend, assets, output, seconds):
    path, old = item
    name = Path(path).name
    report = {'path': path, 'previous': old.get('compatibility')}
    process = None
    try:
        arguments = prepare_arguments(['--window','100x100x640x360','--bg',path,'--silent','--fps','10','--assets-dir',assets])
        with (output / (name + '.log')).open('w') as log:
            process = subprocess.Popen([backend,*arguments], stdout=log, stderr=log, start_new_session=True,
                env=dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"))
            report['window'] = False
            report['nonblank_frame'] = False
            report['frame_changes'] = 0
            previous = None
            deadline = time.monotonic() + seconds
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    rows=subprocess.check_output(['wmctrl','-lp'],text=True,stderr=subprocess.DEVNULL).splitlines()
                except subprocess.CalledProcessError:
                    time.sleep(0.2)
                    continue
                for line in rows:
                    fields=line.split()
                    if len(fields)>2 and fields[2]==str(process.pid):
                        try:
                            frame=capture_window(int(fields[0],16)).convert('RGB')
                        except (RuntimeError, OSError):
                            # X11 may list a window before its backing pixmap exists.
                            continue
                        report['window']=True
                        signature=frame.resize((32,32)).tobytes()
                        if previous is not None and signature != previous:
                            report['frame_changes'] += 1
                        previous=signature
                        nonblank=any(high>low for low,high in frame.getextrema())
                        if nonblank:
                            report['nonblank_frame']=True
                            frame.save(output / (name+'.png'))
                        break
                time.sleep(0.5)
            report['exit_code'] = process.poll()
    except Exception as exc:
        report['error']=str(exc)
    finally:
        if process:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
    logpath=output/(name+'.log')
    if logpath.exists():
        lines=logpath.read_text(errors='replace').splitlines()
        report['diagnostics']=list(dict.fromkeys(line for line in lines if re.search(r'warning|error|unsupported|not supported|exception|failed',line,re.I)))[:30]
    print(name, 'renders' if report.get('nonblank_frame') else 'needs attention',flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',required=True);p.add_argument('--assets',required=True)
    p.add_argument('--ratings',type=Path,default=Path.home()/'.config/Linux Wallpaper Engine/wallpaper-overrides.json')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=8)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    items=[(path,data) for path,data in json.loads(args.ratings.read_text())['overrides'].items() if data.get('compatibility') in ('broken','minor')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports=list(pool.map(lambda item:check(item,args.backend,args.assets,args.output,args.seconds),items))
    (args.output/'results.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(f'{sum(bool(r.get("nonblank_frame")) for r in reports)}/{len(reports)} produced nonblank frames; see results.json for diagnostics')


if __name__=='__main__':main()
