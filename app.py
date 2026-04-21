import os
import pickle
import secrets
import tempfile
from datetime import date, datetime
from math import ceil

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from plotly.subplots import make_subplots
from werkzeug.utils import secure_filename

from utils.data_parser import (
    load_distance_from_zip,
    load_steps_from_zip,
    load_weight_from_zip,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024  # 250 MB

# Persist the secret key to a file so sessions survive server restarts.
_SECRET_KEY_FILE = os.path.join(tempfile.gettempdir(), "fitbit_dashboard_secret.key")
if os.path.exists(_SECRET_KEY_FILE):
    with open(_SECRET_KEY_FILE, "r") as _f:
        app.secret_key = _f.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(_SECRET_KEY_FILE, "w") as _f:
        _f.write(app.secret_key)

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "fitbit_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _cache_path(session_id: str) -> str:
    return os.path.join(UPLOAD_DIR, f"{session_id}.pkl")


def _save_dataframes(session_id: str, steps_df, dist_df, weight_df):
    with open(_cache_path(session_id), "wb") as f:
        pickle.dump({"steps": steps_df, "distance": dist_df, "weight": weight_df}, f)


def _load_dataframes(session_id: str):
    path = _cache_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def _build_activity_chart(filtered, activity_metric, view_mode, dist_df=None,
                          start_date=None, end_date=None, dist_unit="miles"):
    METERS_TO_UNIT = 1609.34 if dist_unit == "miles" else 1000.0
    dist_label = "mi" if dist_unit == "miles" else "km"

    if activity_metric == "Steps":
        daily_steps = filtered.groupby("date")["steps"].sum()
        metrics = {
            "total": f"{int(daily_steps.sum()):,}",
            "avg": f"{int(daily_steps.mean()):,}",
            "best_value": f"{int(daily_steps.max()):,}",
            "best_day": str(daily_steps.idxmax()),
            "days": str(int(daily_steps.shape[0])),
            "label": "Steps",
        }

        if view_mode == "Daily":
            chart_df = daily_steps.reset_index()
            chart_df.columns = ["Date", "Steps"]
            chart_df["Date"] = pd.to_datetime(chart_df["Date"])
            fig = px.line(chart_df, x="Date", y="Steps", title="Daily Steps", markers=False)
        else:
            filtered = filtered.copy()
            filtered["year_month"] = filtered["timestamp"].dt.to_period("M")
            monthly = filtered.groupby("year_month")["steps"].sum().reset_index()
            monthly.columns = ["Month", "Steps"]
            monthly["Month"] = monthly["Month"].dt.to_timestamp()
            fig = px.line(monthly, x="Month", y="Steps", title="Monthly Steps", markers=True)

        fig.update_layout(yaxis_tickformat=",", hovermode="x unified",
                          xaxis_title="", yaxis_title="Steps", height=480)
    else:
        dist_filtered = dist_df[
            (dist_df["date"] >= start_date) & (dist_df["date"] <= end_date)
        ].copy()
        daily_distance = dist_filtered.groupby("date")["distance"].sum() / METERS_TO_UNIT

        if daily_distance.empty:
            return None, None

        metrics = {
            "total": f"{daily_distance.sum():,.1f} {dist_label}",
            "avg": f"{daily_distance.mean():,.2f} {dist_label}",
            "best_value": f"{daily_distance.max():,.2f} {dist_label}",
            "best_day": str(daily_distance.idxmax()),
            "days": str(int(daily_distance.shape[0])),
            "label": f"Distance ({dist_label})",
        }

        if view_mode == "Daily":
            chart_df = daily_distance.reset_index()
            chart_df.columns = ["Date", f"Distance ({dist_label})"]
            chart_df["Date"] = pd.to_datetime(chart_df["Date"])
            fig = px.line(chart_df, x="Date", y=f"Distance ({dist_label})",
                          title="Daily Distance", markers=False)
        else:
            dist_filtered["year_month"] = dist_filtered["timestamp"].dt.to_period("M")
            monthly_dist = dist_filtered.groupby("year_month")["distance"].sum().reset_index()
            monthly_dist.columns = ["Month", f"Distance ({dist_label})"]
            monthly_dist["Month"] = monthly_dist["Month"].dt.to_timestamp()
            monthly_dist[f"Distance ({dist_label})"] /= METERS_TO_UNIT
            fig = px.line(monthly_dist, x="Month", y=f"Distance ({dist_label})",
                          title="Monthly Distance", markers=True)

        fig.update_layout(hovermode="x unified", xaxis_title="",
                          yaxis_title=f"Distance ({dist_label})", height=480)

    return metrics, fig.to_json()


def _build_weight_chart(weight_df, start_date, end_date, weight_unit="lbs"):
    LBS_TO_KG = 0.453592
    wf = weight_df[
        (weight_df["date"].dt.date >= start_date)
        & (weight_df["date"].dt.date <= end_date)
    ].copy()

    if wf.empty:
        return None, None

    if weight_unit == "kg":
        wf["weight"] = wf["weight"] * LBS_TO_KG
    unit = weight_unit

    latest_weight = wf.iloc[-1]["weight"]
    earliest_weight = wf.iloc[0]["weight"]
    weight_change = latest_weight - earliest_weight
    avg_weight = wf["weight"].mean()

    w_metrics = {
        "latest": f"{latest_weight:.1f} {unit}",
        "avg": f"{avg_weight:.1f} {unit}",
        "change_value": f"{latest_weight:.1f} {unit}",
        "change_delta": f"{weight_change:+.1f} {unit}",
        "measurements": str(len(wf)),
    }

    if "bmi" in wf.columns and wf["bmi"].notna().any():
        weight_fig = make_subplots(specs=[[{"secondary_y": True}]])
        weight_fig.add_trace(
            go.Scatter(x=wf["date"], y=wf["weight"],
                       name=f"Weight ({unit})", mode="lines+markers"),
            secondary_y=False,
        )
        weight_fig.add_trace(
            go.Scatter(x=wf["date"], y=wf["bmi"],
                       name="BMI", mode="lines+markers", line=dict(dash="dot")),
            secondary_y=True,
        )
        weight_fig.update_yaxes(title_text=f"Weight ({unit})", secondary_y=False)
        weight_fig.update_yaxes(title_text="BMI", secondary_y=True)
        weight_fig.update_layout(title="Weight & BMI Over Time")
    else:
        weight_fig = px.line(wf, x="date", y="weight",
                             title="Weight Over Time", markers=True)

    weight_fig.update_layout(hovermode="x unified", xaxis_title="", height=480)

    return w_metrics, weight_fig.to_json()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".zip"):
        return render_template("index.html", error="Please upload a valid .zip file."), 400

    filename = secure_filename(file.filename)
    session_id = secrets.token_hex(16)
    filepath = os.path.join(UPLOAD_DIR, f"{session_id}_{filename}")
    file.save(filepath)

    with open(filepath, "rb") as f:
        raw = f.read()

    steps_df = load_steps_from_zip(raw)
    dist_df = load_distance_from_zip(raw)
    weight_df = load_weight_from_zip(raw)

    if steps_df.empty:
        os.remove(filepath)
        return render_template(
            "index.html",
            error="No steps CSV files found. Expected files matching "
                  "steps_*.csv inside a Physical Activity_GoogleData folder."
        ), 400

    _save_dataframes(session_id, steps_df, dist_df, weight_df)
    os.remove(filepath)  # raw zip no longer needed

    session["sid"] = session_id
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    sid = session.get("sid")
    if not sid:
        return redirect(url_for("index"))

    data = _load_dataframes(sid)
    if data is None:
        return redirect(url_for("index"))

    steps_df = data["steps"]
    dist_df = data["distance"]
    weight_df = data["weight"]

    min_date = str(steps_df["date"].min())
    max_date = str(steps_df["date"].max())
    sources = sorted(steps_df["data source"].dropna().unique().tolist())
    has_distance = not dist_df.empty
    has_weight = not weight_df.empty

    # Default charts
    start_d = steps_df["date"].min()
    end_d = steps_df["date"].max()
    filtered = steps_df.copy()

    metrics, chart_json = _build_activity_chart(filtered, "Steps", "Daily")

    w_metrics, w_chart_json = None, None
    if has_weight:
        w_metrics, w_chart_json = _build_weight_chart(weight_df, start_d, end_d)

    return render_template(
        "dashboard.html",
        min_date=min_date,
        max_date=max_date,
        sources=sources,
        has_distance=has_distance,
        has_weight=has_weight,
        metrics=metrics,
        chart_json=chart_json,
        w_metrics=w_metrics,
        w_chart_json=w_chart_json,
    )


