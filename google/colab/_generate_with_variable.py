"""Helper to generate code targeting dataframes."""

import uuid
import IPython

_ICON_SVG = """
  <svg xmlns="http://www.w3.org/2000/svg" height="24px"viewBox="0 0 24 24"
       width="24px">
    <path d="M7,19H8.4L18.45,9,17,7.55,7,17.6ZM5,21V16.75L18.45,3.32a2,2,0,0,1,2.83,0l1.4,1.43a1.91,1.91,0,0,1,.58,1.4,1.91,1.91,0,0,1-.58,1.4L9.25,21ZM18.45,9,17,7.55Zm-12,3A5.31,5.31,0,0,0,4.9,8.1,5.31,5.31,0,0,0,1,6.5,5.31,5.31,0,0,0,4.9,4.9,5.31,5.31,0,0,0,6.5,1,5.31,5.31,0,0,0,8.1,4.9,5.31,5.31,0,0,0,12,6.5,5.46,5.46,0,0,0,6.5,12Z"/>
  </svg>"""


def get_html(dataframe) -> str:
  """Returns the html to generate for a dataframe."""
  if not IPython.get_ipython():
    return ""
  namespace = IPython.get_ipython().user_ns

  variable_name = None
  for varname, var in namespace.items():
    if dataframe is var and not varname.startswith("_"):
      variable_name = varname
      break

  if not variable_name:
    return ""

  button_id = "id_" + str(uuid.uuid4())

  return """
  <div id="{button_id}">
    <style>
      .colab-df-container {{
        display:flex;
        flex-wrap:wrap;
        gap: 12px;
      }}

      .colab-df-generate {{
        background-color: #E8F0FE;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        display: none;
        fill: #1967D2;
        height: 32px;
        padding: 0 0 0 0;
        width: 32px;
      }}

      .colab-df-generate:hover {{
        background-color: #E2EBFA;
        box-shadow: 0px 1px 2px rgba(60, 64, 67, 0.3), 0px 1px 3px 1px rgba(60, 64, 67, 0.15);
        fill: #174EA6;
      }}

      [theme=dark] .colab-df-generate {{
        background-color: #3B4455;
        fill: #D2E3FC;
      }}

      [theme=dark] .colab-df-generate:hover {{
        background-color: #434B5C;
        box-shadow: 0px 1px 3px 1px rgba(0, 0, 0, 0.15);
        filter: drop-shadow(0px 1px 2px rgba(0, 0, 0, 0.3));
        fill: #FFFFFF;
      }}
    </style>
    <div class="colab-df-container">
      <button class="colab-df-generate" onclick="generateWithVariable('{variable_name}')"
              title="Generate code using this dataframe."
              style="display:none;">
        {icon}
      </button>
      <script>
       (() => {{
        const buttonEl =
          document.querySelector('#{button_id} button.colab-df-generate');
        buttonEl.style.display =
          google.colab.kernel.accessAllowed ? 'block' : 'none';

        buttonEl.onclick = () => {{
          google.colab.notebook.generateWithVariable('{variable_name}');
        }}
       }})();
      </script>
    </div>
  </div>
  """.format(
      icon=_ICON_SVG,
      variable_name=variable_name,
      button_id=button_id,
  )
