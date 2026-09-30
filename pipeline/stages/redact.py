"""Conservative viewer preview: whole-frame blur since plate detection can miss."""
import subprocess
from ..common import ROOT
def preview(clip,cfg):
    import imageio_ffmpeg
    out=ROOT/cfg['output']/'videos'/f"{clip['id']}-redacted.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(ROOT/clip['file']),'-an','-vf','scale=48:-2:flags=area,scale=768:-2:flags=neighbor','-c:v','libx264','-pix_fmt','yuv420p',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return 'videos/'+out.name
