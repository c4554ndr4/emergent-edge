import pytest
from concurrent.futures import ThreadPoolExecutor
from src.models.llm_client import EndpointLLMClient, get_default_llm_client, DeterministicStubLLM
from src.models.embedding_client import EndpointEmbeddingClient, DeterministicDummyEmbeddingClient, get_default_embedding_client
from src.models.transport import post_json

@pytest.fixture(autouse=True)
def isolated_endpoints(monkeypatch):
    for name in ('LLM_BASE_URL', 'LLM_API_KEY', 'MODEL_NAME', 'EMBEDDING_BASE_URL', 'EMBEDDING_API_KEY', 'EMBEDDING_MODEL'):
        monkeypatch.delenv(name, raising=False)

def test_offline_requires_no_credentials_and_does_not_mix_live_embeddings(monkeypatch):
    assert isinstance(get_default_llm_client(), DeterministicStubLLM)
    monkeypatch.setenv('LLM_API_KEY', 'fictional-test-key')
    with pytest.raises(ValueError): get_default_llm_client()
    with pytest.raises(ValueError): get_default_embedding_client()

@pytest.mark.parametrize('payload', [{}, {'choices': []}, {'choices': [{'message': {'content': ''}}]}])
def test_chat_rejects_unusable_response(monkeypatch, payload):
    monkeypatch.setattr('src.models.llm_client.post_json', lambda *args: payload)
    with pytest.raises(ValueError): EndpointLLMClient('test', 'https://example.invalid').generate('fictional')

def test_chat_preserves_system_and_user_roles(monkeypatch):
    captured = {}
    def fake(url, path, payload, key):
        captured.update(payload)
        return {'choices': [{'message': {'content': 'result'}}]}
    monkeypatch.setattr('src.models.llm_client.post_json', fake)
    assert EndpointLLMClient('test', 'https://example.invalid').generate('data', 'instruction') == 'result'
    assert [x['role'] for x in captured['messages']] == ['system', 'user']

def test_embeddings_restore_input_order(monkeypatch):
    monkeypatch.setattr('src.models.embedding_client.post_json', lambda *args: {'data': [
        {'index': 1, 'embedding': [0, 1]}, {'index': 0, 'embedding': [1, 0]}]})
    assert EndpointEmbeddingClient('test', 'https://example.invalid').embed(['a', 'b']) == [[1, 0], [0, 1]]

@pytest.mark.parametrize('data', [
    [], [{'index': 0, 'embedding': []}], [{'index': 0, 'embedding': [float('nan')]}],
    [{'index': True, 'embedding': [1]}], [{'index': 2, 'embedding': [1]}]
])
def test_embeddings_reject_invalid_results(monkeypatch, data):
    monkeypatch.setattr('src.models.embedding_client.post_json', lambda *args: {'data': data})
    with pytest.raises(ValueError): EndpointEmbeddingClient('test', 'https://example.invalid').embed(['a'])

def test_dummy_embeddings_are_stable_under_concurrency():
    client = DeterministicDummyEmbeddingClient()
    expected = client.embed(['a', 'b'])
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(result == expected for result in pool.map(lambda _: client.embed(['a', 'b']), range(30)))

@pytest.mark.parametrize('url', ['http://remote.example', 'https://user:secret@example.com', 'https://example.com?key=secret', 'https://example.com#secret'])
def test_transport_rejects_insecure_or_credential_bearing_urls(url):
    with pytest.raises(ValueError): post_json(url, 'chat/completions', {}, None)

def test_transport_disallows_redirects_and_does_not_expose_error_payload(monkeypatch):
    captured = {}
    class Response:
        status_code = 302
    def fake(url, **kwargs):
        captured.update(kwargs)
        return Response()
    monkeypatch.setattr('src.models.transport.requests.post', fake)
    with pytest.raises(RuntimeError, match='HTTP 302'): post_json('https://example.invalid', 'chat/completions', {}, 'fictional')
    assert captured['allow_redirects'] is False

def test_live_placeholder_models_are_rejected():
    with pytest.raises(ValueError): EndpointLLMClient('analysis-model', 'https://example.invalid')
    with pytest.raises(ValueError): EndpointEmbeddingClient('embedding-model', 'https://example.invalid')
