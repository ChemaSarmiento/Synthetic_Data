import importlib.util
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from synthetic_engine.outputs.parquet import sha256

spec = importlib.util.spec_from_file_location("sample_ibm", Path(__file__).parents[1] / "scripts/sample_ibm.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_weighted_sample_is_reproducible_and_preserves_rare_formats(tmp_path):
    source = tmp_path / "source.csv"
    lines = ["Timestamp,Payment Currency,Payment Format,Amount Paid,Is Laundering"]
    for group, count in [("common", 100), ("rare", 10)]:
        lines.extend(f"2022/09/01 10:00,USD,{group},{i},0" for i in range(count))
    source.write_text("\n".join(lines) + "\n")
    metadata = dict(id="fixture", sha256=sha256(source), observed_statistics=dict(payment_format_counts=dict(common=100, rare=10)))
    first = module.sample(source, metadata, tmp_path / "a", rows=10)
    second = module.sample(source, metadata, tmp_path / "b", rows=10)
    assert first == second
    table = pq.read_table(tmp_path / "a/sample.parquet").to_pydict()
    assert len(set(table["source_row_index"])) == 10
    assert table["Payment Format"].count("rare") == 5
    assert sum(table["sampling_weight"]) == 110
    with pytest.raises(FileExistsError):
        module.sample(source, metadata, tmp_path / "a", rows=10)
    metadata["sha256"] = "wrong"
    with pytest.raises(ValueError, match="registered source"):
        module.sample(source, metadata, tmp_path / "c", rows=10)
