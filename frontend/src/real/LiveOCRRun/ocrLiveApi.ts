import { getOCRToken } from './localSession';
import { getToken } from '../../api';
const env=(import.meta as ImportMeta & {env:Record<string,string>}).env;
const base=(env.VITE_OCR_API_BASE||env.VITE_API_BASE_URL||'/api').replace(/\/$/,'');
export class OCRLiveError extends Error {constructor(message:string,public status=0){super(message);this.name='OCRLiveError';}}
export async function ocrRequest<T>(path:string,body?:FormData|object,method?:string,signal?:AbortSignal):Promise<T>{
 try {
  const response=await fetch(`${base}/ocr/${path}`,{method:method||(body?'POST':'GET'),signal,credentials:'include',headers:{...(body instanceof FormData?{}:{'Content-Type':'application/json'}),Authorization:`Bearer ${(getOCRToken()||getToken())}`},body:body instanceof FormData?body:body?JSON.stringify(body):undefined});
  const data=await response.json();
  if(!response.ok)throw new OCRLiveError(typeof data.detail==='string'?data.detail:'OCR request failed',response.status);
  return data as T;
 }catch(error){if(error instanceof OCRLiveError)throw error;throw new OCRLiveError(error instanceof Error?error.message:'Local OCR service unavailable');}
}
export interface EngineStatus {available:boolean;engine:string;engine_version:string;device:string;reasons_if_unavailable:string[];setup:string;limits:{max_seconds:number;max_files:number;image_mb:number;video_mb:number}}
export interface PlateResult {track_id:number|null;box:number[]|null;raw:string;normalised:string;voted:string|null;format_valid:boolean;format:string;ocr_confidence:number;vote_confidence:number;n_reads:number;status:string;reason?:string;expected?:string;exact_match?:boolean|null;cer?:number|null;time_s?:number;label_key?:string;scored?:boolean;first_time_s?:number|null;first_frame?:number;last_frame?:number;character_confidences?:{character:string;confidence:number}[];plate_detection_confidence?:number|null;detection_confidence_source?:string;confidence_threshold?:number;low_confidence?:boolean;confidence_basis?:string;crop_image?:string|null}
export interface FileResult {file:string;sha256:string;type:string;mode_used:string;duration_ms:number;status:string;error?:string;plates:PlateResult[];tracks:PlateResult[];video_fps?:number;stage_ms?:Record<string,number>;annotated_image?:string|null;image_width?:number;image_height?:number}
export interface Accuracy {value:number;n:number;ci95:number[];correct:number}
export interface Metrics {n_scored:number;blind:boolean;verdict:string;plate_accuracy_all:Accuracy|null;cer:number|null;coverage:number|null;selective_accuracy:Accuracy|null;coverage_curve:{threshold:number;coverage:number;accuracy:number|null}[];reliability:{bin:string;n:number;confidence:number;accuracy:number}[];error_cases:{clip_id:string;track_id:number;expected:string;predicted:string;category:string}[]}
export interface OCRJob {job_id:string;state:string;stage:string;progress:number;files:FileResult[];metrics:Metrics|{scored:false};scored?:boolean;engine:string;engine_version:string;device:string;duration_ms:number;error?:string;purged:boolean}
