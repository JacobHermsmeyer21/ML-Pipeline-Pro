import csv
import io
import json

import pytest

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.dataset_preparation import decode_labels, prepare_csv, transform_rows
from ml_pipeline_pro.datasets import DatasetValidationError
from ml_pipeline_pro.preparation_schemas import PreparationSettings


def raw_csv(count=200, *, existing=False):
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(["Age years", "Category", "Outcome", *(["partition"] if existing else [])])
    for index in range(count):
        writer.writerow(
            [
                index % 20,
                "HIGH" if index % 4 < 2 else "LOW",
                "alpha" if index % 2 == 0 else "beta",
                *(
                    ["train" if index < 140 else "validation" if index < 170 else "test"]
                    if existing
                    else []
                ),
            ]
        )
    return text.getvalue().encode()


def config(**overrides):
    return PreparationSettings(name="raw", version="v1", target_column="Outcome", **overrides)


def test_default_stratified_split_is_exact_reproducible_and_exhaustive():
    result = prepare_csv(raw_csv(), config(), Settings(_env_file=None))
    assert result.preview["row_counts"] == {"train": 140, "validation": 30, "test": 30}
    assert result.preview["class_counts"] == {
        "train": {"alpha": 70, "beta": 70},
        "validation": {"alpha": 15, "beta": 15},
        "test": {"alpha": 15, "beta": 15},
    }
    assert result.preview["encoded_width"] == 3
    assert len(list(csv.DictReader(io.StringIO(result.content.decode())))) == 200
    again = prepare_csv(raw_csv(), config(), Settings(_env_file=None))
    assert result == again
    assert (
        prepare_csv(raw_csv(), config(seed=99), Settings(_env_file=None)).content != result.content
    )


def test_user_mapping_and_target_ids_are_applied_and_reusable():
    result = prepare_csv(
        raw_csv(),
        config(
            columns={
                "Category": {
                    "treatment": "mapping",
                    "mapping": {"HIGH": 7, "LOW": -2},
                    "unknown_value": 3,
                }
            },
            label_mapping={"alpha": 1, "beta": 0},
        ),
        Settings(_env_file=None),
    )
    recipe = json.loads(result.manifest)
    assert recipe["columns"][1]["mapping"] == {"HIGH": 7, "LOW": -2}
    assert decode_labels([0, 1], recipe) == ["beta", "alpha"]
    rows = list(csv.DictReader(io.StringIO(result.content.decode())))
    assert rows[0]["feature_1"] == "7" and rows[0]["target"] == "1"
    assert rows[2]["feature_1"] == "-2"
    assert transform_rows([{"Age years": "10", "Category": "NEW"}], recipe) == [[10, 3]]
    assert result.preview["encoded_width"] == 2


def test_holdout_features_cannot_change_fitted_vocabulary_imputation_or_types():
    content = raw_csv(existing=True)
    first = prepare_csv(
        content, config(split_column="partition", impute_missing=True), Settings(_env_file=None)
    )
    text = content.decode().splitlines()
    for index in range(141, len(text)):
        parts = text[index].split(",")
        parts[0], parts[1] = "99999", "UNSEEN"
        text[index] = ",".join(parts)
    second = prepare_csv(
        "\n".join(text).encode(),
        config(split_column="partition", impute_missing=True),
        Settings(_env_file=None),
    )
    for before, after in zip(first.preview["columns"], second.preview["columns"], strict=True):
        for key in ("treatment", "categories", "mapping", "fill_value", "output_columns"):
            assert before[key] == after[key]
    assert second.preview["columns"][1]["unknown_count"] == 60
    recipe = json.loads(second.manifest)
    assert transform_rows([{"Age years": "99999", "Category": "UNSEEN"}], recipe) == [[99999, 0, 0]]


def test_missing_values_require_explicit_training_fitted_imputation():
    source = raw_csv(existing=True).replace(b"0,HIGH,alpha,train", b",,alpha,train", 1)
    with pytest.raises(DatasetValidationError, match="imputation"):
        prepare_csv(source, config(split_column="partition"), Settings(_env_file=None))
    result = prepare_csv(
        source, config(split_column="partition", impute_missing=True), Settings(_env_file=None)
    )
    assert result.preview["columns"][0]["fill_value"] == 10
    assert result.preview["columns"][1]["fill_value"] == "LOW"


