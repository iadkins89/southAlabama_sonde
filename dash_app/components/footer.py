from dash import html

def create_footer():
    footer = html.Footer(
        children=[
            html.Div(
                className="footer-content",
                children=[
                    # Left Section: Address
                    html.Div(
                        className="footer-left",
                        children=[
                            html.P("University of South Alabama"),
                            html.P("Coastal Engineering"),
                        ],
                    ),
                    # Middle Section: Name and Email
                    html.Div(
                        className="footer-middle",
                        children=[
                            html.P("Ian Adkins"),
                            html.P("iea2021@jagmail.southalabama.edu"),
                        ],
                    ),
                    # Right Section: GitHub Link with Image
                    html.Div(
                        className="footer-right",
                        children=[
                            html.A(
                                href="https://github.com/iadkins89/southAlabama_sonde",
                                target="_blank",
                                children=[
                                    html.Img(
                                        src="/assets/github-icon.png",  # Place the image in the "assets" folder
                                        alt="GitHub",
                                        className="github-icon",
                                    )
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
        id="footer",
    )
    return footer