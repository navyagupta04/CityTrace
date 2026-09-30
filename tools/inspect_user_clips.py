import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import cv2,json,numpy as np
cv2.setNumThreads(1)
sources=[('vehicle-a',Path(r'D:/final/ibvap/test_videos/vehicle.mp4')),('vehicle-b',Path(r'C:/Users/Navya gupta/OneDrive/Desktop/WhatsApp Video 2026-10-01 at 1.21.12 AM.mp4'))]
out=Path('output/user-case');out.mkdir(parents=True,exist_ok=True)
for name,path in sources:
 cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));w=int(cap.get(3));h=int(cap.get(4))
 print(json.dumps({'id':name,'fps':fps,'frames':n,'width':w,'height':h,'seconds':n/fps}),flush=True)
 tiles=[]
 for i,t in enumerate(np.linspace(0,max(0,n/fps-.15),8)):
  cap.set(cv2.CAP_PROP_POS_MSEC,float(t)*1000);ok,img=cap.read()
  if not ok:continue
  cv2.imwrite(str(out/f'{name}-{i}.jpg'),img)
  factor=min(480/w,300/h);thumb=cv2.resize(img,(int(w*factor),int(h*factor)));tile=np.full((330,480,3),25,dtype=np.uint8);tile[:thumb.shape[0],:thumb.shape[1]]=thumb;cv2.putText(tile,f'{name}: {t:.2f}s / frame {round(t*fps)}',(10,320),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);tiles.append(tile)
 cap.release()
 while len(tiles)%4:tiles.append(np.zeros_like(tiles[0]))
 cv2.imwrite(str(out/f'{name}-sheet.jpg'),np.concatenate([np.concatenate(tiles[i:i+4],axis=1) for i in range(0,len(tiles),4)],axis=0))
