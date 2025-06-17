import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import date
from datetime import timedelta
import math

from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output

from data_fetcher import generate_combined_jobs_csv, download_conversion_report

# ─── 1. Weekly dates ────────────────────────────────
today = date.today()
days_since_sunday = (today.weekday() + 1) % 7
this_sunday = today - timedelta(days=days_since_sunday)
last_sunday   = this_sunday - timedelta(days=7)
last_saturday = last_sunday + timedelta(days=6)

# formatted
lw_sun_str = last_sunday.strftime("%B %d")
lw_sat_str = last_saturday.strftime("%B %d")
lw_sun_csv = last_sunday.strftime("%m/%d/%Y")
lw_sat_csv = last_saturday.strftime("%m/%d/%Y")


# ─── 2. Operations CSV ────────────────────────────

# build filename & path
jobs_fn   = f"{lw_sun_csv.replace('/','')}_{lw_sat_csv.replace('/','')}_jobs.csv"
jobs_path = Path("Data") / jobs_fn

# one log to show what we're checking
print(f"→ Jobs file: {jobs_path}")

if not jobs_path.exists():
    print("   • generating jobs data…")
    jobs_df = generate_combined_jobs_csv(lw_sun_csv, lw_sat_csv, out_path=str(jobs_path))
else:
    print("   • loaded from disk")
    jobs_df = pd.read_csv(jobs_path)

# then your status_chart setup …
status_order = [
    "Measurement Appointment Scheduled", "Measurement Approved",
    "Submitted to Manufacturing Partner","Order Shipped","Order Received",
    "Install Scheduled","Installed","Complete"
]
all_franchisees = ["All"] + sorted(jobs_df["Franchisee"].dropna().unique())


# ─── 3. Call‐Center CSVs ─────────────────────────────

# build filenames
a = lw_sun_csv.replace("/", "")
b = lw_sat_csv.replace("/", "")
nohs_fn  = Path("Data") / f"{a}_{b}_ccNoHs.csv"
yeshs_fn = Path("Data") / f"{a}_{b}_ccYesHs.csv"

# inbound (no homeshow)
print(f"→ Inbound file: {nohs_fn}")
if not nohs_fn.exists():
    print("   • downloading…")
    rep_no, rep_no_opts = download_conversion_report(
        lw_sun_csv, lw_sat_csv, include_homeshow=False, out_path=str(nohs_fn)
    )
else:
    rep_no = pd.read_csv(nohs_fn)
    rep_no_opts = [{"label":"All","value":"All"}] + [
        {"label":r,"value":r} for r in rep_no["Call Center Rep"].unique()
    ]
    print("   • loaded from disk")

# outbound (with homeshow)
print(f"→ Outbound file: {yeshs_fn}")
if not yeshs_fn.exists():
    print("   • downloading…")
    rep_yes, rep_yes_opts = download_conversion_report(
        lw_sun_csv, lw_sat_csv, include_homeshow=True, out_path=str(yeshs_fn)
    )
else:
    rep_yes = pd.read_csv(yeshs_fn)
    rep_yes_opts = [{"label":"All","value":"All"}] + [
        {"label":r,"value":r} for r in rep_yes["Call Center Rep"].unique()
    ]
    print("   • loaded from disk")


# ─── 4. Make Ops Grpah ─────────────────────────────

