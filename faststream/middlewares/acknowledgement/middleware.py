import logging
from typing import TYPE_CHECKING, Any, Optional

from faststream.exceptions import (
    AckMessage,
    HandlerException,
    NackMessage,
    RejectMessage,
)
from faststream.middlewares.acknowledgement.conf import AckPolicy
from faststream.middlewares.base import BaseMiddleware

if TYPE_CHECKING:
    from types import TracebackType

    from faststream._internal.basic_types import AnyDict
    from faststream._internal.context.repository import ContextRepo
    from faststream.message import StreamMessage


class BaseAcknowledgementMiddleware(BaseMiddleware):
    def __init__(
        self,
        ack_policy: AckPolicy,
        extra_options: "AnyDict",
        msg: Optional[Any],
        context: "ContextRepo",
        message: Optional["StreamMessage[Any]"] = None,
    ) -> None:
        super().__init__(msg, context=context)
        self.ack_policy = ack_policy
        self.extra_options = extra_options
        self.logger = context.get_local("logger")
        self.message = message

    async def on_consume(self, msg: "StreamMessage[Any]") -> "StreamMessage[Any]":
        self.message = msg
        return msg

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_val: Optional[BaseException] = None,
        exc_tb: Optional["TracebackType"] = None,
    ) -> Optional[bool]:
        if self.ack_policy is AckPolicy.DO_NOTHING:
            return False

        if not exc_type:
            await self.__ack()

        elif isinstance(exc_val, HandlerException):
            if isinstance(exc_val, AckMessage):
                await self.__ack(**exc_val.extra_options)

            elif isinstance(exc_val, NackMessage):
                await self.__nack(**exc_val.extra_options)

            elif isinstance(exc_val, RejectMessage):  # pragma: no branch
                await self.__reject(**exc_val.extra_options)

            # Exception was processed and suppressed
            return True

        elif self.ack_policy is AckPolicy.REJECT_ON_ERROR:
            await self.__reject()

        elif self.ack_policy is AckPolicy.NACK_ON_ERROR:
            await self.__nack()

        # Exception was not processed
        return False

    async def __ack(self, **exc_extra_options: Any) -> None:
        try:
            await self.message.ack(**exc_extra_options, **self.extra_options)
        except Exception as er:
            if self.logger is not None:
                self.logger.log(logging.ERROR, er, exc_info=er)

    async def __nack(self, **exc_extra_options: Any) -> None:
        try:
            await self.message.nack(**exc_extra_options, **self.extra_options)
        except Exception as er:
            if self.logger is not None:
                self.logger.log(logging.ERROR, er, exc_info=er)

    async def __reject(self, **exc_extra_options: Any) -> None:
        try:
            await self.message.reject(**exc_extra_options, **self.extra_options)
        except Exception as er:
            if self.logger is not None:
                self.logger.log(logging.ERROR, er, exc_info=er)


class AcknowledgementMiddleware:
    def __init__(self, ack_policy: AckPolicy, extra_options: "AnyDict") -> None:
        self.ack_policy = ack_policy
        self.extra_options = extra_options

    def __call__(self, msg: Optional[Any], context: "ContextRepo") -> Any:
        return BaseAcknowledgementMiddleware(
            ack_policy=self.ack_policy,
            extra_options=self.extra_options,
            msg=msg,
            context=context,
        )
