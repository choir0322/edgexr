# Local detector assets

The first detector uses [chuanqi305/MobileNet-SSD](https://github.com/chuanqi305/MobileNet-SSD)
at commit `bb17b6c3eef36d80be441ae8e5339be66e8e3b7a`:

- `mobilenet-ssd/deploy.prototxt`: network definition.
- `mobilenet-ssd/mobilenet_iter_73000.caffemodel`: learned weights, about 23 MB.
- `mobilenet-ssd/LICENSE`: upstream MIT license; retain with the files.

See docs/DETECTION_BASELINE.md for explicit download steps. Model assets are
ignored by Git and are not downloaded by the detector. Each result records
SHA-256 hashes of both model files. A Git-pinned URL identifies the source;
the recorded hashes identify the bytes actually used, not a signature check.

This is the VOC 20-class model, not a COCO model. It cannot label cups, phones
or keyboards. Use visible people, chairs, bottles or monitors for initial checks.
The upstream demo documents BGR, direct 300x300 resize and normalization.
