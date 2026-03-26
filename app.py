import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import zipfile
import io
import os
import json

st.set_page_config(
    page_title="Fitbit Dashboard",
    page_icon="🏃",
    layout="wide",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* metric cards */
    div[data-testid="stMetric"] {
        background: #f0f2f6;
        border-radius: 12px;
        padding: 16px 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Fitbit Dashboard")


# ── Data loading ────────────────────────────────────────────────────────────
@st.cache_data
def load_steps_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    """Read all steps_*.csv files from the zip and return a single DataFrame."""
    frames: list[pd.DataFrame] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for entry in zf.namelist():
            # Match steps CSVs inside Physical Activity_GoogleData
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

    # Parse timestamps
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    combined["date"] = combined["timestamp"].dt.date

    return combined


@st.cache_data
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
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    combined["date"] = combined["timestamp"].dt.date

    return combined


@st.cache_data
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


# ── File uploader ───────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload your Fitbit Google Takeout zip file",
    type=["zip"],
)

if uploaded_file is None:
    st.info("Upload a Fitbit Takeout .zip file to get started.")
    st.stop()

raw = uploaded_file.getvalue()
df = load_steps_from_zip(raw)
dist_df = load_distance_from_zip(raw)
weight_df = load_weight_from_zip(raw)

if df.empty:
    st.error("No steps CSV files found in the uploaded zip. "
             "Expected files matching `steps_*.csv` inside a "
             "`Physical Activity_GoogleData` folder.")
    st.stop()

# ── Filters ─────────────────────────────────────────────────────────────────
st.markdown("---")

min_date = df["date"].min()
max_date = df["date"].max()

filter_cols = st.columns([2, 2, 1])

with filter_cols[0]:
    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

with filter_cols[1]:
    sources = sorted(df["data source"].dropna().unique().tolist())
    selected_sources = st.multiselect(
        "Data source",
        options=sources,
        default=sources,
    )

with filter_cols[2]:
    view_mode = st.radio("View", ["Daily", "Monthly"], horizontal=True)

# Metric selector (Steps or Distance)
metric_options = ["Steps"]
if not dist_df.empty:
    metric_options.append("Distance")
activity_metric = st.radio("Activity Metric", metric_options, horizontal=True)

if activity_metric == "Distance":
    dist_unit = st.radio("Distance Unit", ["miles", "km"], horizontal=True, key="dist_unit")
    METERS_TO_UNIT = 1609.34 if dist_unit == "miles" else 1000.0
    dist_label = "mi" if dist_unit == "miles" else "km"

# Validate date range selection (user may have picked only one date so far)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

# Apply filters
mask = (
    (df["date"] >= start_date)
    & (df["date"] <= end_date)
    & (df["data source"].isin(selected_sources))
)
filtered = df.loc[mask].copy()

if filtered.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Aggregate metric cards ──────────────────────────────────────────────────
if activity_metric == "Steps":
    daily_steps = filtered.groupby("date")["steps"].sum()

    total_steps = int(daily_steps.sum())
    avg_daily = int(daily_steps.mean())
    best_day = daily_steps.idxmax()
    best_day_steps = int(daily_steps.max())
    num_days = int(daily_steps.shape[0])

    card_cols = st.columns(4)
    card_cols[0].metric("Total Steps", f"{total_steps:,}")
    card_cols[1].metric("Daily Average", f"{avg_daily:,}")
    card_cols[2].metric("Best Day", f"{best_day_steps:,}", delta=str(best_day))
    card_cols[3].metric("Active Days", f"{num_days}")
else:
    # Distance metric
    dist_filtered = dist_df[
        (dist_df["date"] >= start_date)
        & (dist_df["date"] <= end_date)
    ].copy()
    # Distance values are in meters; convert to selected unit
    daily_distance = dist_filtered.groupby("date")["distance"].sum() / METERS_TO_UNIT

    if daily_distance.empty:
        st.warning("No distance data matches the current filters.")
        st.stop()

    total_dist = daily_distance.sum()
    avg_daily_dist = daily_distance.mean()
    best_dist_day = daily_distance.idxmax()
    best_dist = daily_distance.max()
    num_dist_days = int(daily_distance.shape[0])

    card_cols = st.columns(4)
    card_cols[0].metric("Total Distance", f"{total_dist:,.1f} {dist_label}")
    card_cols[1].metric("Daily Average", f"{avg_daily_dist:,.2f} {dist_label}")
    card_cols[2].metric("Best Day", f"{best_dist:,.2f} {dist_label}", delta=str(best_dist_day))
    card_cols[3].metric("Active Days", f"{num_dist_days}")

# ── Line chart ──────────────────────────────────────────────────────────────
st.markdown("---")

if activity_metric == "Steps":
    if view_mode == "Daily":
        chart_df = daily_steps.reset_index()
        chart_df.columns = ["Date", "Steps"]
        chart_df["Date"] = pd.to_datetime(chart_df["Date"])

        fig = px.line(
            chart_df,
            x="Date",
            y="Steps",
            title="Daily Steps",
            markers=False,
        )
    else:
        filtered["year_month"] = filtered["timestamp"].dt.to_period("M")
        monthly = filtered.groupby("year_month")["steps"].sum().reset_index()
        monthly.columns = ["Month", "Steps"]
        monthly["Month"] = monthly["Month"].dt.to_timestamp()

        fig = px.line(
            monthly,
            x="Month",
            y="Steps",
            title="Monthly Steps",
            markers=True,
        )

    fig.update_layout(
        yaxis_tickformat=",",
        hovermode="x unified",
        xaxis_title="",
        yaxis_title="Steps",
        height=480,
    )
else:
    if view_mode == "Daily":
        chart_df = daily_distance.reset_index()
        chart_df.columns = ["Date", f"Distance ({dist_label})"]
        chart_df["Date"] = pd.to_datetime(chart_df["Date"])

        fig = px.line(
            chart_df,
            x="Date",
            y=f"Distance ({dist_label})",
            title="Daily Distance",
            markers=False,
        )
    else:
        dist_filtered["year_month"] = dist_filtered["timestamp"].dt.to_period("M")
        monthly_dist = dist_filtered.groupby("year_month")["distance"].sum().reset_index()
        monthly_dist.columns = ["Month", f"Distance ({dist_label})"]
        monthly_dist["Month"] = monthly_dist["Month"].dt.to_timestamp()
        monthly_dist[f"Distance ({dist_label})"] = monthly_dist[f"Distance ({dist_label})"] / METERS_TO_UNIT

        fig = px.line(
            monthly_dist,
            x="Month",
            y=f"Distance ({dist_label})",
            title="Monthly Distance",
            markers=True,
        )

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="",
        yaxis_title=f"Distance ({dist_label})",
        height=480,
    )

