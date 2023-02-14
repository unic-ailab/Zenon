# from rasa.core.channels.rest import RestInput
# from sanic.request import Request
# from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn, Union


# class RestMetadataInput(RestInput):
#     def name(name) -> Text:
#         """Name of your custom channel."""
#         return "rest_metadata"

#     def get_metadata(self, req: Request) -> Optional[Dict[Text, Any]]:
#         """Extracts the metadata from a user message.
#         Args:
#             request: A `Request` object
#         Returns:
#             Metadata extracted from the sent event payload.
#         """
#         return req.json.get("metadata", None)