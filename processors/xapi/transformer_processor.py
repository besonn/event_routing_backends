"""
xAPI processor for transforming and routing events.
"""
import json
from logging import getLogger
from celery import shared_task
from eventtracking.processors.exceptions import NoBackendEnabled

from event_routing_backends.processors.mixins.base_transformer_processor import BaseTransformerProcessorMixin
from event_routing_backends.processors.xapi import XAPI_EVENT_LOGGING_ENABLED, XAPI_EVENTS_ENABLED
from event_routing_backends.processors.xapi.registry import XApiTransformersRegistry

logger = getLogger(__name__)
xapi_logger = getLogger('xapi_tracking')


class XApiProcessor(BaseTransformerProcessorMixin):
    """
    xAPI Processor for transforming and routing events.

    This processor first transform the event using the registered transformer
    and then route the events through the configured routers.

    Every router configured to be used MUST support the transformed event type.
    """

    registry = XApiTransformersRegistry
    # 修改了这里
    @shared_task(bind=True, queue='xapi')
    def transform_event(self, event):
        """
        Transform the event into IMS xAPI format.

        Arguments:
            event (dict):   Event to be transformed.

        Returns:
            ANY:            transformed event

        Raises:
            Any Exception
        """
        if not XAPI_EVENTS_ENABLED.is_enabled():
            raise NoBackendEnabled

        transformed_events = super().transform_event(event)
        if not transformed_events:
            return None

        if not isinstance(transformed_events, list):
            transformed_events = [transformed_events]

        returned_events = []
        for transformed_event in transformed_events:
            event_json = transformed_event.to_json()

            if not transformed_event.object or not transformed_event.object.id:
                logger.debug('xAPI statement of edx event "{}" has no object id: {}'.format(event["name"], event_json))
                return None

            #if XAPI_EVENT_LOGGING_ENABLED.is_enabled():
               # xapi_logger.info(event_json)

            logger.debug('xAPI statement of edx event "{}" is: {}'.format(event["name"], event_json))
            returned_events.append(json.loads(event_json))       
        return returned_events
