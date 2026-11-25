"""CONNEXION stakeholder dashboard. Edit content.json for prose and labels."""

from __future__ import annotations

import json
import hmac
import os
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


HERE = Path(__file__).resolve().parent
YEARS = [2020, 2030, 2040, 2049]
REFERENCE_ORDER = ["16", "120", "183", "208", "68", "434", "87", "464", "540", "621"]
REFERENCE_DISPLAY_ORDER = [
    "water_resources", "agriculture_water_demand", "total_allocation_deficit", "agricultural_water_deficit",
    "dam_storage", "local_storage", "irrigated_crop_production", "rainfed_crop_production",
    "total_crop_market_value",
    "local_crop_food_energy", "food_energy_adequacy", "food_insecurity_fraction",
    "energy_supply", "energy_consumption", "total_malaria_incidence",
    "undernutrition_under_5", "human_prevalence_proxy",
]
POLICY_ORDER = ["696", "194", "438", "394", "396", "433", "87", "464", "53", "46", "540", "621"]
POLICY_COMPARISON_ORDER = [
    "water_resources", "total_allocation_deficit", "agricultural_water_deficit",
    "local_crop_food_energy", "irrigated_crop_production", "rainfed_crop_production", "total_crop_market_value",
    "energy_supply", "energy_consumption",
    "undernutrition_under_5", "human_prevalence_proxy", "total_malaria_incidence",
]
PERIOD_COMPARISON_ORDER = [
    "water_resources", "total_allocation_deficit", "irrigated_crop_production",
    "rainfed_crop_production", "local_crop_food_energy", "energy_consumption",
    "food_insecurity_fraction", "total_malaria_incidence",
]
COLORS = {
    "Water": "#1f6fa5",
    "Food": "#317c58",
    "Agriculture": "#317c58",
    "Food security": "#317c58",
    "Energy": "#b67a1d",
    "Health": "#b7474d",
    "Demography": "#556d76",
}
SCENARIO_COLORS = {
    "ref": "#526a70",
    "centralised_development": "#bd6b28",
    "local_resilience": "#2d7d5a",
    "resource_efficiency": "#2776a8",
}
GRAY = "#687a80"


def access_key() -> str:
    """Read the optional shared access key from deployment secrets."""
    try:
        configured = st.secrets.get("CONNEXION_ACCESS_KEY", "")
    except Exception:
        configured = ""
    return str(configured or os.environ.get("CONNEXION_ACCESS_KEY", "")).strip()


def require_access_key() -> None:
    """Gate the dashboard when a shared key has been configured by the host."""
    expected = access_key()
    if not expected or st.session_state.get("access_granted", False):
        return
    st.title("CONNEXION modelling dashboard")
    st.markdown("Enter the shared access key to continue.")
    entered = st.text_input("Access key", type="password", label_visibility="collapsed")
    if st.button("Open dashboard", type="primary"):
        if hmac.compare_digest(entered, expected):
            st.session_state.access_granted = True
            st.rerun()
        st.error("The access key is not valid.")
    st.stop()


