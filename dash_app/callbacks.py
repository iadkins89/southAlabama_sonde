from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objs as go
from server.models import query_data, save_data_to_csv
from plotly.subplots import make_subplots

def register_callbacks(app):
    @app.callback(
        Output('multi-sensor-graph', 'figure'),
        [Input('date-picker-range', 'start_date'),
         Input('date-picker-range', 'end_date'),
        Input('table-dropdown', 'value')]
    )
    def update_multi_sensor_graph(start_date, end_date, sensor_name):

        data = query_data(start_date, end_date, sensor_name)

        timestamps = [d.timestamp for d in data]
        temperatures = [d.temperature for d in data]
        dissolved_oxygen = [d.dissolved_oxygen for d in data]
        conductivity = [d.conductivity for d in data]
        turbidity = [d.turbidity for d in data]
        ph_values = [d.ph for d in data]

        # Create subplots with shared x-axis
        fig = make_subplots(
            rows=5, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03
        )

        # Add traces for each parameter
        fig.add_trace(go.Scatter(x=timestamps, y=dissolved_oxygen, mode='lines+markers', name='Dissolved Oxygen', line={'color': 'lightblue'}, marker={'size': 2}, fill='tozeroy', fillcolor='rgba(173, 216, 230, 0.3)', hoverlabel=dict(font_color="black")), row=1, col=1)
        fig.add_trace(go.Scatter(x=timestamps, y=conductivity, mode='lines+markers', name='Conductivity', line={'color': 'mediumaquamarine'}, marker={'size': 2}, fill='tozeroy', fillcolor='rgba(102, 205, 170, 0.3)', hoverlabel=dict(font_color="black")), row=2, col=1)
        fig.add_trace(go.Scatter(x=timestamps, y=turbidity, mode='lines+markers', name='Turbidity', line={'color': 'mediumpurple'}, marker={'size': 2}, fill='tozeroy', fillcolor='rgba(147, 112, 219, 0.3)', hoverlabel=dict(font_color="black")), row=3, col=1)
        fig.add_trace(go.Scatter(x=timestamps, y=ph_values, mode='lines+markers', name='pH', line={'color': 'coral'}, marker={'size': 2}, fill='tozeroy', fillcolor='rgba(255, 127, 80, 0.3)', hoverlabel=dict(font_color="black")), row=4, col=1)
        fig.add_trace(go.Scatter(x=timestamps, y=temperatures, mode='lines+markers', name='Temperature', line={'color': 'lightsalmon'}, marker={'size': 2}, fill='tozeroy', fillcolor='rgba(255, 160, 122, 0.3)', hoverlabel=dict(font_color="black")), row=5, col=1)

        # Update layout for each subplot
        fig.update_xaxes(showspikes=True, spikecolor="grey",spikemode="across")
        fig.update_yaxes(showspikes=True, spikecolor="grey")

        fig.update_yaxes(title_text="(mg/L)", range=[0,20], row=1, col=1, side="right")
        fig.update_yaxes(title_text="(mS/cm)",range=[0,20], row=2, col=1, side="right")
        fig.update_yaxes(title_text="(NTU)",range=[0,50], row=3, col=1, side="right")
        fig.update_yaxes(title_text="pH", range=[0, 14], row=4, col=1, side="right")
        fig.update_yaxes(title_text="(°C)", range=[0, 38], row=5, col=1, side="right")

        # Add annotations for labels on the left side
        annotations = [
            dict(xref='paper', yref='y1', x=-0.02, y=10, text="Dissolved Oxygen", showarrow=False, textangle=-90),
            dict(xref='paper', yref='y2', x=-0.02, y=10, text="Conductivity", showarrow=False, textangle=-90),
            dict(xref='paper', yref='y3', x=-0.02, y=25, text="Turbidity", showarrow=False, textangle=-90),
            dict(xref='paper', yref='y4', x=-0.02, y=7, text="pH", showarrow=False, textangle=-90),
            dict(xref='paper', yref='y5', x=-0.02, y=19, text="Temperature", showarrow=False, textangle=-90),
        ]
        fig.update_layout(annotations=annotations)

        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',  # Set background color to transparent or a specific color
            paper_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=100, r=100, t=50, b=50),  
            height=800, 
            showlegend=False,
            hoverlabel=dict(
                font_color="black"  # Change the hover text color to black
            )
        )

        return fig

    @app.callback(
        Output('confirm-dialog', 'displayed'),
        Output('confirm-dialog', 'message'),
        Output('download-dataframe-csv', 'data'),
        [Input('set-filename-btn', 'n_clicks')],
        [State('date-picker-range', 'start_date'),
         State('date-picker-range', 'end_date'),
         State('csv-filename', 'value'),
         State('table-dropdown', 'value')]
    )
    def update_output(n_clicks, start_date, end_date, filename, sensor_name):
        if n_clicks is None:
            raise PreventUpdate
        else:
            if not start_date or not end_date or not filename:
                return True, 'Please provide a valid date range and filename.', None
            data = query_data(start_date, end_date, sensor_name)
            if not data:
                return True, 'No data found for the given date range.', None

            saved_csv_file = save_data_to_csv(data, f"{filename}.csv")
            return False, '', dict(content=saved_csv_file, filename=f"{filename}.csv")
        return False, '', None
