"""SRVGGNetCompact, vendored from Real-ESRGAN (BSD-3-Clause, xinntao/Real-ESRGAN
realesrgan/archs/srvgg_arch.py) without the basicsr registry dependency.

realesr-general-x4v3 = SRVGGNetCompact(num_feat=64, num_conv=32, upscale=4, prelu).
"""
import torch
from torch import nn
from torch.nn import functional as F


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        body = [nn.Conv2d(num_in_ch, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        for _ in range(num_conv):
            body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")


class PReLUMinMax(nn.Module):
    """PReLU as max(x,0) + a*min(x,0): MAXIMUM/MINIMUM/MUL/ADD instead of GREATER/SELECT."""

    def __init__(self, prelu):
        super().__init__()
        self.weight = nn.Parameter(prelu.weight.detach().view(1, -1, 1, 1))

    def forward(self, x):
        return torch.clamp_min(x, 0) + self.weight * torch.clamp_max(x, 0)


class Body(nn.Module):
    """Conv/PReLU stack only: returns the pre-PixelShuffle 48-channel map.
    PixelShuffle + nearest-upsample residual run in the native post-process."""

    def __init__(self, net):
        super().__init__()
        self.body = nn.ModuleList(PReLUMinMax(m) if isinstance(m, nn.PReLU) else m for m in net.body)

    def forward(self, x):
        for layer in self.body:
            x = layer(x)
        return x


def body_postprocess(feat_nhwc, inp_nhwc, scale=4):
    """Reference for the native post-process: (N,H,W,3*s*s) + (N,H,W,3) -> (N,sH,sW,3)."""
    n, h, w, _ = feat_nhwc.shape
    out = feat_nhwc.reshape(n, h, w, 3, scale, scale).transpose(0, 1, 4, 2, 5, 3).reshape(n, h * scale, w * scale, 3)
    return out + inp_nhwc.repeat(scale, axis=1).repeat(scale, axis=2)


class NHWC(nn.Module):
    """NHWC in/out wrapper so the converter can fold the layout transposes."""

    def __init__(self, net):
        super().__init__()
        self.net = net

    def forward(self, x):
        return self.net(x.permute(0, 3, 1, 2)).permute(0, 2, 3, 1)


def load_x4v3(path):
    net = SRVGGNetCompact()
    state = torch.load(path, map_location="cpu", weights_only=True)
    net.load_state_dict(state.get("params_ema", state.get("params", state)))
    return net.eval()
