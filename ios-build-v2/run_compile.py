from pathlib import Path
import json,os,subprocess
b=Path(__file__).resolve().parent
e=os.environ.copy();e['PKG_CONFIG_LIBDIR']=str(b/'pkgconfig');e['PKG_CONFIG_PATH']=''
with (b/'configure.log').open('w') as f:r=subprocess.run(json.loads((b/'configure-command.json').read_text()),cwd=b/'ffmpeg-7.0.2',env=e,stdout=f,stderr=subprocess.STDOUT)
print('configure exit',r.returncode,flush=True);print((b/'configure.log').read_text()[-1800:],flush=True)
if r.returncode==0:
 with (b/'compile.log').open('w') as f:r=subprocess.run(['make','-j6','libavcodec/libavcodec.a'],cwd=b/'ffmpeg-7.0.2',stdout=f,stderr=subprocess.STDOUT)
 print('compile exit',r.returncode);print((b/'compile.log').read_text()[-2400:])

raise SystemExit(r.returncode)