@st.cache_data(show_spinner=False)
def load_data(data_modified_ns: int) -> dict:
    return json.loads((HERE / "data.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_ssp_data(data_modified_ns: int) -> dict:
    return json.loads((HERE / "ssp_baseline.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_policy_ensemble(data_modified_ns: int) -> dict:
    return json.loads((HERE / "ssp_policy_ensemble.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_results(data_modified_ns: int) -> pd.DataFrame:
    rows = load_data(data_modified_ns)["results"]
    df = pd.DataFrame(rows, columns=["month", "location", "indicator", "case", "value"])
    df["year"] = df["month"].str.slice(0, 4).astype(int)
    return df


def load_content() -> dict:
    # Intentionally uncached: editing this small file updates visible text on rerun.
    return json.loads((HERE / "content.json").read_text(encoding="utf-8"))


def load_evidence() -> dict:
    # Reviewed narrative notes are kept separate from generated model data.
    return json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))


def fmt(value: float | None, digits: int = 2) -> str:
    if value is None or not pd.notna(value):
        return "—"
    value = float(value)
    if abs(value) >= 1e9:
        return f"{value / 1e9:,.{digits}f} bn"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.{digits}f} m"
    if abs(value) >= 1e3:
        return f"{value:,.0f}"
    return f"{value:,.{digits}f}"


def percent(reference: float, variant: float) -> float | None:
    if not pd.notna(reference) or not pd.notna(variant):
        return None
    if abs(reference) < 1e-9:
        # (variant + epsilon) / (reference + epsilon) = 1 for paired zeros.
        return 0.0 if abs(variant) < 1e-9 else None
    return 100 * (variant - reference) / reference


def percentage_label(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}%"


def chart_base(unit: str, height: int = 260) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=45, r=15, t=15, b=45),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", color="#37535a", size=11),
        showlegend=False,
        hovermode="x unified",
    )
    fig.update_xaxes(title_text="Year", tickmode="array", tickvals=YEARS, range=[2015, 2049], showgrid=False, linecolor="#a9babd")
    fig.update_yaxes(title_text=unit, gridcolor="#e7eeee", zeroline=False,
                     tickformat="~s", automargin=True, rangemode="tozero")
    return fig


def add_ribbon(fig: go.Figure, years: list, low: list, high: list, color: str, name: str) -> None:
    fig.add_trace(go.Scatter(x=years, y=low, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=years, y=high, mode="lines", line=dict(width=0), fill="tonexty",
        fillcolor=color, hoverinfo="skip", showlegend=False, name=name,
    ))


def scaled(item: dict, values: list) -> list:
    return [v * 100 if item["kind"] == "fraction" and v is not None else v for v in values]


def axis_unit(item: dict) -> str:
    return "%" if item["kind"] == "fraction" else item["unit"]


def reference_chart(item: dict, ensemble_item: dict, show_previous: bool = False) -> go.Figure:
    annual = item["annual"]
    years = annual["years"]
    color = COLORS.get(item["domain"], GRAY)
    fig = chart_base(axis_unit(item))
    fig.update_xaxes(range=[2020, 2049])
    paths = ensemble_item["paths"]
    ssp1 = scaled(item, paths["ssp126"]["reference"]["median"])
    ssp5 = scaled(item, paths["ssp585"]["reference"]["median"])
    for scenario, fill in (("ssp126", "rgba(31,111,165,.15)"),
                           ("ssp585", "rgba(183,71,77,.15)")):
        band = paths[scenario]["reference"]
        add_ribbon(fig, years, scaled(item, band["p10"]), scaled(item, band["p90"]),
                   fill, f"{scenario} stochastic range")
    fig.add_trace(go.Scatter(x=years, y=ssp1, mode="lines", line=dict(color=color, width=2.8),
                             name="SSP1-2.6"))
    fig.add_trace(go.Scatter(x=years, y=ssp5, mode="lines", line=dict(color=color, width=2.8, dash="dash"),
                             name="SSP5-8.5"))
    if show_previous and "prior_ssp126" in annual:
        fig.add_trace(go.Scatter(x=years, y=scaled(item, annual["prior_ssp126"]), mode="lines",
                                 line=dict(color="#252c2e", width=1.7, dash="dot"), name="Previous SSP1-2.6"))
        fig.add_trace(go.Scatter(x=years, y=scaled(item, annual["prior_ssp585"]), mode="lines",
                                 line=dict(color="#252c2e", width=1.7, dash="dashdot"), name="Previous SSP5-8.5"))
    bounds = [value for scenario in ("ssp126", "ssp585")
              for stat in ("p10", "p90")
              for value in scaled(item, paths[scenario]["reference"][stat])]
    if show_previous and "prior_ssp126" in annual:
        bounds += scaled(item, annual["prior_ssp126"]) + scaled(item, annual["prior_ssp585"])
    if item["kind"] == "fraction":
        fig.update_yaxes(range=[0, 100], ticksuffix="%", tickformat=".0f")
    else:
        fig.update_yaxes(range=[0, max(1, max(bounds) * 1.06)])
    return fig


def snapshot_heatmap(rows: list[dict], columns: list[str], title: str) -> go.Figure:
    values = [[row.get(column) for column in columns] for row in rows]
    text_values = [["—" if value is None else f"{value:+.0f}%" for value in line]
                   for line in values]
    clipped = [[None if value is None else max(-100, min(100, value)) for value in line]
               for line in values]
    fig = go.Figure(go.Heatmap(
        z=clipped, x=columns, y=[row["Indicator"] for row in rows],
        text=text_values, texttemplate="%{text}",
        colorscale=[[0, "#3f73a4"], [.5, "#f7f8f7"], [1, "#c47b3b"]],
        zmin=-100, zmax=100, zmid=0,
        colorbar=dict(title="Change (%)"),
        hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(template="plotly_white", title=title,
                      height=max(310, 31 * len(rows) + 130),
                      margin=dict(l=200, r=35, t=60, b=55),
                      yaxis=dict(autorange="reversed"),
                      xaxis=dict(side="top"), font=dict(size=11))
    return fig


def baseline_change_rows(ensemble: dict, keys: list[str]) -> list[dict]:
    rows = []
    for key in keys:
        item = ensemble["indicators"][key]
        row = {"Indicator": item["label"]}
        for scenario, label in (("ssp126", "SSP1"), ("ssp585", "SSP5")):
            series = item["paths"][scenario]["reference"]["median"]
            for year in (2030, 2049):
                row[f"{label} {year}"] = percent(series[0], series[year - 2020])
        rows.append(row)
    return rows


def policy_markers(fig: go.Figure, selected: str) -> None:
    fig.add_vline(x=2030, line_color="#667d82", line_dash="dash", line_width=1.4)


def policy_absolute_chart(item: dict, selected: list[str]) -> go.Figure:
    annual = item["annual"]
    years = annual["ref"]["years"]
    color = COLORS.get(item["domain"], GRAY)
    fig = chart_base(axis_unit(item), 245)
    for scenario in ["ref"] + selected:
        band = annual[scenario]
        add_ribbon(fig, years, scaled(item, band["p10"]), scaled(item, band["p90"]),
                   "rgba(90,125,132,.10)", f"{scenario} 10th–90th percentile")
        fig.add_trace(go.Scatter(x=years, y=scaled(item, annual[scenario]["median"]), mode="lines",
                                 line=dict(color=SCENARIO_COLORS.get(scenario, color), width=3 if scenario == "ref" else 2.4,
                                           dash="dash" if scenario == "ref" else "solid"), name=scenario.replace("_", " ").title()))
    if item["kind"] == "fraction":
        fig.update_yaxes(range=[0, 100], ticksuffix="%", tickformat=".0f")
    policy_markers(fig, "")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.22, x=0, font=dict(size=10)))
    return fig


def policy_relative_chart(item: dict, selected: list[str]) -> go.Figure:
    annual = item["annual"]
    years = annual["ref"]["years"]
    ref = annual["ref"]["median"]
    color = COLORS.get(item["domain"], GRAY)
    fig = chart_base("Change from reference (%)", 245)
    fig.add_hline(y=0, line_color="#516066", line_width=1.6)
    finite = [0]
    for scenario in selected:
        values = [percent(a, b) for a, b in zip(ref, annual[scenario]["median"])]
        band = item["relative"][scenario]
        add_ribbon(fig, years, band["p10"], band["p90"], "rgba(90,125,132,.12)", f"{scenario} 10th–90th percentile")
        fig.add_trace(go.Scatter(x=years, y=values, mode="lines", line=dict(color=SCENARIO_COLORS.get(scenario, color), width=2.5), name=scenario.replace("_", " ").title()))
        finite.extend([float(v) for v in values + band["p10"] + band["p90"] if v is not None and pd.notna(v)])
    policy_markers(fig, "")
    lo, hi = min(finite), max(finite)
    pad = max((hi - lo) * .10, 0.5)
    fig.update_yaxes(range=[lo - pad, hi + pad], ticksuffix="%", tickformat=".2~f")
    return fig


def period_average_heatmap(data: dict, labels: dict, selected: list[str], keys: list[str]) -> go.Figure:
    """Compare late and early period averages against the reference trajectory."""
    periods = [("2020–2030", 2020, 2030), ("2040–2049", 2040, 2049)]
    scenarios = selected
    columns = [f"{labels[scenario]} · {period[0]}" for scenario in scenarios for period in periods]
    rows, z, hover = [], [], []
    for key in keys:
        if key not in data["policy"]:
            continue
        item = data["policy"][key]
        years = item["annual"]["ref"]["years"]
        ref = item["annual"]["ref"]["median"]
        row_values, row_hover = [], []
        for scenario in scenarios:
            alt = item["annual"][scenario]["median"]
            for period_name, start, end in periods:
                indices = [i for i, year in enumerate(years) if start <= year <= end]
                ref_avg = sum(ref[i] for i in indices) / len(indices)
                alt_avg = sum(alt[i] for i in indices) / len(indices)
                change = percent(ref_avg, alt_avg)
                row_values.append(change)
                row_hover.append(
                    f"{item['label']}<br>{labels[scenario]} · {period_name}"
                    f"<br>Change from reference: {percentage_label(change)}"
                )
        rows.append(item["label"])
        z.append(row_values)
        hover.append(row_hover)
    fig = go.Figure(go.Heatmap(
        z=z, x=columns, y=rows, text=hover, hovertemplate="%{text}<extra></extra>",
        colorscale=[[0, "#2776a8"], [.5, "#f5f7f7"], [1, "#bd6b28"]],
        zmid=0, colorbar=dict(title="%", ticksuffix="%"), zsmooth=False,
    ))
    fig.update_layout(
        template="plotly_white", height=max(360, 34 * len(rows) + 130),
        margin=dict(l=10, r=10, t=10, b=95), paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", color="#37535a", size=11),
        xaxis=dict(tickangle=-32, side="bottom"), yaxis=dict(autorange="reversed"),
    )
    return fig


def heading(domain: str, title: str, subtitle: str | None = None) -> None:
    color = COLORS.get(domain, GRAY)
    st.markdown(f'<div class="domain" style="color:{color}">{domain.upper()}</div>', unsafe_allow_html=True)
    st.markdown(f"#### {title}")
    if subtitle:
        st.caption(subtitle)


def method_name(method: str) -> str:
    return {"end": "December value", "mean": "Annual mean", "sum": "Annual total"}.get(method, method)


def evidence_note(note: dict) -> None:
    st.markdown(
        '<div class="reference-note">'
        '<div><b>Definition.</b></div>'
        '<div><b>What is known.</b></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    citations = " · ".join(
        f'[{source["label"]}]({source["url"]})' if source.get("url") else source["label"]
        for source in note["sources"]
    )
    st.caption(f"Evidence sources: {citations}")


def overview(data: dict, content: dict) -> None:
    st.title("Project overview")
    st.markdown(content["intro"])
    st.markdown("### Explore the model outputs")
    cards = [
        ("WEFH system baseline", "Reference trajectories for the water, energy, food and health sectors under the SSP1 sustainability and SSP5 fossil-fuelled development pathways (SSP1–2.6 and SSP5–8.5), simulated with the basin-scale system dynamics model for 2020–2050."),
        ("Policy comparison", "WEFH policy scenarios simulated under both SSP–RCP pathways and compared with the corresponding business-as-usual reference scenario."),
        ("Crocodile catchment case study", "Meso-scale WEF nexus assessment using the extended WRSM2000-WEF model, linking catchment hydrology with water, agricultural production, energy and health indicators across management cases."),
    ]
    st.markdown('<div class="overview-grid">' + ''.join(
        f'<div class="overview-card"><h3>{title}</h3><p>{body}</p></div>'
        for title, body in cards
    ) + '</div>', unsafe_allow_html=True)
    st.markdown("### Project partners")
    columns = st.columns(2, gap="large")
    for column, partners in zip(columns, (content["partners"][:5], content["partners"][5:])):
        with column:
            for filename, name in partners:
                logo, label = st.columns([1, 2], gap="small", vertical_alignment="center")
                with logo:
                    st.image(str(HERE / "assets" / filename), width="stretch")
                with label:
                    st.markdown(f'<div class="partner-name">{name}</div>', unsafe_allow_html=True)


def reference_page(ssp_data: dict, ensemble: dict, content: dict) -> None:
    st.title(content["reference_title"])
    st.caption(content["reference_caption"])
    st.markdown(
        '<div class="ssp-legend"><span class="solid-line"></span> SSP1-2.6'
        '<span class="dashed-line"></span> SSP5-8.5'
        '</div>',
        unsafe_allow_html=True,
    )
    st.info("Blue and red ribbons show each pathway's 10th–90th percentile across 100 repeated model stochastic runs. They exclude climate, crop-area, parameter and structural uncertainty.")
    st.markdown("### System patterns, 2020–2049")
    reference_order = [key for key in REFERENCE_DISPLAY_ORDER if key in ssp_data["indicators"]]
    for start in range(0, len(reference_order), 2):
        cols = st.columns(2, gap="large")
        for col, key in zip(cols, reference_order[start:start + 2]):
            item = ssp_data["indicators"][key]
            with col:
                with st.container(border=True):
                    heading(item["domain"], item["label"], f'{method_name(item["annual_method"])} · {axis_unit(item)}')
                    st.plotly_chart(reference_chart(item, ensemble["indicators"][key], False), width="stretch", config={"displaylogo": False})
                    if key == "human_prevalence_proxy":
                        st.caption("* Prevalence indicator refers to the population at risk.")
    st.caption("Line colors identify sectors; line styles identify SSP pathways. Absolute time-series axes start at zero; fraction indicators use the full 0–100% scale.")
    st.markdown("### Change from the 2020 level")
    st.caption("Near future: 2030 · Mid-century: 2049. Each cell is the percent change from that pathway's 2020 median. Color is capped at ±100% for readability; the printed value is uncapped. A dash means the 2020 level is zero. Water outcomes in individual years can be strongly affected by hydrological variability.")
    domains = sorted({ssp_data["indicators"][key]["domain"] for key in reference_order})
    selected_domains = st.multiselect("Sectors", domains, default=domains, key="baseline_change_domains")
    change_keys = [key for key in reference_order if ssp_data["indicators"][key]["domain"] in selected_domains]
    if change_keys:
        st.plotly_chart(snapshot_heatmap(baseline_change_rows(ensemble, change_keys),
                        ["SSP1 2030", "SSP5 2030", "SSP1 2049", "SSP5 2049"],
                        "Percent change from 2020"), width="stretch", config={"displaylogo": False})
        zero_rows = []
        for key in change_keys:
            item = ensemble["indicators"][key]
            paths = item["paths"]
            if any(abs(paths[scenario]["reference"]["median"][0]) < 1e-9
                   for scenario in ("ssp126", "ssp585")):
                row = {"Indicator": item["label"], "Unit": axis_unit(item)}
                for scenario, label in (("ssp126", "SSP1"), ("ssp585", "SSP5")):
                    series = scaled(item, paths[scenario]["reference"]["median"])
                    row.update({f"{label} {year}": fmt(series[year - 2020])
                                for year in (2020, 2030, 2049)})
                zero_rows.append(row)
        if zero_rows:
            st.caption("Absolute levels for indicators whose 2020 value is zero")
            st.dataframe(pd.DataFrame(zero_rows), hide_index=True, width="stretch")
    st.markdown("### Pathway summary")
    rows = []
    for key in reference_order:
        item = ssp_data["indicators"][key]
        paths = ensemble["indicators"][key]["paths"]
        a1, b1 = paths["ssp126"]["reference"]["median"][0], paths["ssp126"]["reference"]["median"][-1]
        a5, b5 = paths["ssp585"]["reference"]["median"][0], paths["ssp585"]["reference"]["median"][-1]
        if item["kind"] == "fraction":
            a1, b1, a5, b5 = (value * 100 for value in (a1, b1, a5, b5))
            gap = f"{b5-b1:+.2f} pp"
        else:
            gap = fmt(b5-b1)
        rows.append({"Domain": item["domain"], "Indicator": item["label"], "Unit": axis_unit(item),
                     "SSP1 2020": fmt(a1), "SSP1 2049": fmt(b1),
                     "SSP5 2020": fmt(a5), "SSP5 2049": fmt(b5), "2049 SSP5−SSP1": gap})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("The model provides complete annual results through 2049. Values are summed, averaged or taken in December according to the indicator definition. The health outputs are provisional model indicators, not calibrated disease forecasts.")


def legacy_policy_page(data: dict, content: dict) -> None:
    st.title(content["policy_title"])
    st.caption(content["policy_caption"])
    labels = content["scenario_labels"]
    descriptions = content.get("scenario_descriptions", {})
    selected = []
    st.markdown("**Select policy pathways to compare.** The neutral reference is always shown.")
    for scenario in ["centralised_development", "local_resilience", "resource_efficiency"]:
        with st.container():
            if st.checkbox(labels[scenario], value=True, key=f"scenario_{scenario}"):
                selected.append(scenario)
            st.caption(descriptions.get(scenario, ""))
    st.info("These are comparative model trajectories, not precise forecasts. Bands show the 10th–90th percentile across the complete stored trajectories available for each case.")
    st.caption("Left: modelled level · Right: change from reference · Vertical markers: policy start · Shading: 10th–90th percentile")
    policy_order = [key for key in POLICY_COMPARISON_ORDER if key in data["policy"]]
    for key in policy_order:
        item = data["policy"][key]
        with st.container(border=True):
            heading(item["domain"], item["label"], f'{method_name(item["annual_method"])} · {axis_unit(item)}')
            left, right = st.columns(2, gap="medium")
            with left:
                st.caption("A · Modelled output level")
                st.plotly_chart(policy_absolute_chart(item, selected), width="stretch", config={"displaylogo": False}, key=f"policy_abs_{key}")
            with right:
                st.caption("B · Change from reference")
                st.plotly_chart(policy_relative_chart(item, selected), width="stretch", config={"displaylogo": False}, key=f"policy_rel_{key}")
    st.markdown("### Period-average comparison")
    st.caption("Percentage difference from the reference trajectory, averaged over 2020–2030 and 2040–2049. Positive values indicate a higher modelled level; negative values indicate a lower level.")
    if selected:
        st.plotly_chart(
            period_average_heatmap(data, labels, selected, PERIOD_COMPARISON_ORDER),
            width="stretch", config={"displaylogo": False}, key="policy_period_heatmap",
        )
    else:
        st.info("Select at least one policy pathway to show the period comparison.")
    st.markdown("### Absolute output summary")
    absolute_rows = []
    for key in policy_order:
        item = data["policy"][key]
        for scenario in ["ref"] + selected:
            series = item["annual"][scenario]["median"]
            row = {"Pathway": "Reference" if scenario == "ref" else labels[scenario], "Domain": item["domain"], "Indicator": item["label"], "Unit": axis_unit(item)}
            row.update({str(y): fmt(series[y - 2015]) for y in [2020, 2030, 2040, 2049]})
            absolute_rows.append(row)
    st.dataframe(pd.DataFrame(absolute_rows), hide_index=True, width="stretch")
    st.markdown("### Relative change by year")
    rows = []
    for key in policy_order:
        item = data["policy"][key]
        ref = item["annual"]["ref"]["median"]
        for scenario in selected:
            alt = item["annual"][scenario]["median"]
            row = {"Pathway": labels[scenario], "Domain": item["domain"], "Indicator": item["label"]}
            row.update({str(y): percentage_label(percent(ref[y - 2015], alt[y - 2015])) for y in [2020, 2030, 2040, 2049]})
            rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("The summary table reports relative change from the neutral reference for 2020, 2030, 2040 and 2049.")


def ssp_policy_trajectory(item: dict, scenario: str, policy: str, policy_label: str) -> go.Figure:
    fig = chart_base(axis_unit(item), 310)
    fig.update_xaxes(range=[2020, 2049])
    for name, label, color in (("reference", "No policy", "#526a70"),
                               (policy, policy_label, SCENARIO_COLORS[policy])):
        values = item["paths"][scenario][name]
        add_ribbon(fig, item["years"], scaled(item, values["p10"]),
                   scaled(item, values["p90"]),
                   f"rgba({','.join(str(int(color[i:i+2], 16)) for i in (1,3,5))},.14)",
                   f"{label} stochastic range")
        fig.add_trace(go.Scatter(x=item["years"], y=scaled(item, values["median"]),
                                 mode="lines", line=dict(color=color, width=2.8), name=label))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.14, x=0))
    if item["kind"] == "fraction":
        fig.update_yaxes(range=[0, 100], ticksuffix="%", tickformat=".0f")
    else:
        all_values = [v for name in ("reference", policy)
                      for stat in ("p10", "p90") for v in item["paths"][scenario][name][stat]]
        fig.update_yaxes(range=[0, max(1, max(all_values) * 1.06)])
    return fig


