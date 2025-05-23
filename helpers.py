"""
Helper utilities for event transformers.
"""
import datetime
import logging
import uuid
from urllib.parse import parse_qs, urlparse

from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth import get_user_model
from isodate import duration_isoformat
from opaque_keys.edx.keys import CourseKey

logger = logging.getLogger(__name__)

# Imported from edx-platform
try:
    from common.djangoapps.student.models import get_potentially_retired_user_by_username
    from openedx.core.djangoapps.content.course_overviews.api import get_course_overviews
    from openedx.core.djangoapps.external_user_ids.models import ExternalId, ExternalIdType
except ImportError as exc:  # pragma: no cover
    logger.exception(exc)

    get_potentially_retired_user_by_username = None
    get_course_overviews = None
    ExternalId = None
    ExternalIdType = None


User = get_user_model()
UTC_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
BLOCK_ID_FORMAT = '{block_version}:{course_id}+type@{block_type}+block@{block_id}'


def get_uuid5(namespace_key, name):
    """
    Create a UUID5 string based on custom namesapce and name.

    Arguments:
    namespace_key (str):    key to be used to create a custom namespace
    name  (str):            string for which we need to creat a UUID

    Returns:
        str

    """
    # We are not pulling base uuid from settings to avoid
    # data discrepancies incase setting is changed inadvertently
    base_uuid = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
    base_namespace = uuid.uuid5(base_uuid, namespace_key)
    return uuid.uuid5(base_namespace, name)


def get_anonymous_user_id(username_or_id, external_type):
    """
    Generate anonymous user id.

    Generate anonymous id for student.
    In case of anonymous user, return random uuid.

    Arguments:
        username_or_id (str):     username for the learner
        external_type  (str):     external type id e.g. caliper or xapi

    Returns:
        str
    """
    if not (ExternalId and ExternalIdType):
        raise ImportError("Could not import external_user_ids from edx-platform.")  # pragma: no cover

    user = get_user(username_or_id)
    if not user:
        logger.warning('User with username "%s" does not exist. '
                       'Cannot generate anonymous ID', username_or_id)
        return 'null'
        raise ValueError(f"User with username {username_or_id} does not exist.")

    # Older versions of edx-platform do not have the XAPI or
    # Caliper ExternalIdTypes, so we fall back to LTI here.
    # Eventually this will be a problem when those instances
    # upgrade and their actor id's all change, unless we
    # eventually add a setting to force LTI here instead of the
    # usual type.
    try:
        type_name = getattr(ExternalIdType, external_type)
    except AttributeError:  # pragma: no cover
        type_name = ExternalIdType.LTI

    external_id, _ = ExternalId.add_new_user_id(user, type_name)
    if not external_id:
        raise ValueError("External ID type: %s does not exist" % type_name)

    anonymous_id = str(external_id.external_user_id)

    return anonymous_id


def get_user(username_or_id):
    """
    Get user by username or user id.

    Arguments:
        username_or_id (str):     username or user id of the learner

    Returns:
        user object
    """
    if not get_potentially_retired_user_by_username:
        raise ImportError("Could not import student.models from edx-platform.")  # pragma: no cover

    user = username = None

    if not username_or_id:
        return None

    try:
        user = User.objects.get(id=int(username_or_id))
    except (User.DoesNotExist, ValueError):
        username = username_or_id
        user = User.objects.filter(username=username).first()

    if username and not user:
        try:
            user = get_potentially_retired_user_by_username(username)
        except Exception as ex:  # pylint: disable=broad-except
            logger.info('User with username "%s" does not exist.%s', username, ex)

    return user


def get_user_email(username_or_id):
    """
    Get user's email from username or user id.

    Arguments:
        username_or_id (str):     username for the learner

    Returns:
        str
    """
    user = get_user(username_or_id)

    if not user:
        logger.info('User with username "%s" does not exist.', username_or_id)
        user_email = 'unknown@example.com'
    else:
        user_email = user.email

    return user_email


def get_course_from_id(course_id):
    """
    Get Course object using the `course_id`.

    Arguments:
        course_id (str) :   ID of the course

    Returns:
        Course
    """
    if not get_course_overviews:
        raise ImportError("Could not import course_overviews.api from edx-platform.")  # pragma: no cover

    course_key = CourseKey.from_string(course_id)
    course_overviews = get_course_overviews([course_key])
    if course_overviews:
        return course_overviews[0]
    raise ValueError(f"Course with id {course_id} does not exist.")


