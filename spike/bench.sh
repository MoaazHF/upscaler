#!/bin/sh
# Phase 0.5 spike: on-device LiteRT benchmark (run via adb shell from /data/local/tmp/upscaler).
# benchmark_model: https://storage.googleapis.com/litert/binaries/2.3.0/android_arm64/benchmark_model
# sha256 844d518d490a42e73472477f9f793605d24ed95c77c9ab55d55614dc68d52b7a
cd /data/local/tmp/upscaler || exit 1
for t in 128 192 256 384 512; do
  st=$(dumpsys thermalservice | grep -m1 "Thermal Status" | sed "s/.*: //")
  r=$(./benchmark_model --graph=x4v3body_t${t}_fp32.tflite --use_gpu=true --gpu-precision=fp16 --max_secs=10 2>&1)
  echo "t$t thermal=$st | $(echo "$r" | grep -E "Inference \(avg\)|Model initialization|Overall footprint" | tr '\n' '|')"
  sleep 20
done