def make_figure(selected_franchisee):
    # 1) Filter
    df_f = jobs_df if selected_franchisee == "All" else jobs_df[jobs_df["Franchisee"] == selected_franchisee]
    
    # 2) Aggregate
    grouped = (
        df_f
        .groupby(["Status","Order Type"], observed=False)
        .agg(Count=("ID","nunique"))
        .reset_index()
    )
    grouped["Status"] = pd.Categorical(grouped["Status"], categories=status_order, ordered=True)
    
    # 3) Fill missing combos
    order_types = ["New", "Claim", "Reorder"]
    combos = pd.MultiIndex.from_product([status_order, order_types], names=["Status","Order Type"])
    grouped = (
        grouped
        .set_index(["Status","Order Type"])
        .reindex(combos, fill_value=0)
        .reset_index()
    )

    # 4) Compute totals
    totals = (
        grouped
        .groupby("Status", observed=False)["Count"]
        .sum()
        .reindex(status_order)
        .reset_index()
    )
    raw_max = int(totals["Count"].max()) if not totals.empty else 0
    top = math.ceil(raw_max/5) * 5 * 1.1 if raw_max % 5 else raw_max * 1.1
    top = int(math.ceil(top))

    # 5) Build manually with go.Figure()
    fig = go.Figure()

    for ot in order_types:
        df_trace = grouped[grouped["Order Type"] == ot]
        fig.add_trace(go.Bar(
            x=df_trace["Status"],
            y=df_trace["Count"],
            name=ot,
            marker_color={"New":"#2C3E70","Claim":"#a1c4bd","Reorder":"#bbbfbf"}.get(ot, "#888"),
            customdata=[[ot]] * len(df_trace),
            hovertemplate="<b>%{x}</b><br>Type: %{customdata[0]}<br>Count: %{y}<extra></extra>",
            uid=ot  # critical for animation
        ))

    # 6) Add totals
    fig.add_trace(go.Scatter(
        x=totals["Status"], y=totals["Count"] * 1.02,
        mode="text", text=totals["Count"], textposition="top center",
        textfont=dict(color="#2C3E70", size=16), hoverinfo="skip", showlegend=False
    ))

    fig.update_layout(
        uirevision="static-axes",
        plot_bgcolor="white",
        paper_bgcolor="white",
        barmode="stack",
        height=500,
        margin=dict(t=100, b=30, l=40, r=40),
        font=dict(family="Segoe UI, sans-serif", size=14, color="#2C3E70"),  # Global font for axis, legend, etc.
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        title=dict(
            text=f"Project Status by Order Type — {selected_franchisee}",
            font=dict(
                family="Segoe UI, sans-serif",
                size=20,              # Match H1-style prominence
                color="#2C3E70"
            ),
        )
    )
    
    # 8) Shorten labels
    def shorten(lbl):
        lbl = re.sub(r"(?i)measurement[s]?","Meas.",lbl)
        lbl = re.sub(r"(?i)manufacturing( partner)?","MFG",lbl)
        return re.sub(r"(?i)appointment[s]?","Appt.",lbl)

    # 9) Axes
    fig.update_xaxes(
        ticktext=[shorten(s) for s in status_order],
        tickvals=status_order,
        showticklabels=True,
        ticks="outside",
        tickangle=-45,
        showline=True,
        linecolor="#2C3E70",
        autorange=False,
        fixedrange=True,
        range=[-0.5, len(status_order)-0.5]
    )

    fig.update_yaxes(
        range=[0, top],
        autorange=False, rangemode="tozero",
        showticklabels=False, ticks="",
        fixedrange=True
    )

    return fig


# ─── 5. Instantiate Dash App & Layout ─────────────────────────────────────

app = Dash(__name__)
server = app.server
app.title = "Art of Drawers Dashboard"