def convert_seconds_to_iso(seconds):
    """
    Convert seconds from integer to ISO format.

    Arguments:
        seconds (int): number of seconds

    Returns:
        str
    """
    if seconds is None:
        return None
    return duration_isoformat(datetime.timedelta(
        seconds=seconds
    ))


def convert_seconds_to_float(seconds):
    """
    Convert seconds from integer to Float format.

    Arguments:
        seconds(str) : number of seconds

    Returns:
        float
    """
    if seconds is None or (seconds != 0 and not seconds):
        return None
    else:
        return float("{0:.3f}".format(float(seconds)))


def convert_datetime_to_iso(current_datetime):
    """
    Convert provided datetime into UTC format.

    Arguments:
        current_datetime (str):     datetime string

    Returns:
        str
    """
    # convert current_datetime to a datetime object if it is string
    if isinstance(current_datetime, str):
        current_datetime = parse(current_datetime)

    utc_offset = current_datetime.utcoffset()
    utc_datetime = current_datetime - utc_offset

    formatted_datetime = utc_datetime.strftime(UTC_DATETIME_FORMAT)[:-3] + 'Z'

    return formatted_datetime


def get_block_id_from_event_referrer(referrer):
    """
    Derive and return block id from event referrer.

    Arguments:
        referrer (str):   referrer string.

    Returns:
        str or None
    """
    if referrer is not None:
        parsed = urlparse(referrer)
        block_id = parse_qs(parsed.query)['activate_block_id'][0]\
            if 'activate_block_id' in parse_qs(parsed.query) and parse_qs(parsed.query)['activate_block_id'][0] \
            else None

    else:
        block_id = None

    return block_id


def get_block_id_from_event_data(data, course_id):
    """
    Derive and return block id from event data.

    Arguments:
        data (str):   data string.
        course_id       (str) : course key string

    Returns:
        str or None
    """
    if data is not None and course_id is not None:
        data_array = data.split('_')
        course_id_array = course_id.split(':')
        block_version = get_block_version(course_id)
        if len(data_array) > 1 and len(course_id_array) > 1:
            block_id = BLOCK_ID_FORMAT.format(
                block_version=block_version,
                course_id=course_id_array[1],
                block_type='problem',
                block_id=data_array[1]
            )
        else:
            block_id = None  # pragma: no cover
    else:
        block_id = None

    return block_id


def get_problem_block_id(referrer, data, course_id):
    """
    Derive and return block id from event data.

    Arguments:
        referrer (str):   referrer string.
        data (str):   data string.
        course_id       (str) : course key string

    Returns:
        str or None
    """
    block_id = get_block_id_from_event_referrer(referrer)
    if block_id is None:
        block_id = get_block_id_from_event_data(
            data,
            course_id
        )

    return block_id


def make_video_block_id(video_id, course_id):
    """
    Return formatted video block id for provided video and course.

    Arguments:
        video_id        (str) : id for the video object
        course_id       (str) : course key string

    Returns:
        str
    """
    course_id_array = course_id.split(':')
    block_version = get_block_version(course_id)
    return BLOCK_ID_FORMAT.format(
        block_version=block_version,
        course_id=course_id_array[1],
        block_type='video',
        block_id=video_id
    )


def backend_cache_ttl():
    """
    Return cache time out.

    Returns:
        int
    """
    return getattr(settings, 'EVENT_TRACKING_BACKENDS_CACHE_TTL', 600)


def get_business_critical_events():
    """
    Return list of business critical events.

    Returns:
        list
    """
    return getattr(settings, 'EVENT_TRACKING_BACKENDS_BUSINESS_CRITICAL_EVENTS', [
        'edx.course.enrollment.activated',
        'edx.course.enrollment.deactivated',
        'edx.course.grade.passed.first_time'
    ])


def get_block_version(course_id):
    """
    Return versioned block id.

    Arguments:
        course_id (str):    course id
        block_id (str):     block id

    Returns:
        str
    """
    course_id_array = course_id.split(':')
    block_version = "block-{0}".format(course_id_array[0].split("-")[-1])
    if "ccx" in course_id_array[0]:
        block_version = "ccx-{block_version}".format(block_version=block_version)
    return block_version