@app.route("/api/update", methods=["POST"])
def api_update():
    sid = session.get("sid")
    if not sid:
        return jsonify({"error": "No data uploaded"}), 400

    data = _load_dataframes(sid)
    if data is None:
        return jsonify({"error": "Session expired"}), 400

    steps_df = data["steps"]
    dist_df = data["distance"]
    weight_df = data["weight"]

    params = request.get_json(force=True)
    start_date = date.fromisoformat(params.get("start_date", str(steps_df["date"].min())))
    end_date = date.fromisoformat(params.get("end_date", str(steps_df["date"].max())))
    selected_sources = params.get("sources", sorted(steps_df["data source"].dropna().unique().tolist()))
    view_mode = params.get("view_mode", "Daily")
    activity_metric = params.get("activity_metric", "Steps")
    dist_unit = params.get("dist_unit", "miles")
    weight_unit = params.get("weight_unit", "lbs")

    mask = (
        (steps_df["date"] >= start_date)
        & (steps_df["date"] <= end_date)
        & (steps_df["data source"].isin(selected_sources))
    )
    filtered = steps_df.loc[mask].copy()

    if filtered.empty:
        return jsonify({"error": "No data matches the current filters."}), 200

    metrics, chart_json = _build_activity_chart(
        filtered, activity_metric, view_mode,
        dist_df=dist_df, start_date=start_date, end_date=end_date, dist_unit=dist_unit,
    )

    if metrics is None:
        return jsonify({"error": "No distance data matches the current filters."}), 200

    result = {"metrics": metrics, "activity_chart_json": chart_json}

    if not weight_df.empty:
        w_metrics, w_chart_json = _build_weight_chart(weight_df, start_date, end_date, weight_unit)
        result["weight_metrics"] = w_metrics
        result["weight_chart_json"] = w_chart_json

    return jsonify(result)