app.layout = html.Div(
    style={
        "fontFamily": "Segoe UI, sans-serif",
        "margin": "0 auto",
        "maxWidth": "1200px",
        "backgroundColor": "#FFFFFF"
    },

    
    children=[
            
        # Project Status Section
        html.H1(
            f"AoD Weekly Report - {today.strftime('%B %d, %Y')}",
            style={"marginTop": "24px", "color": "#2C3E70", "textAlign": "center", "marginBottom": "16px"}
        ),



        html.H2(
            "Operations",
            style={"marginTop": "24px", "color": "#2C3E70","marginBottom": "6px"}
        ),

        html.Div(
            f"Data collected from last week: {lw_sun_str} – {lw_sat_str}", 
            style={"fontSize": "14px", "color": "gray", "textAlign": "left", "marginBottom": "24px", "fontStyle": "italic"}
        ),
        
        html.Div(
            style={"display": "flex", "flexDirection": "column"},
            children=[
                html.Label(
                    "Select Franchisee:",
                    style={"fontWeight": "600", "color": "#2C3E70", "marginBottom": "4px"}
                ),
                dcc.Dropdown(
                    id="franchisee-selector",
                    options=[{"label": f, "value": f} for f in all_franchisees],
                    value="All",
                    clearable=False,
                    style={
                        "width": "240px",
                        "fontSize": "14px",
                        "borderRadius": "4px",
                        "border": "1px solid #2C3E70"
                    }
                ),
                dcc.Graph(
                    id="status-bar-chart",
                    style={
                        "marginBottom": "0px"
                    }
                )



            ]
        ),

        # Call Center Rep Section
        html.Div(
            style={"marginTop": "0px"},
            children=[
                html.H2(
                    "Call Center", 
                    style={"color": "#2C3E70", "marginBottom": "6px"}),

                html.Div(
                    f"Data collected from last week: {lw_sun_str} – {lw_sat_str}", 
                    style={"fontSize": "14px", "color": "gray", "textAlign": "left", "marginBottom": "24px", "fontStyle": "italic"}
                ),

                html.Div(
                    style={"marginBottom": "12px"},
                    children=[
                        html.Label(
                            "Select Call Center Rep:",
                            style={
                                "fontWeight": "600",
                                "color": "#2C3E70",
                                "marginBottom": "4px"
                            }
                        ),
                        dcc.Dropdown(
                            id="rep-selector",
                            options=rep_no_opts,
                            value="All",
                            clearable=False,
                            style={
                                "width": "260px",
                                "border": "1px solid #2C3E70",
                                "borderRadius": "4px",
                                "fontSize": "14px"
                            }
                        )
                    ]
                ),

                # Metrics container
                html.Div(
                    id="metrics-container",
                    style={
                        "display": "flex",
                        "justifyContent": "center",
                        "gap": "80px",
                        "marginBottom": "16px"
                    },
                    children=[
                        html.Div(id="touches-metric", style={"textAlign": "center"}),
                        html.Div(id="design-metric", style={"textAlign": "center"})
                    ]
                ),

                # Tables
                html.Div(
                    style={"display": "flex", "gap": "40px"},
                    children=[
                        # Inbound
                        html.Div(
                            style={"flex": "1"},
                            children=[
                                html.H4(
                                    "Inbound Performance",
                                    style={"textAlign": "center", "color": "#2C3E70", "marginBottom": "6px"}
                                ),

                                html.Div(
                                f"(excludes homeshow data)", 
                                style={"fontSize": "14px", "color": "gray", "textAlign": "center", "marginBottom": "24px", "fontStyle": "italic"}
                                ),
                                
                                dash_table.DataTable(
                                    id="inbound-table",
                                    columns=[],
                                    data=[],
                                    style_cell={
                                        "padding": "8px",
                                        "fontFamily": "Segoe UI, sans-serif",
                                        "fontSize": "14px",
                                        "textAlign": "left"
                                    },
                                    style_header={
                                        "backgroundColor": "#2C3E70",
                                        "color": "white",
                                        "fontWeight": "bold"
                                    },
                                    style_data_conditional=[
                                        {"if": {"row_index": "odd"}, "backgroundColor": "#F9F9F9"},
                                        {"if": {"row_index": "even"}, "backgroundColor": "#EFEFEF"},
                                        # inbound rate coloring
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} >= 86",
                                                "column_id": "Inbound Help Rate (%)"
                                            },
                                            "backgroundColor": "#00cc96",
                                            "color": "white"
                                        },
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} < 86",
                                                "column_id": "Inbound Help Rate (%)"
                                            },
                                            "backgroundColor": "#ef553b",
                                            "color": "white"
                                        }
                                    ]
                                )
                            ]
                        ),
                        # Outbound
                        html.Div(
                            style={"flex": "1"},
                            children=[
                                html.H4(
                                    "Outbound Performance",
                                    style={"textAlign": "center", "color": "#2C3E70", "marginBottom": "6px"}
                                ),

                                html.Div(
                                    f"(includes homeshow data)", 
                                    style={"fontSize": "14px", "color": "gray", "textAlign": "center", "marginBottom": "24px", "fontStyle": "italic"}
                                ),
                                
                                dash_table.DataTable(
                                    id="outbound-table",
                                    columns=[],
                                    data=[],
                                    style_cell={
                                        "padding": "8px",
                                        "fontFamily": "Segoe UI, sans-serif",
                                        "fontSize": "14px",
                                        "textAlign": "left"
                                    },
                                    style_header={
                                        "backgroundColor": "#2C3E70",
                                        "color": "white",
                                        "fontWeight": "bold"
                                    },
                                    style_data_conditional=[
                                        {"if": {"row_index": "odd"}, "backgroundColor": "#F9F9F9"},
                                        {"if": {"row_index": "even"}, "backgroundColor": "#EFEFEF"},
                                        # touches-proxy coloring
                                        {
                                            "if": {
                                                "filter_query": "{Outbound Proxy Value} >= 700",
                                                "column_id": "Touches - Proxy"
                                            },
                                            "backgroundColor": "#00cc96",
                                            "color": "white"
                                        },
                                        {
                                            "if": {
                                                "filter_query": "{Outbound Proxy Value} < 700",
                                                "column_id": "Touches - Proxy"
                                            },
                                            "backgroundColor": "#ef553b",
                                            "color": "white"
                                        }
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ]
        ),
        
        html.H2(
            "Finance", 
            style={"color": "#2C3E70", "marginBottom": "6px"}
        ),

        html.Div(
            f"Data collected from last week: {lw_sun_str} – {lw_sat_str}", 
            style={"fontSize": "14px", "color": "gray", "textAlign": "left", "marginBottom": "24px", "fontStyle": "italic"}
        ),

        html.H2(
            "Marketing", 
            style={"color": "#2C3E70", "marginBottom": "6px"}
        ),

        html.Div(
            f"Data collected from last week: {lw_sun_str} – {lw_sat_str}", 
            style={"fontSize": "14px", "color": "gray", "textAlign": "left", "marginBottom": "24px", "fontStyle": "italic"}
        ),

    ]
)

