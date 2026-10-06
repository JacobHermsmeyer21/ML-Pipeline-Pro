"""Generate a deterministic synthetic binary classification CSV using only Python."""

import csv
import random
from pathlib import Path


def make_dataset(destination: Path) -> None:
    rng = random.Random(42)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["feature_1", "feature_2", "target", "split"])
        for split, count in (("train", 80), ("validation", 20), ("test", 20)):
            for index in range(count):
                label = index % 2
                center = -1.5 if label == 0 else 1.5
                writer.writerow(
                    [f"{rng.gauss(center, 0.5):.6f}", f"{rng.gauss(center, 0.5):.6f}", label, split]
                )


if __name__ == "__main__":
    make_dataset(Path(__file__).parent / "data" / "classification.csv")
