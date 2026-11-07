from dash import html


def create_footer():
    return html.Footer(
        html.Div(
            [
                html.Div(
                    [html.Strong("University of South Alabama"), html.Span("Coastal Engineering")],
                    className="footer-block",
                ),
                html.Div(
                    [html.Span("Ian Adkins"),
                     html.A("iea2021@jagmail.southalabama.edu", href="mailto:iea2021@jagmail.southalabama.edu")],
                    className="footer-block",
                ),
                html.A(
                    [html.I(className="bi bi-github"), "Source code"],
                    href="https://github.com/iadkins89/southAlabama_sonde",
                    target="_blank",
                    rel="noopener",
                    className="footer-link",
                ),
            ],
            className="footer-content",
        ),
        id="footer",
    )
