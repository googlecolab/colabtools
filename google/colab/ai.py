"""Colab AI library.

Example:
  from google.colab import ai
  ai.generate_text("What is the capital of France?")
"""

__all__ = ['generate_text']

import os as _os
from google.colab import userdata as _userdata
from openai import OpenAI as _OpenAI  # pytype: disable=import-error


def generate_text(prompt: str, model_name='google/gemini-2.0-flash') -> str:
  """Generates text using the given prompt and model.

  Args:
    prompt: The prompt to use for text generation.
    model_name: The name of the model to use.

  Returns:
    The generated text.
  """
  model_proxy_token = _get_model_proxy_token()

  client = _OpenAI(
      # TODO: b/412340050 - Set _OpenAI_BASE_URL based on environment
      # prod or staging.
      base_url='https://mp-staging.kaggle.net/models/openapi',
      api_key=model_proxy_token,
  )

  completion = client.chat.completions.create(
      model=model_name, messages=[{'role': 'user', 'content': prompt}]
  )
  return completion.choices[0].message.content


def _get_model_proxy_token() -> str:
  """Gets the model proxy token from user secrets.

  Returns:
    The model proxy token.
  """
  if 'MODEL_PROXY_API_KEY' in _os.environ:
    return _os.environ['MODEL_PROXY_API_KEY']

  model_proxy_token = _userdata.get('MODEL_PROXY_API_KEY')
  _os.environ['MODEL_PROXY_API_KEY'] = model_proxy_token
  return model_proxy_token
