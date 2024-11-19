from dash import dcc, html, register_page
import dash_bootstrap_components as dbc

register_page(
	__name__,
	top_nav=True,
	path='/about'
)

def layout():
	layout = dbc.Container(
	[
		dbc.Row(
			dbc.Col(
				html.H1("About Us", style={"margin-top": "2.7%", "margin-left": "14.5%", "margin-right": "14.5%"}),
			width=12
			)
	),
		dbc.Row(
			dbc.Col(
				html.P(
					"Welcome to the Coastal Telemetry Project at the University of South Alabama. "
					"Our mission is to innovate and implement cutting-edge telemetry devices designed to monitor and protect our coastal environments. "
					"Utilizing the advanced capabilities of LoRaWAN (Long Range Wide Area Network) technology, our devices provide real-time data collection and transmission over vast distances, making them ideal for remote and hard-to-reach coastal areas.",
				className="lead",
				style={"margin-left": "14.5%", "margin-right": "14.5%"}
			),
		width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.H2("Our Mission", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
				html.P(
				"Our primary goal is to enhance the understanding and preservation of coastal ecosystems through accurate and reliable telemetry. By deploying these advanced devices, we aim to:",
				className="lead",
				style={"margin-left": "14.5%", "margin-right": "14.5%"}
			),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.Ul(
			[
				html.Li("Monitor environmental parameters such as water quality, temperature, and salinity.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
				html.Li("Track the movement and behavior of marine and coastal wildlife.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
				html.Li("Support scientific research and conservation efforts with high-quality data.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
				html.Li("Provide valuable information to stakeholders, including researchers, environmental agencies, and the general public.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
			]
		),
		width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.H2("Our Technology", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.P(
				"Our telemetry devices leverage LoRaWAN technology to offer:",
				className="lead",
				style={"margin-left": "14.5%", "margin-right": "14.5%"}
			),
		width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.Ul(
					[
						html.Li("Long-Range Communication: Capable of transmitting data over several kilometers, ensuring coverage in remote areas.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
						html.Li("Low Power Consumption: Designed to operate for extended periods without the need for frequent battery replacements.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
						html.Li("Scalability: Easily expandable networks to accommodate additional sensors and devices.", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
					]
			),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.H2("Get Involved", tyle={"margin-left": "14.5%", "margin-right": "14.5%"}),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.P(
				"We invite students, researchers, and anyone passionate about environmental conservation to get involved with our project. Whether you're interested in field deployment, data analysis, or technological development, there's a place for you in our team.",
				className="lead",
				style={"margin-left": "14.5%", "margin-right": "14.5%"}
			),
		width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.H2("Contact Us", style={"margin-left": "14.5%", "margin-right": "14.5%"}),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.P(
				"For more information about our project, collaborations, or any inquiries, please feel free to reach out to us at:",
				className="lead",
				style={"margin-left": "14.5%", "margin-right": "14.5%"}
			),
		width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.P(
				[
					"Email: ",
					html.A("iea2021@jagmail.southalabama.edu", href="mailto:iea2021@jagmail.southalabama.edu"),
				],
				className="lead",
				style={"margin-left": "14.5%", "margin-right": "14.5%"}
			),
			width=12
		)
	),
	dbc.Row(
		dbc.Col(
			html.P(
					[
					"You can also explore our latest developments and access our open-source telemetry dashboard on GitHub: ",
					html.A("Telemetry Dashboard GitHub Repository", href="https://github.com/iadkins89/southAlabama_sonde"),
					],
					className="lead",
					style={"margin-left": "14.5%", "margin-right": "14.5%"}
				),
			width=12
		)
	),
	],
		fluid=True
	)

	return layout