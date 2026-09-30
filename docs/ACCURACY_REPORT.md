# Real-footage accuracy report

Not measured: no ground-truth labels. The 90% target has not been demonstrated.

Processed 2 licensed clips (84.08 seconds). YOLOX and ByteTrack produced 4 tracks. These are unvalidated model tracks, not a ground-truth vehicle count. Runtime for this invocation: 624.66 seconds (cached stages may be reused).

No plate detector/OCR weights are configured; every track abstains. No accuracy, coverage, CER or confidence interval is asserted. Obtain consented readable-plate footage, label tracks blindly, split by video, tune on dev and freeze before evaluating test once.

Eligibility: human-readable plate, best plate height ≥ 25 px. All-tracks accuracy also counts unreadable tracks and abstentions as incorrect. Wilson 95% intervals accompany measured values; small N is inadequate for a reliable target claim.

Models: {"onnxruntime": "1.30.0", "supervision": "0.25.1", "opencv-python": "4.11.0.86", "detector": "OpenCV Zoo YOLOX", "inference_backend": "OpenCV DNN CPU", "weights_sha256": "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063", "plate_ocr": "Not configured"}

Config hash: 78a3ba30fe2c200dd0c3f61735b1113a49ef119f19cbfb988f41b9b7bf878567
