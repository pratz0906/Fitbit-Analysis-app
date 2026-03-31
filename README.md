# Fitbit Dashboard

A Flask web application that visualizes your Fitbit data from a Google Takeout export. View your steps, distance, weight, and BMI trends through interactive charts and summary metrics. Set step targets and track your daily progress.

## Prerequisites

- Python 3.10 or higher
- A Fitbit Google Takeout `.zip` file (see [How to Export Your Data](#how-to-export-your-fitbit-data) below)

## Running the Application

### Option A: Double-click launcher (easiest)

- **Windows** — Double-click `run.bat`
- **macOS / Linux** — Run `./run.sh` (you may need to `chmod +x run.sh` first)

The launcher will automatically create a virtual environment, install dependencies, start the server, and open your browser.

### Option B: Manual setup

1. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   ```

2. **Activate the virtual environment**:

   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the app**:

   ```bash
   python app.py
   ```

5. Open `http://localhost:5000` in your browser.

## How to Export Your Fitbit Data

1. Go to [Google Takeout](https://takeout.google.com/).
2. Click **Deselect all**, then scroll down and select **Fitbit**.
3. Click **Next step**, choose your export format (`.zip`), and start the export.
4. Once the export is ready, download the `.zip` file. **Do not extract it** — the app reads the zip directly.

## Using the Dashboard

### 1. Upload Your Data

When the app launches you will see a file uploader. Drag and drop (or browse for) your Fitbit Takeout `.zip` file (up to 250 MB). The app will parse the data automatically.

### 2. Filter Your Data

At the top of the dashboard you can:

| Filter | Description |
|---|---|
| **Date range** | Pick a start and end date to narrow the time window. |
| **Data source** | Select or deselect specific Fitbit data sources. |
| **View** | Toggle between **Daily** and **Monthly** aggregation. |

Filters update the dashboard instantly via AJAX — no page reload needed.

### 3. Choose an Activity Metric

Select either **Steps** or **Distance** (if distance data is available in your export).

- When **Distance** is selected, you can also choose between **miles** and **km**.

### 4. Summary Cards

Four metric cards are displayed at the top:

- **Total** — Sum of steps or distance over the selected period.
- **Daily Average** — Mean per day.
- **Best Day** — Highest single-day value and its date.
- **Active Days** — Number of days with recorded data.

### 5. Activity Chart

An interactive line chart plots your steps or distance over time. Hover over the chart for exact values.

### 6. Steps Target Tracker

Set a step goal for any time period:

- Enter your **target steps** (e.g. 100,000) and choose a **start date** and **end date**.
- Click **Calculate** to see:
  - Steps completed so far
  - Remaining steps
  - Days left
  - **Daily steps needed** to hit the target
  - A progress bar and on-track/behind status indicator

### 7. Weight & BMI

If your export contains weight data (`weight-*.json` files inside `Global Export Data`), a **Weight** section appears below the activity chart:

- Toggle between **lbs** and **kg**.
- View latest weight, average weight, total change, and measurement count.
- A combined **Weight & BMI** chart is displayed if BMI data is present.

## Troubleshooting

| Issue | Solution |
|---|---|
| "No steps CSV files found" | Ensure your zip contains a `Physical Activity_GoogleData` folder with `steps_*.csv` files. You may need to re-export from Google Takeout with Fitbit selected. |
| Distance option not showing | Your export may not contain `distance_*.csv` files. Check the `Physical Activity_GoogleData` folder inside the zip. |
| Weight section not appearing | Your export may not include `weight-*.json` files. Verify the `Global Export Data` folder is present in the zip. |
| File too large error | The maximum upload size is 250 MB. If your export is larger, try selecting fewer Fitbit data categories in Google Takeout. |
| App won't start | Make sure your virtual environment is activated and all dependencies are installed (`pip install -r requirements.txt`). |

## Dependencies

- [Flask](https://flask.palletsprojects.com/) — Web framework
- [Pandas](https://pandas.pydata.org/) — Data manipulation
- [Plotly](https://plotly.com/python/) — Interactive charts
