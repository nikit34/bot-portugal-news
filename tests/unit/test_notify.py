from src.static.settings import MAX_ERROR_RESPONSE_CHARS
from src.utils.notify import build_error_message, build_run_summary, redact_secrets


def test_redact_secrets_scrubs_access_token_and_oauth():
    url = '400 Bad Request for url: https://graph.facebook.com/v18.0/me/photos?fields=x&access_token=EAABsecret123&y=1'
    out = redact_secrets(url)
    assert 'EAABsecret123' not in out
    assert 'access_token=***' in out
    assert 'fields=x' in out and 'y=1' in out  # other params preserved

    out2 = redact_secrets("Authorization: OAuth EAABsecrettoken")
    assert 'EAABsecrettoken' not in out2 and 'OAuth ***' in out2


def test_redact_secrets_scrubs_dict_repr_and_bare_eaa_token():
    # Regression: repeater.log_error logs str(args), so the token appears in dict-repr
    # form {'access_token': 'EAA...'} — not the URL query form. It must still be scrubbed.
    tok = 'EAAUC9oTMHfQBR' + 'x' * 40
    params = "('https://graph.facebook.com/v22.0/1784/media', " \
             "{'access_token': '" + tok + "', 'limit': 50})"
    out = redact_secrets(params)
    assert tok not in out
    # a bare token anywhere (no access_token= prefix) is also caught by the EAA rule
    assert redact_secrets('token is ' + tok + ' end').count(tok) == 0


def test_build_error_message_redacts_token():
    class _Resp:
        text = 'body access_token=SECRETTOKEN extra'
    err = type('E', (Exception,), {})('boom for url ...?access_token=SECRETTOKEN')
    err.response = _Resp()
    msg = build_error_message('ERROR: x', err, '')
    assert 'SECRETTOKEN' not in msg
    assert 'access_token=***' in msg


def test_build_run_summary_reports_publishes_and_failures():
    stats = {'posts': 2, 'platforms': {'FACEBOOK': 2, 'TELEGRAM': 2, 'INSTAGRAM': 1},
             'ig_today': 5, 'ig_limit': 12, 'ig_this_run': 1, 'meta_circuit_open': False}
    out = build_run_summary(stats, {'comment': 2, 'story': 0}, '[ImageFilter] images checked: 3')

    assert 'опубликовано 2' in out
    assert 'FACEBOOK:2' in out and 'INSTAGRAM:1' in out
    assert 'IG за сутки: 5/12 (+1' in out
    assert 'первый комментарий IG не отправлен: 2' in out
    assert 'Stories не опубликованы' not in out   # story=0 -> no line
    assert '[ImageFilter]' in out


def test_build_run_summary_flags_circuit_open():
    stats = {'posts': 0, 'platforms': {}, 'ig_today': 0, 'ig_limit': 12,
             'ig_this_run': 0, 'meta_circuit_open': True}
    out = build_run_summary(stats, {'comment': 0, 'story': 0}, '')
    assert 'Meta circuit open' in out


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
