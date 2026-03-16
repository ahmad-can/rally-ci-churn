"""Verify shared controller runtime helpers."""

from __future__ import annotations

from keystoneauth1 import session as ks_session

from rally_ci_churn.plugins import controller_runtime


class _FakeKeystoneClient:
    def __init__(self) -> None:
        self._session = ks_session.Session()

    def get_session(self):
        return self._session, None


class _FakeClients:
    def __init__(self) -> None:
        self.keystone = _FakeKeystoneClient()


class _DummyParallelMixin(controller_runtime.ParallelBootMixin):
    def __init__(self) -> None:
        self._clients = _FakeClients()


def test_ensure_http_pool_capacity_scales_cached_keystone_session() -> None:
    dummy = _DummyParallelMixin()
    keystone_session = dummy._clients.keystone.get_session()[0]
    original_http_adapter = keystone_session.adapters["http://"]
    original_https_adapter = keystone_session.adapters["https://"]

    assert getattr(original_http_adapter, "_pool_maxsize") == controller_runtime.HTTP_POOL_BASE_SIZE
    assert getattr(original_https_adapter, "_pool_maxsize") == controller_runtime.HTTP_POOL_BASE_SIZE

    dummy._ensure_http_pool_capacity(12)

    resized_http_adapter = keystone_session.adapters["http://"]
    resized_https_adapter = keystone_session.adapters["https://"]
    expected_size = 12 + controller_runtime.HTTP_POOL_HEADROOM

    assert isinstance(resized_http_adapter, type(original_http_adapter))
    assert isinstance(resized_https_adapter, type(original_https_adapter))
    assert getattr(resized_http_adapter, "_pool_maxsize") == expected_size
    assert getattr(resized_https_adapter, "_pool_maxsize") == expected_size
    assert getattr(resized_http_adapter, "_pool_connections") == expected_size
    assert getattr(resized_https_adapter, "_pool_connections") == expected_size


def test_ensure_http_pool_capacity_never_downsizes_existing_pool() -> None:
    dummy = _DummyParallelMixin()
    keystone_session = dummy._clients.keystone.get_session()[0]

    dummy._ensure_http_pool_capacity(20)
    large_http_adapter = keystone_session.adapters["http://"]
    large_https_adapter = keystone_session.adapters["https://"]

    dummy._ensure_http_pool_capacity(4)

    assert getattr(keystone_session.adapters["http://"], "_pool_maxsize") == getattr(large_http_adapter, "_pool_maxsize")
    assert getattr(keystone_session.adapters["https://"], "_pool_maxsize") == getattr(large_https_adapter, "_pool_maxsize")


def test_ensure_http_pool_capacity_without_cached_clients_is_noop() -> None:
    class _NoClients(controller_runtime.ParallelBootMixin):
        pass

    _NoClients()._ensure_http_pool_capacity(12)
