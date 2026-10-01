"""Prepare the first five supplied files in filename order; never fetch footage."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
import cv2
import imageio_ffmpeg
from pipeline.common import ROOT, digest


def prepare(paths):
    dest = ROOT/'frontend/public/videos/live'
    dest.mkdir(parents=True,exist_ok=True)
    feeds=[]
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    for i,path in enumerate(sorted(map(Path,paths),key=lambda p:p.name.lower())[:5]):
        cap=cv2.VideoCapture(str(path))
        width,height=map(int,(cap.get(cv2.CAP_PROP_FRAME_WIDTH),cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        fourcc=int(cap.get(cv2.CAP_PROP_FOURCC))
        codec=''.join(chr((fourcc>>(8*k))&255) for k in range(4))
        cap.release()
        if not width or not height:
            raise ValueError(f'Cannot decode {path.name}')
        target=dest/(path.stem+'.mp4')
        command=[ffmpeg,'-y','-i',str(path),'-map','0:v:0','-an']
        if codec in ('avc1','h264') and height<=720:
            command+=['-c:v','copy']
        else:
            command+=['-vf',"scale=-2:'min(720,ih)'",'-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p']
        subprocess.run(command+['-movflags','+faststart',str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        cap=cv2.VideoCapture(str(target));fps=cap.get(cv2.CAP_PROP_FPS)
        feeds.append(dict(id=f'live-{i+1}',file='/videos/live/'+target.name,title=path.stem,
                          camera_id=f'C{i+1:02}',duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps,
                          width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),fps=fps,
                          sha256=digest(target),source_sha256=digest(path)))
        cap.release()
        print(f"Prepared {target.name} ({feeds[-1]['duration']:.2f}s)",flush=True)
    config=ROOT/'frontend/src/real/liveFeeds.config.ts'
    config.write_text('export interface LiveFeed {id:string;file:string;title:string;camera_id:string;duration:number;width:number;height:number;fps:number;sha256:string;source_sha256:string}\nexport const liveFeeds: LiveFeed[] = '+json.dumps(feeds,indent=2)+';\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('files',nargs='+');args=parser.parse_args();prepare(args.files)
