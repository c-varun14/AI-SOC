"""Export the EfficientNetV2-S candidate to a separate ExecuTorch/XNNPACK file."""

import argparse
import os
from pathlib import Path
import sys

import torch
import torch.nn as nn

# On Windows, point ExecuTorch to the flatc.exe bundled in this environment.
bundled_flatc = (
    Path(sys.prefix)
    / "Lib"
    / "site-packages"
    / "executorch"
    / "data"
    / "bin"
    / "flatc.exe"
)
if bundled_flatc.is_file():
    os.environ["FLATC_EXECUTABLE"] = str(bundled_flatc)

from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
from executorch.exir import to_edge_transform_and_lower
from torchvision.models import efficientnet_v2_s


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    device = torch.device("cpu")
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    sample_input = torch.load(args.sample, map_location=device, weights_only=True)
    expected_shape = (1, 3, checkpoint["image_size"], checkpoint["image_size"])
    if tuple(sample_input.shape) != expected_shape:
        raise ValueError(f"Expected input shape {expected_shape}; got {tuple(sample_input.shape)}")

    model = efficientnet_v2_s(weights=None)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 2)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()

    with torch.no_grad():
        pytorch_output = model(sample_input)
        exported_program = torch.export.export(model, (sample_input,))
        executorch_program = to_edge_transform_and_lower(
            exported_program,
            partitioner=[XnnpackPartitioner()],
        ).to_executorch()

    with args.output.open("xb") as output_file:
        output_file.write(executorch_program.buffer)

    print("ExecuTorch export succeeded.")
    print("Model: EfficientNetV2-S Experiment 2")
    print("Input shape:", tuple(sample_input.shape))
    print("PyTorch output logits:", pytorch_output[0].tolist())
    print("Saved separate XNNPACK model:", args.output)
    print("The baseline checkpoint and baseline .pte file were not changed.")


if __name__ == "__main__":
    main()
