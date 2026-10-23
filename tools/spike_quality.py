"""Phase 0.5 spike: PSNR of each .tflite vs the PyTorch fp32 model on 128px tiles (CPU).

usage: python -I tools/spike_quality.py models/realesr-general-x4v3.pth testset/kodak/*.png
"""
import pathlib
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from srvgg import body_postprocess, load_x4v3  # noqa: E402

from ai_edge_litert.interpreter import Interpreter  # noqa: E402

T = 128
MODELS = ["x4v3_t128_fp32", "x4v3_t128_fp16w", "x4v3_t128_int8dyn",
          "x4v3body_t128_fp32", "x4v3body_t128_fp16w", "x4v3body_t128_int8dyn"]


def tiles(img):
    h, w, _ = img.shape
    for y in range(0, h - T + 1, T * 2):
        for x in range(0, w - T + 1, T * 2):
            yield img[y:y + T, x:x + T]


def psnr(a, b):
    mse = np.mean((np.clip(a, 0, 1) - np.clip(b, 0, 1)) ** 2)
    return float("inf") if mse == 0 else 10 * np.log10(1 / mse)


def main():
    net = load_x4v3(sys.argv[1])
    runners = {}
    for name in MODELS:
        it = Interpreter(model_path=f"models/{name}.tflite", num_threads=8)
        it.allocate_tensors()
        runners[name] = it
    scores = {n: [] for n in MODELS}
    for path in sys.argv[2:]:
        img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255
        for tile in tiles(img):
            x = tile[None]
            with torch.no_grad():
                ref = net(torch.from_numpy(x).permute(0, 3, 1, 2)).permute(0, 2, 3, 1).numpy()
            for name, it in runners.items():
                it.set_tensor(it.get_input_details()[0]["index"], x)
                it.invoke()
                y = it.get_tensor(it.get_output_details()[0]["index"])
                if "body" in name:
                    y = body_postprocess(y, x)
                scores[name].append(psnr(y, ref))
    for name, s in scores.items():
        print(f"{name:24s} tiles={len(s):3d} PSNR min={min(s):6.2f} mean={np.mean(s):6.2f} dB")


if __name__ == "__main__":
    main()
