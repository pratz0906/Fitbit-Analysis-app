"""Diagnose which CSV files and data sources cause duplicate step counts."""
import sys
import zipfile
import io
import os
import pandas as pd

def diagnose(zip_path: str):
    with open(zip_path, "rb") as f:
        raw = f.read()

    frames = []
    file_info = []

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for entry in zf.namelist():
            basename = os.path.basename(entry)
            if (
                "Physical Activity_GoogleData" in entry
                and basename.lower().startswith("steps_")
                and basename.lower().endswith(".csv")
            ):
                with zf.open(entry) as f:
                    df = pd.read_csv(f)
                    df["_source_file"] = basename
                    frames.append(df)
                    file_info.append((basename, len(df)))

    if not frames:
        print("No steps CSV files found.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], format="ISO8601", utc=True)

    print("=" * 70)
    print("CSV FILES FOUND")
    print("=" * 70)
    for name, count in file_info:
        print(f"  {name}: {count:,} rows")
    print(f"\n  Total rows (all files): {len(combined):,}")

    print("\n" + "=" * 70)
    print("DATA SOURCES IN CSV")
    print("=" * 70)
    for src, grp in combined.groupby("data source"):
        print(f"  {src}")
        print(f"    Rows: {len(grp):,}")
        print(f"    Date range: {grp['timestamp'].min().date()} to {grp['timestamp'].max().date()}")
        print(f"    Total steps: {grp['steps'].sum():,.0f}")
        files = grp["_source_file"].unique()
        print(f"    Found in: {', '.join(files)}")
        print()

    print("=" * 70)
    print("DUPLICATE TIMESTAMP ANALYSIS")
    print("=" * 70)
    dup_mask = combined.duplicated(subset=["timestamp"], keep=False)
    dups = combined[dup_mask]
    print(f"  Unique timestamps: {combined['timestamp'].nunique():,}")
    print(f"  Total rows: {len(combined):,}")
    print(f"  Rows with duplicate timestamps: {len(dups):,}")
    print(f"  Extra rows (double-counted): {len(dups) - dups['timestamp'].nunique():,}")

    if not dups.empty:
        dup_steps_by_source = dups.groupby("data source")["steps"].sum()
        print(f"\n  Steps in duplicate rows by source:")
        for src, steps in dup_steps_by_source.items():
            print(f"    {src}: {steps:,.0f}")

        print(f"\n  Sample duplicates (first 10 timestamps):")
        sample_ts = dups["timestamp"].unique()[:10]
        for ts in sample_ts:
            rows = combined[combined["timestamp"] == ts]
            print(f"\n  Timestamp: {ts}")
            for _, row in rows.iterrows():
                print(f"    source={row['data source']!r}  steps={row['steps']}  file={row['_source_file']}")

    # Show impact
    print("\n" + "=" * 70)
    print("IMPACT ON TOTAL STEPS")
    print("=" * 70)
    raw_total = combined.groupby("timestamp")["steps"].sum().sum()
    deduped = (
        combined.sort_values("steps", ascending=False)
        .drop_duplicates(subset=["timestamp"], keep="first")
    )
    deduped_total = deduped["steps"].sum()
    print(f"  Without dedup (sum all rows): {raw_total:,.0f}")
    print(f"  With dedup (one per timestamp): {deduped_total:,.0f}")
    print(f"  Overcounted by: {raw_total - deduped_total:,.0f} ({(raw_total - deduped_total) / deduped_total * 100:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_duplicates.py <path_to_zip>")
        sys.exit(1)
    diagnose(sys.argv[1])