# ─── 6. Callbacks ───────────────────────────────────────────────────────────

@app.callback(
    Output("status-bar-chart","figure"),
    Input("franchisee-selector","value")
)
def update_ops(selected):
    try:
        return make_figure(selected)
    except Exception:
        import traceback
        print("Error in make_figure:\n", traceback.format_exc())
        # return an empty figure so Dash doesn’t crash completely
        return go.Figure()

@app.callback(
    Output("metrics-container","children"),
    Output("inbound-table","columns"),
    Output("inbound-table","data"),
    Output("outbound-table","columns"),
    Output("outbound-table","data"),
    Input("rep-selector","value")
)
def update_rep_section(sel):
    # pick the right inbound vs outbound DF
    df_in  = rep_no  if sel=="All" else rep_no[rep_no["Call Center Rep"]==sel]
    df_out = rep_yes if sel=="All" else rep_yes[rep_yes["Call Center Rep"]==sel]

    
    # ── metric 1: touches (proxy) ─────────────────────────
    total_proxy = int(df_out["Outbound Communication Count"].sum())
    proxy_color = "#00cc96" if total_proxy >= 700 else "#ef553b"
    
    touches_box = html.Div(
        [
            html.H1(f"{total_proxy}", style={"margin": 0, "fontSize": "48px", "color": proxy_color}),
            html.Div("touches - proxy", style={"fontSize": "14px", "color": "gray"})
        ],
        style={"textAlign": "center"}    # ← add this
    )
    
    # ── metric 2: design appointments ──────────────────────
    total_booked = int(df_out["Total Booked"].sum())
    
    design_box = html.Div(
        [
            html.H1(f"{total_booked}", style={"margin": 0, "fontSize": "48px", "color": "#2C3E70"}),
            html.Div("design appointments scheduled", style={"fontSize": "14px", "color": "gray"})
        ],
        style={"textAlign": "center"}    # ← and this
    )
    
    # bundle them for the first output
    metrics = [touches_box, design_box]


    # ── build inbound table ─────────────────────────────────
    if sel=="All":
        tl = df_in["Inbound Lead Count"].sum()
        tb = df_in["Inbound Booked Count"].sum()
        hr = (tb/tl*100) if tl else 0
        in_cols = [
            {"name":"Call Center Rep","id":"Call Center Rep"},
            {"name":"Inbound Lead Count","id":"Inbound Lead Count"},
            {"name":"Inbound Booked Count","id":"Inbound Booked Count"},
            {"name":"Inbound Help Rate (%)","id":"Inbound Help Rate (%)"},
        ]
        in_data = [{
            "Call Center Rep":"BSC – Total",
            "Inbound Lead Count":tl,
            "Inbound Booked Count":tb,
            "Inbound Rate Value":hr,
            "Inbound Help Rate (%)":f"{hr:.1f}%"
        }]
    else:
        in_cols = [
            {"name":"Call Center Rep","id":"Call Center Rep"},
            {"name":"Inbound Lead Count","id":"Inbound Lead Count"},
            {"name":"Inbound Booked Count","id":"Inbound Booked Count"},
            {"name":"Inbound Help Rate (%)","id":"Inbound Help Rate (%)"},
        ]
        in_data = df_in[[
            "Call Center Rep",
            "Inbound Lead Count",
            "Inbound Booked Count",
            "Inbound Help Rate (%)"
        ]].to_dict("records")

    # ── build outbound table ────────────────────────────────
    if sel=="All":
        tp  = df_out["Outbound Communication Count"].sum()
        ol  = df_out["Outbound Lead Count"].sum()
        ob  = df_out["Outbound Booked Count"].sum()
        ohr = (ob/tp*100) if tp else 0
        out_cols = [
            {"name":"Call Center Rep","id":"Call Center Rep"},
            {"name":"Outbound Lead Count","id":"Outbound Lead Count"},
            {"name":"Outbound Booked Count","id":"Outbound Booked Count"},
            {"name":"Outbound Help Rate (%)","id":"Outbound Help Rate (%)"},
        ]
        out_data = [{
            "Call Center Rep":"BSC – Total",
            "Outbound Lead Count":ol,
            "Outbound Booked Count":ob,
            "Outbound Proxy Value":tp,
            "Outbound Help Rate (%)":f"{ohr:.1f}%"
        }]
    else:
        out_cols = [
            {"name":"Call Center Rep","id":"Call Center Rep"},
            {"name":"Outbound Lead Count","id":"Outbound Lead Count"},
            {"name":"Outbound Booked Count","id":"Outbound Booked Count"},
            {"name":"Outbound Help Rate (%)","id":"Outbound Help Rate (%)"},
        ]
        out_data = (
            df_out
            .rename(columns={"Outbound Communication Count":"Touches – Proxy"})
            [[
                "Call Center Rep",
                "Touches – Proxy",
                "Outbound Lead Count",
                "Outbound Booked Count",
                "Outbound Help Rate (%)"
            ]]
            .to_dict("records")
        )

    # return exactly 5 items** to match the 5 Outputs
    return metrics, in_cols, in_data, out_cols, out_data


# ─── 7. Run ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=8053)
