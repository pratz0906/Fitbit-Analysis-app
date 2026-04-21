import pandas as pd
import zipfile
import io
import os
import json


def load_steps_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    """Read all steps_*.csv files from the zip and return a single DataFrame."""
    frames: list[pd.DataFrame] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for entry in zf.namelist():
            basename = os.path.basename(entry)
            if (
                "Physical Activity_GoogleData" in entry
                and basename.lower().startswith("steps_")
                and basename.lower().endswith(".csv")
            ):
                with zf.open(entry) as f:
                    df = pd.read_csv(f)
                    frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], format="ISO8601", utc=True)
    combined["date"] = combined["timestamp"].dt.date

    # Google Fit exports contain multiple data sources that record
    # overlapping steps for the same timestamp (e.g. phone sensor +
    # "merge_step_deltas" derived aggregate).  Keep only the row with
    # the highest step count per timestamp to avoid double-counting.
    combined = (
        combined.sort_values("steps", ascending=False)
        .drop_duplicates(subset=["timestamp"], keep="first")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return combined


def load_distance_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    """Read all distance_*.csv files from the zip and return a single DataFrame."""
    frames: list[pd.DataFrame] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for entry in zf.namelist():
            basename = os.path.basename(entry)
            if (
                "Physical Activity_GoogleData" in entry
                and basename.lower().startswith("distance_")
                and basename.lower().endswith(".csv")
            ):
                with zf.open(entry) as f:
                    df = pd.read_csv(f)
                    frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], format="ISO8601", utc=True)
    combined["date"] = combined["timestamp"].dt.date

    # Deduplicate overlapping data sources (same logic as steps).
    combined = (
        combined.sort_values("distance", ascending=False)
        .drop_duplicates(subset=["timestamp"], keep="first")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return combined


def load_weight_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    """Read all weight-*.json files from the zip and return a single DataFrame."""
    records: list[dict] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for entry in zf.namelist():
            basename = os.path.basename(entry)
            if (
                "Global Export Data" in entry
                and basename.lower().startswith("weight-")
                and basename.lower().endswith(".json")
            ):
                with zf.open(entry) as f:
                    data = json.loads(f.read())
                    if isinstance(data, list):
                        records.extend(data)
                    elif isinstance(data, dict):
                        records.append(data)

    if not records:
        return pd.DataFrame()

    wdf = pd.DataFrame(records)
    wdf["date"] = pd.to_datetime(wdf["date"], format="%m/%d/%y")
    wdf = wdf.sort_values("date").reset_index(drop=True)

    return wdf
