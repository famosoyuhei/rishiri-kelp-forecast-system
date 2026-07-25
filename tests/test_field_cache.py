"""
Unit tests for the shared Redis/in-memory field cache (start.py):
  - _fc_redis_get() / _fc_redis_set()   Upstash REST wire format
  - _field_cache_get() / _field_cache_set()  hybrid cache, malformed-value handling
  - _get_summit_hourly_temps()          summit cache consumer
  - get_analysis_field()                /api/analysis/field cache-hit path

Covers the 2026-08-05 incident: _fc_redis_set() previously POSTed
["EX", ttl, payload] to /set/<key>, which Upstash stored verbatim as the
value instead of interpreting as SET's EX option, corrupting every cached
entry. Fixed to POST the full command ["SET", key, payload, "EX", ttl] to
the Upstash REST root endpoint, and to never let a malformed cached value
propagate to a caller that would crash on it.

Run from project root:
    python -m pytest tests/test_field_cache.py -v
"""
import json
from unittest.mock import patch, MagicMock

import pytest

# Import start.py exactly once, here, before any test's monkeypatched env vars
# (e.g. a fake UPSTASH_REDIS_REST_URL) could be active. Flask-Limiter reads
# UPSTASH_REDIS_REST_URL at *module import time* to pick its rate-limit
# storage backend; if start.py were first imported while a test's fake
# Upstash URL was set, every later test hitting a rate-limited route would
# try to connect to that fake host and fail. Module-level import runs at
# collection time, before any fixture/monkeypatch executes.
import start  # noqa: E402


@pytest.fixture
def upstash_env(monkeypatch):
    """Make _fc_redis_get/_fc_redis_set attempt the Redis path (not short-circuit)."""
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL', 'https://fake-upstash.example.com')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN', 'fake-token')


# ---------------------------------------------------------------------------
# _fc_redis_set: wire format
# ---------------------------------------------------------------------------

def test_fc_redis_set_sends_full_set_command_array(upstash_env):
    import start
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {'result': 'OK'}

    with patch.object(start.requests, 'post', return_value=mock_resp) as mock_post:
        ok = start._fc_redis_set('somekey', {'a': 1, 'b': [1, 2]}, 900)

    assert ok is True
    assert mock_post.call_count == 1
    call = mock_post.call_args
    # Posted to the Upstash REST root endpoint, not /set/<key>.
    assert call.args[0] == 'https://fake-upstash.example.com'
    sent_json = call.kwargs['json']
    assert sent_json[0] == 'SET'
    assert sent_json[1] == 'fc2:somekey'  # _FC_KEY_PREFIX applied
    assert json.loads(sent_json[2]) == {'a': 1, 'b': [1, 2]}
    assert sent_json[3] == 'EX'
    assert sent_json[4] == '900'
    assert sent_json == ['SET', 'fc2:somekey', sent_json[2], 'EX', '900']


def test_fc_redis_set_returns_false_when_result_is_not_ok(upstash_env):
    import start
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {'result': 'something-else'}
    with patch.object(start.requests, 'post', return_value=mock_resp):
        assert start._fc_redis_set('k', {'x': 1}, 100) is False


def test_fc_redis_set_returns_false_on_non_200(upstash_env):
    import start
    mock_resp = MagicMock(status_code=500)
    with patch.object(start.requests, 'post', return_value=mock_resp):
        assert start._fc_redis_set('k', {'x': 1}, 100) is False


def test_fc_redis_set_returns_false_without_upstash_env(monkeypatch):
    import start
    monkeypatch.delenv('UPSTASH_REDIS_REST_URL', raising=False)
    monkeypatch.delenv('UPSTASH_REDIS_REST_TOKEN', raising=False)
    assert start._fc_redis_set('k', {'x': 1}, 100) is False


# ---------------------------------------------------------------------------
# Redis failure / timeout must never raise (never turn into a 500)
# ---------------------------------------------------------------------------

def test_fc_redis_set_timeout_does_not_raise(upstash_env):
    import start
    import requests as _requests_mod
    with patch.object(start.requests, 'post', side_effect=_requests_mod.exceptions.Timeout):
        assert start._fc_redis_set('k', {'x': 1}, 100) is False


def test_fc_redis_get_timeout_does_not_raise(upstash_env):
    import start
    import requests as _requests_mod
    with patch.object(start.requests, 'get', side_effect=_requests_mod.exceptions.Timeout):
        assert start._fc_redis_get('k') is None


def test_fc_redis_get_undecodable_json_returns_none(upstash_env):
    import start
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {'result': 'not valid json {{{'}
    with patch.object(start.requests, 'get', return_value=mock_resp):
        assert start._fc_redis_get('k') is None


