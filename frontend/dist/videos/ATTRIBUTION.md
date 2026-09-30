# Real traffic samples

These original, unmodified clips are redistributed from **Intel IoT DevKit, sample-videos** under **Creative Commons Attribution 4.0 International (CC BY 4.0)**.

Attribution: Intel Corporation / Intel IoT DevKit contributors, *Sample videos for running inference*. No endorsement is implied. Retrieved 30 September 2026.

| File | Original source | SHA-256 |
|---|---|---|
| `car-detection.mp4` | [Intel source](https://github.com/intel-iot-devkit/sample-videos/blob/master/car-detection.mp4) | `d31e0ebf194cc16e50eea784e7c3b0b1bb7976a4fb9b3fec26cb92a6704cca34` |
| `person-bicycle-car-detection.mp4` | [Intel source](https://github.com/intel-iot-devkit/sample-videos/blob/master/person-bicycle-car-detection.mp4) | `452b11b7e0efbd019f1d9570d0c790e90416ad4ad29eec6003872d08443140ef` |

[Upstream repository](https://github.com/intel-iot-devkit/sample-videos) · [Upstream licence](https://github.com/intel-iot-devkit/sample-videos/blob/master/LICENSE) · [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/) · full licence included in `LICENSE-CC-BY-4.0.txt`.

These clips are suited to **vehicle detection, tracking and density tests**. Plates are generally too small to read. Evaluate OCR on separately obtained, lawfully collected footage with legible plates, ground truth, and representative Indian road conditions. These files are not an Indian ANPR benchmark. Unreadable tracks are posted as anonymous traffic observations, never invented plate strings.

From the project root, with optional dependencies and local YOLO weights installed:

```sh
python -m tools.process_video samples/car-detection.mp4 --camera C04 --vehicle-model models/yolo11n.pt --detect-only --output-video output/annotated.mp4
```

All processing is local. The tool sends events only to the API URL you provide (localhost by default). The optional model files are not included.