def ssp_policy_page(ensemble: dict, content: dict) -> None:
    st.title("Policy pathways under SSP1-2.6 and SSP5-8.5")
    st.caption("WEFH SDM v9.11 with IMAGE crop areas · 2020–2049")
    st.info("The three existing policy packages are run under both SSP pathways. Ribbons show the 10th–90th percentile across 24 stochastic runs for each pathway and policy. They exclude input and structural uncertainty. Policy flags turn on in January 2020; individual equations retain their programmed 2023, 2025 or 2030 ramps.")
    labels = content["scenario_labels"]
    descriptions = content.get("scenario_descriptions", {})
    policies = ["centralised_development", "local_resilience", "resource_efficiency"]
    selected = st.selectbox("Policy package", policies, format_func=lambda key: labels[key])
    st.caption(descriptions.get(selected, ""))
    keys = [key for key in POLICY_COMPARISON_ORDER if key in ensemble["indicators"]]

    st.markdown("### Policy effect compared with the same SSP without policy")
    st.caption("Values are percent differences in the 2030 or 2049 median. A dash means the no-policy level is zero. This isolates the policy effect within each SSP.")
    effect_rows = []
    for key in keys:
        item = ensemble["indicators"][key]
        row = {"Indicator": item["label"]}
        for scenario, label in (("ssp126", "SSP1"), ("ssp585", "SSP5")):
            ref = item["paths"][scenario]["reference"]["median"]
            alt = item["paths"][scenario][selected]["median"]
            for year in (2030, 2049):
                row[f"{label} {year}"] = percent(ref[year - 2020], alt[year - 2020])
        effect_rows.append(row)
    columns = ["SSP1 2030", "SSP5 2030", "SSP1 2049", "SSP5 2049"]
    st.plotly_chart(snapshot_heatmap(effect_rows, columns, "Policy effect versus no policy"),
                    width="stretch", config={"displaylogo": False})

    st.markdown("### Change from the 2020 level")
    st.caption("This view shows the overall pathway change, including SSP conditions and the selected policy. Each series is compared with its own 2020 median.")
    change_rows = []
    for key in keys:
        item = ensemble["indicators"][key]
        row = {"Indicator": item["label"]}
        for scenario, label in (("ssp126", "SSP1"), ("ssp585", "SSP5")):
            for policy, suffix in (("reference", "no policy"), (selected, "with policy")):
                series = item["paths"][scenario][policy]["median"]
                for year in (2030, 2049):
                    row[f"{label} {suffix} {year}"] = percent(series[0], series[year - 2020])
        change_rows.append(row)
    columns = [f"{label} {suffix} {year}" for year in (2030, 2049)
               for label in ("SSP1", "SSP5") for suffix in ("no policy", "with policy")]
    st.plotly_chart(snapshot_heatmap(change_rows, columns, "Percent change from 2020"),
                    width="stretch", config={"displaylogo": False})

    st.markdown("### Trajectories and stochastic ranges")
    indicator = st.selectbox("Indicator to inspect", keys,
                             format_func=lambda key: ensemble["indicators"][key]["label"])
    cols = st.columns(2, gap="large")
    for col, scenario, label in zip(cols, ("ssp126", "ssp585"), ("SSP1-2.6", "SSP5-8.5")):
        with col:
            st.markdown(f"**{label}**")
            st.plotly_chart(ssp_policy_trajectory(ensemble["indicators"][indicator], scenario,
                            selected, labels[selected]), width="stretch", config={"displaylogo": False})
    st.caption("The policy effect is a model response to the defined package, not an estimate of implementation cost or feasibility. Health outputs remain provisional model indicators.")


