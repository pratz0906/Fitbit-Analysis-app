"""
Fitbit Analysis – Standalone Desktop Application (No Server)

Uses pywebview's JavaScript-to-Python bridge so all data processing runs
natively in-process.  No Flask, no HTTP server, no network port.

Charts are rendered client-side with Plotly.js; the Python side only
returns JSON payloads through the bridge.

Usage:
    python fitbit_desktop.py
"""

import os
import sys
from datetime import date
from math import ceil

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webview

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.data_parser import (
    load_distance_from_zip,
    load_steps_from_zip,
    load_weight_from_zip,
)


# ── API exposed to JavaScript as  pywebview.api.*  ─────────────────────────

class Api:
    def __init__(self):
        self._window = None
        self.steps_df = None
        self.dist_df = None
        self.weight_df = None

    def set_window(self, window):
        self._window = window

    # ── File selection & loading ────────────────────────────────────────

    def select_file(self):
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Zip Files (*.zip)",),
        )
        if not result:
            return None
        return result[0]

    def load_file(self, filepath):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        try:
            self.steps_df = load_steps_from_zip(raw)
            self.dist_df = load_distance_from_zip(raw)
            self.weight_df = load_weight_from_zip(raw)
        except Exception as e:
            return {"error": f"Failed to parse data: {e}"}

        if self.steps_df.empty:
            return {
                "error": "No steps CSV files found. Expected files matching "
                         "steps_*.csv inside a Physical Activity_GoogleData folder."
            }

        min_date = str(self.steps_df["date"].min())
        max_date = str(self.steps_df["date"].max())
        sources = sorted(self.steps_df["data source"].dropna().unique().tolist())
        has_distance = not self.dist_df.empty
        has_weight = not self.weight_df.empty

        metrics, chart_json = self._build_activity_chart(
            self.steps_df.copy(), "Steps", "Daily",
        )

        w_metrics, w_chart_json = None, None
        if has_weight:
            w_metrics, w_chart_json = self._build_weight_chart(
                self.weight_df,
                self.steps_df["date"].min(),
                self.steps_df["date"].max(),
            )

        return {
            "filename": os.path.basename(filepath),
            "min_date": min_date,
            "max_date": max_date,
            "sources": sources,
            "has_distance": has_distance,
            "has_weight": has_weight,
            "metrics": metrics,
            "chart_json": chart_json,
            "w_metrics": w_metrics,
            "w_chart_json": w_chart_json,
        }

    # ── Filter update ───────────────────────────────────────────────────

    def update_filters(self, params):
        if self.steps_df is None:
            return {"error": "No data loaded"}

        start_date = date.fromisoformat(
            params.get("start_date", str(self.steps_df["date"].min()))
        )
        end_date = date.fromisoformat(
            params.get("end_date", str(self.steps_df["date"].max()))
        )
        selected_sources = params.get(
            "sources",
            sorted(self.steps_df["data source"].dropna().unique().tolist()),
        )
        view_mode = params.get("view_mode", "Daily")
        activity_metric = params.get("activity_metric", "Steps")
        dist_unit = params.get("dist_unit", "miles")
        weight_unit = params.get("weight_unit", "lbs")

        mask = (
            (self.steps_df["date"] >= start_date)
            & (self.steps_df["date"] <= end_date)
            & (self.steps_df["data source"].isin(selected_sources))
        )
        filtered = self.steps_df.loc[mask].copy()

        if filtered.empty:
            return {"error": "No data matches the current filters."}

        metrics, chart_json = self._build_activity_chart(
            filtered, activity_metric, view_mode,
            dist_df=self.dist_df,
            start_date=start_date,
            end_date=end_date,
            dist_unit=dist_unit,
        )

        if metrics is None:
            return {"error": "No distance data matches the current filters."}

        result = {"metrics": metrics, "activity_chart_json": chart_json}

        if not self.weight_df.empty:
            w_metrics, w_chart_json = self._build_weight_chart(
                self.weight_df, start_date, end_date, weight_unit,
            )
            result["weight_metrics"] = w_metrics
            result["weight_chart_json"] = w_chart_json

        return result

    # ── Target tracker ──────────────────────────────────────────────────

    def calculate_target(self, params):
        if self.steps_df is None:
            return {"error": "No data loaded"}

        try:
            target_steps = int(params["target_steps"])
            target_start = date.fromisoformat(params["target_start"])
            target_end = date.fromisoformat(params["target_end"])
        except (KeyError, ValueError, TypeError):
            return {"error": "Invalid input. Provide target_steps, target_start, and target_end."}

        if target_end <= target_start:
            return {"error": "Target end date must be after start date."}
        if target_steps <= 0:
            return {"error": "Target steps must be a positive number."}

        today = date.today()
        effective_end = min(today, target_end)

        mask = (self.steps_df["date"] >= target_start) & (self.steps_df["date"] <= effective_end)
        steps_completed = int(self.steps_df.loc[mask].groupby("date")["steps"].sum().sum())

        remaining = max(0, target_steps - steps_completed)
        total_days = (target_end - target_start).days + 1
        elapsed_days = max(0, (effective_end - target_start).days + 1)
        days_left = max(0, (target_end - today).days)

        if days_left > 0:
            daily_needed = ceil(remaining / days_left)
        elif remaining == 0:
            daily_needed = 0
        else:
            daily_needed = -1

        progress_pct = (
            min(100, round(steps_completed / target_steps * 100, 1))
            if target_steps > 0 else 0
        )

        if remaining == 0:
            status, status_label = "completed", "Target reached!"
        elif days_left == 0 and remaining > 0:
            status = "behind"
            status_label = f"Deadline passed — {remaining:,} steps short"
        else:
            expected_by_now = target_steps * (elapsed_days / total_days) if total_days > 0 else 0
            if steps_completed >= expected_by_now:
                status, status_label = "ahead", "Ahead of pace"
            else:
                status, status_label = "behind", "Behind pace"

        return {
            "target_steps": f"{target_steps:,}",
            "steps_completed": f"{steps_completed:,}",
            "remaining": f"{remaining:,}",
            "days_left": days_left,
            "daily_needed": f"{daily_needed:,}" if daily_needed >= 0 else "N/A",
            "progress_pct": progress_pct,
            "status": status,
            "status_label": status_label,
        }

    # ── Chart builders ──────────────────────────────────────────────────

    def _build_activity_chart(self, filtered, activity_metric, view_mode,
                              dist_df=None, start_date=None, end_date=None,
                              dist_unit="miles"):
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
                fig = px.line(chart_df, x="Date", y="Steps",
                              title="Daily Steps", markers=False)
            else:
                filtered = filtered.copy()
                filtered["year_month"] = filtered["timestamp"].dt.to_period("M")
                monthly = filtered.groupby("year_month")["steps"].sum().reset_index()
                monthly.columns = ["Month", "Steps"]
                monthly["Month"] = monthly["Month"].dt.to_timestamp()
                fig = px.line(monthly, x="Month", y="Steps",
                              title="Monthly Steps", markers=True)

            fig.update_layout(yaxis_tickformat=",", hovermode="x unified",
                              xaxis_title="", yaxis_title="Steps", height=480)
        else:
            if dist_df is None or dist_df.empty:
                return None, None
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

    def _build_weight_chart(self, weight_df, start_date, end_date,
                            weight_unit="lbs"):
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
                           name="BMI", mode="lines+markers",
                           line=dict(dash="dot")),
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


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    api = Api()
    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "desktop.html",
    )

    window = webview.create_window(
        title="Fitbit Dashboard",
        url=html_path,
        js_api=api,
        width=1300,
        height=900,
        min_size=(900, 640),
        text_select=True,
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