def test_fc_redis_get_uses_prefixed_key(upstash_env):
    import start
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {'result': json.dumps({'ok': True})}
    with patch.object(start.requests, 'get', return_value=mock_resp) as mock_get:
        result = start._fc_redis_get('somekey')
    assert result == {'ok': True}
    called_url = mock_get.call_args.args[0]
    assert called_url.endswith('/get/fc2:somekey')


# ---------------------------------------------------------------------------
# _field_cache_get: malformed-value handling (the actual production bug)
# ---------------------------------------------------------------------------

def test_field_cache_get_rejects_legacy_malformed_list_from_redis():
    import start
    # Exactly the corrupted shape observed in production before the fix.
    malformed = ['EX', 1800, '{"time": [], "temperature_2m": []}']
    with patch.object(start, '_fc_redis_get', return_value=malformed):
        start._analysis_field_cache.pop('mykey', None)
        result = start._field_cache_get('mykey')
    assert result is None  # never propagates the malformed list


def test_field_cache_get_falls_back_to_in_memory_when_redis_malformed():
    import start
    from datetime import timedelta
    good = {'time': ['x'], 'temperature_2m': [1.0]}
    start._analysis_field_cache['mykey2'] = {
        'data': good,
        'expires': start.datetime.now(start.JST) + timedelta(seconds=100),
    }
    with patch.object(start, '_fc_redis_get', return_value=['EX', 100, '{}']):
        result = start._field_cache_get('mykey2')
    assert result == good
    start._analysis_field_cache.pop('mykey2', None)


def test_field_cache_get_returns_valid_dict_from_redis():
    import start
    good = {'time': ['x'], 'temperature_2m': [1.0]}
    with patch.object(start, '_fc_redis_get', return_value=good):
        start._analysis_field_cache.pop('mykey3', None)
        result = start._field_cache_get('mykey3')
    assert result == good
    start._analysis_field_cache.pop('mykey3', None)


def test_field_cache_get_none_on_total_miss():
    import start
    start._analysis_field_cache.pop('mykey4', None)
    with patch.object(start, '_fc_redis_get', return_value=None):
        assert start._field_cache_get('mykey4') is None


# ---------------------------------------------------------------------------
# _get_summit_hourly_temps: consumer-level defense + cache-miss re-fetch
# ---------------------------------------------------------------------------

def test_get_summit_hourly_temps_missing_keys_falls_through_to_fresh_fetch():
    import start
    malformed_but_dict = {'unexpected': 'shape'}  # a dict, but missing required keys
    fresh_resp = MagicMock()
    fresh_resp.raise_for_status.return_value = None
    fresh_resp.json.return_value = {
        'hourly': {'time': ['2026-08-05T06:00'], 'temperature_2m': [10.0]}
    }
    with patch.object(start, '_field_cache_get', return_value=malformed_but_dict), \
         patch.object(start, '_field_cache_set') as mock_set, \
         patch.object(start.requests, 'get', return_value=fresh_resp):
        result = start._get_summit_hourly_temps()

    assert result is not None
    assert result['time'] == ['2026-08-05T06:00']
    assert result['temperature_2m'] == [10.0]
    assert result['_cache_hit'] is False
    mock_set.assert_called_once()  # re-populates the cache with a well-formed entry


def test_get_summit_hourly_temps_valid_cache_hit_copies_not_mutates():
    import start
    cached = {'time': ['x'], 'temperature_2m': [5.0], '_fetched_at': 'now', '_cache_hit': False}
    with patch.object(start, '_field_cache_get', return_value=cached):
        result = start._get_summit_hourly_temps()

    assert result['_cache_hit'] is True
    assert cached['_cache_hit'] is False  # original object untouched


# ---------------------------------------------------------------------------
# get_analysis_field(): cache-hit copy-not-mutate (route-level)
# ---------------------------------------------------------------------------

def test_get_analysis_field_cache_hit_does_not_mutate_shared_cache_object():
    import start
    cached_entry = {
        'status': 'success', 'type': 'score', 'day': 0,
        'target_date': '2026-08-05', 'timezone': 'Asia/Tokyo',
        'generated_at': 'x', 'cache': {'hit': False},
        'points': [], 'summary': {},
    }
    client = start.app.test_client()
    with patch.object(start, '_field_cache_get', return_value=cached_entry):
        resp = client.get('/api/analysis/field?type=score&day=0')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['cache'] == {'hit': True}
    # The object _field_cache_get() returned must not have been mutated in place.
    assert cached_entry['cache'] == {'hit': False}
