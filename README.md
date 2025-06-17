# Art of Drawers Weekly Dashboard

This is a Dash-based dynamic reporting dashboard for weekly job and call center performance.

## Features
- Automatically fetches weekly Canvas data using authenticated cookies
- Displays operational and call center performance metrics
- Deployed on Render.com with scheduled updates

## Setup Instructions
1. Make sure your `canvas_cookies.json` is present in the root directory.
2. Install dependencies:
   pip install -r requirements.txt
3. Run locally:
   python app.py

## Deployment
Use `render.yaml` to deploy this project as a Dash app to Render.com.

NOTE: Be sure to upload your `canvas_cookies.json` as a Secret File in Render.