def aggregate_series(df: pd.DataFrame, case_id: int, aggregation: str, annual: bool) -> pd.Series:
    chosen = df[df["case"] == case_id]
    if chosen.empty:
        return pd.Series(dtype=float)
    period = "year" if annual else "month"
    # Spatial aggregation follows the indicator workbook definition.
    group = chosen.groupby(period)["value"]
    return group.mean() if aggregation == "average" else group.sum()


def map_chart(data: dict, values: dict[str, float], unit: str, difference: bool) -> go.Figure:
    shapes = data["shapes"]
    finite = [abs(v) for v in values.values() if pd.notna(v)]
    maximum = max(finite, default=1) or 1
    fig = go.Figure()
    for shape in shapes:
        code = shape["code"]
        value = values.get(code)
        if value is None or not pd.notna(value):
            fill = "#dce5e6"
        elif difference:
            magnitude = min(abs(value) / maximum, 1)
            fill = f"rgba(49,124,88,{.20 + .65 * magnitude:.3f})" if value >= 0 else f"rgba(183,71,77,{.20 + .65 * magnitude:.3f})"
        else:
            magnitude = min(abs(value) / maximum, 1)
            fill = f"rgba(31,111,165,{.16 + .70 * magnitude:.3f})"
        for ring in shape["rings"]:
            fig.add_trace(go.Scatter(
                x=[p[0] for p in ring], y=[p[1] for p in ring], mode="lines",
                line=dict(color="#c5d2d3", width=.6), fill="toself", fillcolor=fill,
                hovertemplate=f"{code}<br>{fmt(value)} {unit}<extra></extra>", showlegend=False,
            ))
    fig.update_layout(
        height=440, margin=dict(l=5, r=5, t=5, b=5),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), yaxis=dict(visible=False),
    )
    return fig


