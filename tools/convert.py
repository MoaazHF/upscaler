"""Convert realesr-general-x4v3 to fixed-shape NHWC .tflite in fp32 / fp16-weights / int8-dynamic.

usage: python -I tools/convert.py models/realesr-general-x4v3.pth --tiles 128 256 --out models/
"""
import argparse
import pathlib
import sys

import torch

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from srvgg import NHWC, Body, load_x4v3  # noqa: E402

import litert_torch  # noqa: E402
from ai_edge_quantizer import quantizer, recipe, recipe_manager  # noqa: E402

ALL = recipe.TFLOperationName.ALL_SUPPORTED


def fp16_recipe():
    rm = recipe_manager.RecipeManager()
    rm.add_weight_only_config(regex=".*", operation_name=ALL, num_bits=16,
                              algorithm_key=recipe.AlgorithmName.FLOAT_CASTING)
    return rm.get_quantization_recipe()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weights")
    ap.add_argument("--tiles", type=int, nargs="+", default=[128, 256])
    ap.add_argument("--out", default="models")
    ap.add_argument("--variant", choices=["full", "body"], default="full",
                    help="body = conv/PReLU only; PixelShuffle + residual done natively")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    net = load_x4v3(a.weights)
    model = NHWC(Body(net) if a.variant == "body" else net).eval()
    tag = "x4v3" if a.variant == "full" else "x4v3body"
    for t in a.tiles:
        fp32 = out / f"{tag}_t{t}_fp32.tflite"
        litert_torch.convert(model, (torch.rand(1, t, t, 3),)).export(str(fp32))
        for name, rcp in (("fp16w", fp16_recipe()), ("int8dyn", recipe.dynamic_wi8_afp32())):
            q = quantizer.Quantizer(str(fp32), rcp)
            q.quantize().export_model(str(out / f"{tag}_t{t}_{name}.tflite"), overwrite=True)
        print("tile", t, "done")


if __name__ == "__main__":
    main()
