# Saved-frame detector baseline — 2026-10-05

Inspected Desktop copies of detection-01/report.json and annotated.png, plus
the user's Pi terminal output. Pi 4, Linux 6.12.47+rpt-rpi-v8 aarch64, Python
3.11.2, OpenCV 4.11.0, NumPy 1.26.4. Git 0152508a94a40001a9d800c0734f5a0e8c92a628,
clean. Camera image 1280x720 grayscale from combined-motion-03 at file time 2 s.
Dining scene, visible chairs/table; lighting, power and cooling unspecified.

MobileNet-SSD VOC, CPU/OpenCV backend, two threads, threshold 0.5, direct 300x300
resize and replicated grayscale. Three warm-ups and twenty measured runs on
the same image; model loading separate (172.13 ms).

| Stage | Median ms | Nearest-rank p95 ms |
| --- | ---: | ---: |
| Preprocessing | 6.05 | 6.19 |
| Inference including setInput | 188.42 | 190.00 |
| Box processing | 1.41 | 1.50 |
| Total per-run compute | 195.90 | 197.46 |

CPU temperature readings before/after: 45.764/48.686 C. This short run does not
establish sustained thermal behavior. Times exclude disk, drawing, camera and
display. Reciprocal median compute is about 5.1/s in isolation; it is not a
measured live frame rate. Median component times need not sum to median total.

The table (score .9988) and left chair (.9432) have plausible boxes. The clearly
visible right chair was missed. This is useful first recognition on monochrome
footage, not an accuracy benchmark. Scores are model confidence, not accuracy.
The Pi ran all 44 unit tests successfully, including OpenCV preprocessing and
loopback HTTP tests that were unavailable in the local development sandbox.

Artifact SHA-256 identities:

- Image: a819dca6754e7bfdad717ca4cae216ff392289194b574aa5a6cffe70f4941f7f
- Prototxt: 2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608
- Weights: 52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7

Next: optional live detection at a target 2 Hz, measuring contention with
camera motion and IMU. See LIVE_DETECTION.md. Keep raw images/reports local.
