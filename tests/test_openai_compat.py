import json

import httpx
import pytest

from negmt.llm.openai_compat import LLMServerError, OpenAICompatClient


def ok(content, prompt_tokens=100, completion_tokens=20):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                                     "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}})


def client(handler, **kw):
    return OpenAICompatClient("http://gpu:8000/v1/", "Qwen/Qwen3.8-27B", model="qwen3.8-27b",
                              transport=httpx.MockTransport(handler), backoff=0, **kw)


def test_request_shape_and_response():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return ok('{"a": 1}')

    c = client(handler, sampling={"top_p": 0.8}, extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    resp = c.generate("SYSTEM", [{"role": "user", "content": "hi"}], {"type": "object"}, seed=7, temperature=0.7)

    body = seen["body"]
    assert seen["url"] == "http://gpu:8000/v1/chat/completions"
    assert body["model"] == "Qwen/Qwen3.8-27B"
    assert body["messages"][0] == {"role": "system", "content": "SYSTEM"}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert body["seed"] == 7 and body["temperature"] == 0.7 and body["top_p"] == 0.8
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert resp.text == '{"a": 1}' and resp.input_tokens == 100 and resp.output_tokens == 20
    assert resp.model == "qwen3.8-27b"


def test_think_block_is_stripped():
    c = client(lambda r: ok('<think>planning...</think>\n{"a": 1}'))
    assert c.generate("s", [], {}).text == '{"a": 1}'


def test_retries_server_errors_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, text="busy") if len(calls) < 3 else ok("{}")

    assert client(handler).generate("s", [], {}).text == "{}"
    assert len(calls) == 3


def test_gives_up_after_max_retries():
    with pytest.raises(LLMServerError):
        client(lambda r: httpx.Response(500, text="boom"), max_retries=2).generate("s", [], {})


def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, text="bad schema")

    with pytest.raises(ValueError):
        client(handler).generate("s", [], {})
    assert len(calls) == 1