@app.route("/api/target", methods=["POST"])
def api_target():
    sid = session.get("sid")
    if not sid:
        return jsonify({"error": "No data uploaded"}), 400

    data = _load_dataframes(sid)
    if data is None:
        return jsonify({"error": "Session expired"}), 400

    steps_df = data["steps"]
    params = request.get_json(force=True)

    try:
        target_steps = int(params["target_steps"])
        target_start = date.fromisoformat(params["target_start"])
        target_end = date.fromisoformat(params["target_end"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Invalid input. Provide target_steps, target_start, and target_end."}), 400

    selected_sources = params.get("sources", sorted(steps_df["data source"].dropna().unique().tolist()))

    if target_end <= target_start:
        return jsonify({"error": "Target end date must be after start date."}), 400

    if target_steps <= 0:
        return jsonify({"error": "Target steps must be a positive number."}), 400

    today = date.today()

    # Steps completed within the target period (up to today)
    effective_end = min(today, target_end)
    mask = (
        (steps_df["date"] >= target_start)
        & (steps_df["date"] <= effective_end)
        & (steps_df["data source"].isin(selected_sources))
    )
    steps_completed = int(steps_df.loc[mask].groupby("date")["steps"].sum().sum())

    remaining = max(0, target_steps - steps_completed)
    total_days = (target_end - target_start).days + 1
    elapsed_days = max(0, (effective_end - target_start).days + 1)
    days_left = max(0, (target_end - today).days)

    if days_left > 0:
        daily_needed = ceil(remaining / days_left)
    elif remaining == 0:
        daily_needed = 0
    else:
        daily_needed = -1  # deadline passed and target not met

    progress_pct = min(100, round(steps_completed / target_steps * 100, 1)) if target_steps > 0 else 0

    # Determine status based on linear pace
    if remaining == 0:
        status = "completed"
        status_label = "Target reached!"
    elif days_left == 0 and remaining > 0:
        status = "behind"
        status_label = f"Deadline passed — {remaining:,} steps short"
    else:
        expected_by_now = target_steps * (elapsed_days / total_days) if total_days > 0 else 0
        if steps_completed >= expected_by_now:
            status = "ahead"
            status_label = "Ahead of pace"
        else:
            status = "behind"
            status_label = "Behind pace"

    return jsonify({
        "target_steps": f"{target_steps:,}",
        "steps_completed": f"{steps_completed:,}",
        "remaining": f"{remaining:,}",
        "days_left": days_left,
        "daily_needed": f"{daily_needed:,}" if daily_needed >= 0 else "N/A",
        "progress_pct": progress_pct,
        "status": status,
        "status_label": status_label,
    })


@app.errorhandler(413)
def too_large(e):
    return render_template("index.html", error="File too large. Maximum size is 250 MB."), 413


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
