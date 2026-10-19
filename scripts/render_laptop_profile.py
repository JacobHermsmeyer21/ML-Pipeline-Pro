"""Render the approved laptop gateway and Kubernetes manifest without deployment."""

import argparse
from pathlib import Path

from ml_pipeline_pro.laptop_deployment import render_laptop_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/laptop-five-minute"))
    args = parser.parse_args()
    print(render_laptop_profile(Path(__file__).resolve().parents[1], args.output))


if __name__ == "__main__":
    main()
