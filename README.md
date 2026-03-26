# Fitbit Dashboard

A Streamlit web application that visualizes your Fitbit data from a Google Takeout export. View your steps, distance, weight, and BMI trends through interactive charts and summary metrics.

## Prerequisites

- Python 3.10 or higher
- A Fitbit Google Takeout `.zip` file (see [How to Export Your Data](#how-to-export-your-fitbit-data) below)

## Installation

1. **Clone or download** this project to your local machine.

2. **Create a virtual environment** (recommended):

   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**:

   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

With your virtual environment activated, run:

```bash
streamlit run app.py
```

The dashboard will open in your default browser at `http://localhost:8501`.

## How to Export Your Fitbit Data

1. Go to [Google Takeout](https://takeout.google.com/).
2. Click **Deselect all**, then scroll down and select **Fitbit**.
3. Click **Next step**, choose your export format (`.zip`), and start the export.
4. Once the export is ready, download the `.zip` file. **Do not extract it** — the app reads the zip directly.

## Using the Dashboard

### 1. Upload Your Data

When the app launches you will see a file uploader. Drag and drop (or browse for) your Fitbit Takeout `.zip` file. The app will parse the data automatically.

### 2. Filter Your Data

At the top of the dashboard you can:

| Filter | Description |
|---|---|
| **Date range** | Pick a start and end date to narrow the time window. |
| **Data source** | Select or deselect specific Fitbit data sources. |
| **View** | Toggle between **Daily** and **Monthly** aggregation. |

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

### 6. Weight & BMI

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
| App won't start | Make sure your virtual environment is activated and all dependencies are installed (`pip install -r requirements.txt`). |

## Dependencies

- [Streamlit](https://streamlit.io/) — Web framework
- [Pandas](https://pandas.pydata.org/) — Data manipulation
- [Plotly](https://plotly.com/python/) — Interactive charts
