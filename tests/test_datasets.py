import pytest

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.schemas import DatasetCreate


def load_csv(tmp_path, text, **settings):
    (tmp_path / "data.csv").write_text(text, encoding="utf-8")
    definition = DatasetCreate(name="data", version="v1", uri="data.csv", feature_columns=["x"])
    return load_dataset(definition, Settings(_env_file=None, dataset_root=tmp_path, **settings))


VALID = "x,target,split\n-1,0,train\n1,1,train\n0,0,validation\n2,1,test\n"


def test_explicit_splits_are_preserved(tmp_path):
    loaded = load_csv(tmp_path, VALID)
    assert loaded.splits["train"].features == [[-1], [1]]
    assert loaded.splits["validation"].targets == [0]
    assert loaded.splits["test"].targets == [1]
    assert loaded.num_classes == 2


@pytest.mark.parametrize(
    "csv_text",
    [
        VALID.replace("x,target,split", "missing,target,split"),
        VALID.replace("-1,0,train", "nan,0,train"),
        VALID.replace("-1,0,train", "inf,0,train"),
        VALID.replace("-1,0,train", "secret,0,train"),
        VALID.replace("-1,0,train", "-1,0.5,train"),
        VALID.replace("2,1,test", "2,1,unknown"),
        VALID.replace("2,1,test\n", ""),
        VALID.replace("0,0,validation", "0,2,validation"),
        VALID.replace("1,1,train", "1,2,train"),
        VALID.replace("1,1,train\n", ""),
        VALID.replace("-1,0,train", "-1,0,train,extra"),
    ],
)
def test_invalid_csv_is_rejected(tmp_path, csv_text):
    with pytest.raises(DatasetValidationError):
        load_csv(tmp_path, csv_text)


def test_file_and_row_limits_are_enforced(tmp_path):
    with pytest.raises(DatasetValidationError, match="file size"):
        load_csv(tmp_path, VALID, dataset_max_bytes=5)
    with pytest.raises(DatasetValidationError, match="row limit"):
        load_csv(tmp_path, VALID, dataset_max_rows=3)