def crocodile_page(data: dict, content: dict, data_modified_ns: int) -> None:
    st.title(content["crocodile_title"])
    st.caption(content["crocodile_caption"])
    indicators = data["indicators"]
    indicator_id = st.selectbox("Indicator", list(indicators), format_func=lambda key: indicators[key]["name"])
    info = indicators[indicator_id]
    available_cases = list(data["coverage"][indicator_id])
    case_labels = {key: data["cases"][key]["measure"] for key in available_cases}
    ref_case = st.selectbox("Workbook case", available_cases, format_func=lambda key: case_labels[key])
    alternative = [key for key in available_cases if key != ref_case]
    alt_case = st.selectbox("Compare with", [None] + alternative, format_func=lambda key: "None" if key is None else case_labels[key])
    df = load_results(data_modified_ns)
    subset = df[df["indicator"] == int(indicator_id)]
    locations = sorted(subset["location"].dropna().unique().tolist())
    location = st.selectbox("Location", ["All locations"] + locations)
    annual = st.toggle("Annual view", value=True)
    series_df = subset if location == "All locations" else subset[subset["location"] == location]
    ref = aggregate_series(series_df, int(ref_case), info["aggregation"], annual)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ref.index, y=ref.values, mode="lines", line=dict(color="#1f6fa5", width=2.6), name=case_labels[ref_case]))
    if alt_case is not None:
        alt = aggregate_series(series_df, int(alt_case), info["aggregation"], annual)
        fig.add_trace(go.Scatter(x=alt.index, y=alt.values, mode="lines", line=dict(color="#b67a1d", width=2.6), name=case_labels[alt_case]))
    fig.update_layout(template="plotly_white", height=380, margin=dict(l=40, r=20, t=25, b=45), hovermode="x unified", legend=dict(orientation="h", y=1.16))
    fig.update_xaxes(title_text="Year" if annual else "Month", showgrid=False)
    fig.update_yaxes(title_text=info["unit"], gridcolor="#e7eeee", tickformat="~s")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.markdown("### Catchment view")
    if alt_case is None:
        spatial = subset[subset["case"] == int(ref_case)].groupby("location")["value"].mean().to_dict()
        st.caption(f"Average {info['name'].lower()} by available catchment location for the selected workbook case.")
    else:
        relevant = subset[subset["case"].isin([int(ref_case), int(alt_case)])]
        paired = relevant.pivot_table(index=["location", "month"], columns="case", values="value", aggfunc="mean")
        paired = paired.dropna(subset=[int(ref_case), int(alt_case)])
        spatial = (paired[int(alt_case)] - paired[int(ref_case)]).groupby(level="location").mean().to_dict()
        st.caption("Average difference between cases at locations and months where both have data. Green indicates an increase; red indicates a decrease.")
    st.plotly_chart(map_chart(data, spatial, info["unit"], alt_case is not None), width="stretch", config={"displaylogo": False})
    st.caption("Workbook case labels are shown as supplied. Coverage and time periods vary by indicator; a blank area has no matched data.")


