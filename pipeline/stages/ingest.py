from pathlib import Path
import shutil
import subprocess
from ..common import ROOT, digest, expiry

def ingest(placement, cfg):
    import cv2
    path=ROOT/placement['file']
    if not path.is_file(): raise FileNotFoundError(f'Missing local video: {path}')
    capture=cv2.VideoCapture(str(path))
    fps=capture.get(cv2.CAP_PROP_FPS); count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)); height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    codec=int(capture.get(cv2.CAP_PROP_FOURCC)); fourcc=''.join(chr((codec>>(8*i))&255) for i in range(4));capture.release()
    if fps<=0 or count<=0 or width<=0: raise ValueError(f'Unreadable video: {path}')
    target=ROOT/cfg['output']/'videos'/f"{placement['id']}.mp4";target.parent.mkdir(parents=True,exist_ok=True)
    if fourcc.lower() in ('avc1','h264'): shutil.copyfile(path,target)
    else:
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(path),'-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return {**placement,'video':f"videos/{placement['id']}.mp4",'fps':fps,'width':width,'height':height,'frame_count':count,'duration_s':count/fps,'sha256':digest(path),'preview_sha256':digest(target),'codec':fourcc,'source':'real','expires_at':expiry(cfg['privacy_settings']['raw_preview_days'])}
