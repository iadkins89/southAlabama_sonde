from dash import html, register_page
import dash_bootstrap_components as dbc

register_page(
	__name__,
	top_nav=True,
	path='/about',
	title="About | South Alabama Telemetry"
)

STEPS = [
	("bi-water", "Measure",
	 "Sonde and gauge sensors record water conditions along the coast."),
	("bi-broadcast", "Transmit",
	 "Readings travel by LoRaWAN radio or Iridium satellite, so remote sites stay connected."),
	("bi-shield-check", "Check",
	 "Tide gauge water levels pass through automated QARTOD quality tests as they arrive."),
	("bi-graph-up", "Publish",
	 "Results appear here on maps and graphs, ready to explore or download as CSV files."),
]

FLAGS = [
	("bi-check-circle-fill", "var(--good)", "Passed", "The reading cleared every test that could be run on it."),
	("bi-exclamation-diamond-fill", "var(--warn)", "Suspect",
	 "Something looks unusual, so the reading stays on the graph as an orange diamond."),
	("bi-x-circle-fill", "var(--bad)", "Failed",
	 "The reading is left off the graphs, but it is still included in CSV downloads."),
]


def layout():
	return html.Div([
		html.Section(
			dbc.Container([
				html.H1("Coastal Telemetry Project"),
				html.P("Live measurements from coastal sensors, built at the University of South Alabama "
				       "to help understand and preserve coastal ecosystems."),
			]),
			className="about-hero"
		),
		dbc.Container([
			html.Section([
				html.H2("How data reaches this site"),
				html.P("Every reading makes the same trip from the water to your screen.", className="about-lead"),
				html.Div(
					[html.Div([html.I(className=f"bi {icon}"), html.H3(title), html.P(text)],
					          className="surface-card flow-step")
					 for icon, title, text in STEPS],
					className="flow-steps"
				),
			], className="about-section"),

			html.Section([
				html.H2("Reading the data"),
				html.P(["Water levels follow the ",
				        html.A("QARTOD", href="https://ioos.noaa.gov/project/qartod/", target="_blank", rel="noopener"),
				        " standard for real-time quality control. Its tests look for readings outside "
				        "a sensor's range, sudden spikes, unusually fast changes and values stuck "
				        "at one number. Each reading then gets a result:"],
				       className="about-lead"),
				html.Div(
					[html.Div(
						[html.Div([html.I(className=f"bi {icon}", style={"color": color}), name], className="flag-name"),
						 html.Div(text, className="flag-text")],
						className="surface-card flag-row"
					) for icon, color, name, text in FLAGS],
					className="flag-list"
				),
			], className="about-section"),

			html.Section([
				html.H2("How water level is measured"),
				html.P("A tide gauge measures the distance down to the water. Subtracting that from the "
				       "gauge's surveyed height gives the water level on the NAVD88 vertical datum.",
				       className="about-lead mb-1"),
				html.Div("Water level = gauge elevation − distance to water", className="formula"),
			], className="about-section"),

			html.Section([
				html.H2("Get involved"),
				html.P(["We invite students, researchers and anyone passionate about the coast to take part, "
				        "whether in field deployment, data analysis or technology development. Reach out at ",
				        html.A("iea2021@jagmail.southalabama.edu", href="mailto:iea2021@jagmail.southalabama.edu"),
				        "."], className="about-lead"),
			], className="about-section pb-5"),
		]),
	], className="page")
