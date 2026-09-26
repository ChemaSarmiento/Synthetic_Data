"""Small validation utilities shared by domain validators."""

import pyarrow.parquet as pq


def require(condition, message):
    if not condition:
        raise ValueError(f"Validation failed: {message}")


def read(path):
    return pq.ParquetFile(path).read()


def values(table, name):
    return table[name].combine_chunks().to_numpy(zero_copy_only=False)
