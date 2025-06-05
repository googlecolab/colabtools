"""Colab AI library.

Example Usage:

1.  **Basic Text Generation:**
    ```
    from google.colab import ai
    response = ai.generate_text("What is the capital of France?")
    print(response)
    ```

2.  **Streaming Text Generation:**
    ```
    from google.colab import ai
    stream = ai.generate_text("Tell me a short story.", stream=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='')
    ```

3.  **Using a Different Model:**
    ```
    from google.colab import ai
    response = ai.generate_text("Explain quantum physics.",
    model_name="google/gemini-2.5-flash")
    print(response)
    ```
"""

import os as _os

from google.colab import errors as _errors
from google.colab import runtime as _runtime
from google.colab import userdata as _userdata
from openai import OpenAI as _OpenAI  # pytype: disable=import-error
from openai.types.chat import ChatCompletionChunk as _ChatCompletionChunk  # pytype: disable=import-error
import requests as _requests

__all__ = ['generate_text', 'get_available_models', 'ModelProxyServiceError']


class ModelProxyServiceError(Exception):
  """Custom exception for errors related to the model proxy service."""

  pass


def generate_text(
    prompt: str,
    model_name: str = 'google/gemini-2.0-flash',
    stream: bool = False,
) -> str | _ChatCompletionChunk:
  """Generates text using the given prompt and model.

  Args:
    prompt: The input text or question.
    model_name: The name of the model to use (e.g., 'google/gemini-2.0-flash').
    stream: If `True`, the response will be streamed back in chunks. If `False`,
      the complete generated text will be returned at once.

  Returns:
    If `stream` is `True`, an `iterator of ChatCompletionChunk` is returned. If
    `stream` is `False`, a string containing the complete generated text is
    returned.
  """

  if not _runtime.IS_EXTERNAL_COLAB:
    raise _errors.RuntimeManagementError(
        'This operation is only supported in external Colab.'
    )

  model_proxy_token = _get_model_proxy_token()

  client = _OpenAI(
      base_url=f'{_get_model_proxy_host()}/models/openapi',
      api_key=model_proxy_token,
  )

  response = client.chat.completions.create(
      model=model_name,
      messages=[{'role': 'user', 'content': prompt}],
      stream=stream,
  )

  if stream:
    return response
  return response.choices[0].message.content


def _get_model_proxy_token() -> str:
  """Gets the model proxy token from user secrets or environment variables.

  Returns:
    The model proxy token.
  """
  if 'MODEL_PROXY_API_KEY' in _os.environ:
    return _os.environ['MODEL_PROXY_API_KEY']

  model_proxy_token = _userdata.get('MODEL_PROXY_API_KEY')
  _os.environ['MODEL_PROXY_API_KEY'] = model_proxy_token
  return model_proxy_token


def _get_model_proxy_host() -> str:
  """Gets the model proxy host from environment variable."""
  return _os.environ.get('MODEL_PROXY_HOST', '')


def get_available_models() -> list[str]:
  """Gets the list of available models."""

  if not _runtime.IS_EXTERNAL_COLAB:
    raise _errors.RuntimeManagementError(
        'This operation is only supported in external Colab.'
    )

  try:
    model_proxy_token = _get_model_proxy_token()
    response = _requests.get(
        f'{_get_model_proxy_host()}/models',
        headers={
            'Authorization': f'Bearer {model_proxy_token}',
        },
    )
    return [m['id'] for m in response.json()['data']]

  except _requests.exceptions.JSONDecodeError as json_err:
    raise ModelProxyServiceError(
        'Failed to decode JSON response from the model proxy service.'
    ) from json_err

  except KeyError as key_err:
    raise ModelProxyServiceError(
        'API response from the model proxy service is missing expected key:'
        f' {key_err}'
    ) from key_err
