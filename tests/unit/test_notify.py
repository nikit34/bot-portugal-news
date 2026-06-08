from src.static.settings import MAX_ERROR_RESPONSE_CHARS
from src.utils.notify import build_error_message


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _ErrorWithResponse(Exception):
    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


def test_build_error_message_basic_with_run_url():
    message = build_error_message('ERROR: x is down', Exception('boom'), 'https://ci/run/1')

    assert message == 'ERROR: x is down\nboom\n<a href="https://ci/run/1">Open CI logs</a>'


def test_build_error_message_without_run_url_still_has_body():
    # Regression: previously the whole message collapsed to '' when run_url was falsy.
    message = build_error_message('ERROR: x is down', Exception('boom'), '')

    assert message == 'ERROR: x is down\nboom'
    assert 'Open CI logs' not in message


def test_build_error_message_truncates_response_body():
    big_body = 'A' * 10000
    error = _ErrorWithResponse('400 Bad Request', _FakeResponse(big_body))

    message = build_error_message('ERROR: x is down', error, '')

    assert ', response: ' in message
    # The appended body must be capped so the alert stays under Telegram's limit.
    assert 'A' * MAX_ERROR_RESPONSE_CHARS in message
    assert 'A' * (MAX_ERROR_RESPONSE_CHARS + 1) not in message
    assert len(message) < 4096


def test_build_error_message_no_response_attr():
    message = build_error_message('ERROR: x is down', Exception('boom'), 'https://ci/run/1')

    assert ', response: ' not in message
