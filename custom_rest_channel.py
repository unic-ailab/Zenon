import asyncio
import inspect
import json
from sanic import Sanic, Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn
from asyncio import Queue, CancelledError
import logging
from http import HTTPStatus

import rasa.utils.endpoints
from rasa.core.channels.rest import (
    RestInput,
    CollectingOutputChannel,
    UserMessage,
)
from connect_to_iam import VerifyAuthentication

logger = logging.getLogger(__name__)

class RestMetadataInput(RestInput):

    @staticmethod
    def name() -> Text:
        """Name of your custom channel."""
        return "rest_metadata"
    
    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        # noinspection PyUnusedLocal
        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @custom_webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:
            sender_id = await self._extract_sender(request)
            text = self._extract_message(request)
            should_use_stream = rasa.utils.endpoints.bool_arg(
                request, "stream", default=False
            )
            input_channel = self._extract_input_channel(request)
            metadata = self.get_metadata(request)
            accessToken = metadata.get("accessToken", None)

            if accessToken:
                # Verify the provided access token
                verification_status = VerifyAuthentication().verification(access_token=accessToken)
                if verification_status == 200:
                    if should_use_stream:
                        return response.stream(
                            self.stream_response(
                                on_new_message, text, sender_id, input_channel, metadata
                            ),
                            content_type="text/event-stream",
                        )
                    else:
                        collector = CollectingOutputChannel()
                        # noinspection PyBroadException
                        try:
                            await on_new_message(
                                UserMessage(
                                    text,
                                    collector,
                                    sender_id,
                                    input_channel=input_channel,
                                    metadata=metadata,
                                )
                            )
                        except CancelledError:
                            logger.error(
                                f"Message handling timed out for " f"user message '{text}'."
                            )
                        except Exception:
                            logger.exception(
                                f"An exception occured while handling "
                                f"user message '{text}'."
                            )
                        return response.json(collector.messages)
                else:
                    return response.text("You are not authorized", status=HTTPStatus.UNAUTHORIZED)
            else:
                return response.text("You are not authorized", status=HTTPStatus.UNAUTHORIZED)

        return custom_webhook    
    
    def stream_response(
        self,
        on_new_message: Callable[[UserMessage], Awaitable[None]],
        text: Text,
        sender_id: Text,
        input_channel: Text,
        metadata: Optional[Dict[Text, Any]],
    ) -> Callable[[Any], Awaitable[None]]:
        async def stream(resp: Any) -> None:
            q = Queue()
            task = asyncio.ensure_future(
                self.on_message_wrapper(
                    on_new_message, text, q, sender_id, input_channel, metadata
                )
            )
            while True:
                result = await q.get()
                if result == "DONE":
                    break
                else:
                    await resp.write(json.dumps(result) + "\n")
            await task

        return stream    
    
    def get_metadata(self, req: Request) -> Optional[Dict[Text, Any]]:
        """Extracts the metadata from a user message.
        Args:
            request: A `Request` object
        Returns:
            Metadata extracted from the sent event payload.
        """
        return req.json.get("metadata", None)