def main() -> None:
    st.set_page_config(page_title="CONNEXION modelling dashboard", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
    require_access_key()
    st.markdown("""
        <style>
        .block-container{max-width:1500px;padding-top:2rem;padding-bottom:3rem}
        h1{font-size:2.15rem!important;letter-spacing:-.03em;color:#183e45}
        h3,h4{color:#204c54}
        .domain{font-weight:800;letter-spacing:.12em;font-size:.72rem;margin-bottom:.1rem}
        .overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:1rem 0}
        .overview-card{min-height:145px;padding:1.1rem 1.25rem;background:#fff;border:1px solid #dce8e6;border-top:4px solid #237080;border-radius:9px}
        .overview-card h3{font-size:1.1rem;margin:.15rem 0 .7rem}
        .overview-card p{font-size:.93rem;line-height:1.45;color:#4d6569;margin:0}
        .partner-name{font-size:.9rem;color:#3d5b62;font-weight:600;line-height:1.35}
        .reference-note{font-size:.84rem;line-height:1.42;color:#36575e;border-top:1px solid #e4ecec;padding-top:.55rem}
        .reference-note div+div{margin-top:.32rem}
        .ssp-legend{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;margin:.8rem 0 1rem;color:#37535a;font-weight:600}
        .ssp-legend span.solid-line,.ssp-legend span.dashed-line{display:inline-block;width:32px;border-top:3px solid #526a70;margin-left:1.1rem}
        .ssp-legend span.solid-line{margin-left:0}
        .ssp-legend span.dashed-line{border-top-style:dashed}
        [data-testid="stSidebar"]{background:#eaf2f1}
        [data-testid="stSidebar"] img{background:#fff;border-radius:8px;padding:5px}
        [data-testid="stImageCaption"]{font-size:.77rem;text-align:center;color:#536c71}
        </style>
    """, unsafe_allow_html=True)
    content = load_content()
    data_modified_ns = (HERE / "data.json").stat().st_mtime_ns
    ssp_modified_ns = (HERE / "ssp_baseline.json").stat().st_mtime_ns
    ensemble_path = HERE / "ssp_policy_ensemble.json"
    data = load_data(data_modified_ns)
    ssp_data = load_ssp_data(ssp_modified_ns)
    ensemble = load_policy_ensemble(ensemble_path.stat().st_mtime_ns) if ensemble_path.exists() else None
    with st.sidebar:
        st.image(str(HERE / "assets" / "CONNEXION  logo.jpg"), width="stretch")
        st.markdown("**Modelling dashboard**")
        section = st.radio("Section", ["Project overview", "WEFH system baseline", "Policy comparison", "Crocodile catchment"], label_visibility="collapsed")
    if section == "Project overview":
        overview(data, content)
    elif section == "WEFH system baseline":
        if ensemble is None:
            st.warning("The SSP policy ensemble is being generated. Refresh when it completes.")
        else:
            reference_page(ssp_data, ensemble, content)
    elif section == "Policy comparison":
        if ensemble is None:
            st.warning("The SSP policy ensemble is being generated. Refresh when it completes.")
        else:
            ssp_policy_page(ensemble, content)
    else:
        crocodile_page(data, content, data_modified_ns)


if __name__ == "__main__":
    main()