@pytest.mark.parametrize(
    "overrides",
    [
        {"columns": {"Category": {"treatment": "mapping", "mapping": {"HIGH": 1}}}},
        {"label_mapping": {"alpha": 1, "beta": 1}},
        {"columns": {"Outcome": {"treatment": "one_hot"}}},
        {"columns": {"Age years": {"treatment": "exclude"}, "Category": {"treatment": "exclude"}}},
        {"columns": {"missing": {"treatment": "exclude"}}},
    ],
)
def test_invalid_user_overrides_fail_before_registration(overrides):
    with pytest.raises(DatasetValidationError):
        prepare_csv(raw_csv(), config(**overrides), Settings(_env_file=None))


def test_rare_classes_and_missing_targets_are_rejected():
    for source in [raw_csv(4), raw_csv().replace(b",alpha", b",", 1)]:
        with pytest.raises(DatasetValidationError):
            prepare_csv(source, config(), Settings(_env_file=None))


def test_csv_structure_and_expansion_guards_reach_intended_boundaries(monkeypatch):
    from ml_pipeline_pro import dataset_preparation as module

    with pytest.raises(DatasetValidationError, match="row limit"):
        prepare_csv(raw_csv(), config(), Settings(_env_file=None, dataset_max_rows=199))
    with pytest.raises(DatasetValidationError, match="raw CSV byte"):
        prepare_csv(raw_csv(), config(), Settings(_env_file=None, dataset_max_bytes=100))
    monkeypatch.setattr(module, "MATRIX_MAX_BYTES", 200 * 3 * 4)
    assert prepare_csv(raw_csv(), config(), Settings(_env_file=None)).preview["encoded_width"] == 3
    monkeypatch.setattr(module, "MATRIX_MAX_BYTES", 200 * 3 * 4 - 1)
    with pytest.raises(DatasetValidationError, match="memory limit"):
        prepare_csv(raw_csv(), config(), Settings(_env_file=None))


def test_large_vocabulary_is_rejected_before_dense_allocation():
    source = "Age years,Category,Outcome\n" + "\n".join(f"{i},value{i},{i % 2}" for i in range(400))
    with pytest.raises(DatasetValidationError, match="128 features"):
        prepare_csv(source.encode(), config(), Settings(_env_file=None))


def test_encoded_csv_and_manifest_exact_caps_and_deadline(monkeypatch):
    from ml_pipeline_pro import dataset_preparation as module

    source = raw_csv()
    result = prepare_csv(source, config(), Settings(_env_file=None))
    exact = len(result.content)
    assert exact > len(source)
    assert (
        prepare_csv(source, config(), Settings(_env_file=None, dataset_max_bytes=exact)).content
        == result.content
    )
    with pytest.raises(DatasetValidationError, match="output byte limit"):
        prepare_csv(source, config(), Settings(_env_file=None, dataset_max_bytes=exact - 1))
    monkeypatch.setattr(module, "MANIFEST_MAX_BYTES", len(result.manifest))
    assert prepare_csv(source, config(), Settings(_env_file=None)).manifest == result.manifest
    monkeypatch.setattr(module, "MANIFEST_MAX_BYTES", len(result.manifest) - 1)
    with pytest.raises(DatasetValidationError, match="metadata exceeds"):
        prepare_csv(source, config(), Settings(_env_file=None))
    with pytest.raises(TimeoutError, match="time budget"):
        prepare_csv(source, config(), Settings(_env_file=None), deadline=0)


def test_exact_encoded_feature_cap_and_one_over():
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow([*(f"number{i}" for i in range(127)), "Category", "Outcome", "partition"])
    for split in ("train", "validation", "test"):
        for label in ("alpha", "beta"):
            writer.writerow([*range(127), "only", label, split])
    source = text.getvalue().encode()
    result = prepare_csv(source, config(split_column="partition"), Settings(_env_file=None))
    assert result.preview["encoded_width"] == 128
    changed = source.replace(b"only,beta", b"other,beta")
    with pytest.raises(DatasetValidationError, match="128 features"):
        prepare_csv(changed, config(split_column="partition"), Settings(_env_file=None))