st.plotly_chart(fig, use_container_width=True)

# ── Weight section ──────────────────────────────────────────────────────────
if not weight_df.empty:
    st.markdown("---")
    st.subheader("Weight")

    weight_unit = st.radio("Unit", ["lbs", "kg"], horizontal=True, key="weight_unit")
    LBS_TO_KG = 0.453592

    # Filter weight data to the same date range
    wf = weight_df[
        (weight_df["date"].dt.date >= start_date)
        & (weight_df["date"].dt.date <= end_date)
    ].copy()

    if not wf.empty:
        # Convert if kg selected
        if weight_unit == "kg":
            wf["weight"] = wf["weight"] * LBS_TO_KG
        unit = weight_unit

        # Metric cards
        latest_weight = wf.iloc[-1]["weight"]
        earliest_weight = wf.iloc[0]["weight"]
        weight_change = latest_weight - earliest_weight
        avg_weight = wf["weight"].mean()

        wcols = st.columns(4)
        wcols[0].metric("Latest Weight", f"{latest_weight:.1f} {unit}")
        wcols[1].metric("Average Weight", f"{avg_weight:.1f} {unit}")
        wcols[2].metric(
            "Change",
            f"{latest_weight:.1f} {unit}",
            delta=f"{weight_change:+.1f} {unit}",
            delta_color="inverse",
        )
        wcols[3].metric("Measurements", f"{len(wf)}")

        # Weight & BMI chart
        if "bmi" in wf.columns and wf["bmi"].notna().any():
            weight_fig = make_subplots(specs=[[{"secondary_y": True}]])
            weight_fig.add_trace(
                go.Scatter(
                    x=wf["date"], y=wf["weight"],
                    name=f"Weight ({unit})", mode="lines+markers",
                ),
                secondary_y=False,
            )
            weight_fig.add_trace(
                go.Scatter(
                    x=wf["date"], y=wf["bmi"],
                    name="BMI", mode="lines+markers",
                    line=dict(dash="dot"),
                ),
                secondary_y=True,
            )
            weight_fig.update_yaxes(title_text=f"Weight ({unit})", secondary_y=False)
            weight_fig.update_yaxes(title_text="BMI", secondary_y=True)
            weight_fig.update_layout(title="Weight & BMI Over Time")
        else:
            weight_fig = px.line(
                wf, x="date", y="weight",
                title="Weight Over Time", markers=True,
            )

        weight_fig.update_layout(
            hovermode="x unified",
            xaxis_title="",
            height=480,
        )

        st.plotly_chart(weight_fig, use_container_width=True)
    else:
        st.info("No weight data in the selected date range.")
