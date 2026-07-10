import httpx
import pytest

from app.services.chat_stream import collect_openai_chat_stream


class FakeStreamResponse:
    def __init__(self, lines, status_code=200, body=b""):
        self._lines = lines
        self.status_code = status_code
        self._body = body
        self.request = httpx.Request("POST", "https://example.test/chat/completions")
        self._content = b""

    @property
    def text(self):
        return self._content.decode("utf-8", "replace")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return self._body


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.payload = None

    def stream(self, method, url, *, headers, json, timeout):
        self.payload = json
        return self.response


@pytest.mark.anyio
async def test_collect_openai_chat_stream_concatenates_delta_content():
    client = FakeClient(FakeStreamResponse([
        'data: {"choices":[{"delta":{"content":"{\\\"a\\\":"}}]}',
        'data: {"choices":[{"delta":{"content":"1}"}}]}',
        'data: [DONE]',
    ]))

    content, response_chars, usage = await collect_openai_chat_stream(
        client,
        "https://example.test/chat/completions",
        headers={},
        payload={"model": "m", "stream": False},
        timeout=httpx.Timeout(10),
    )

    assert content == '{"a":1}'
    assert response_chars > 0
    assert usage is None
    assert client.payload["stream"] is True
    assert client.payload.get("stream_options", {}).get("include_usage") is True


@pytest.mark.anyio
async def test_collect_openai_chat_stream_captures_usage_chunk():
    client = FakeClient(FakeStreamResponse([
        'data: {"choices":[{"delta":{"content":"hi"}}]}',
        'data: {"choices":[], "usage":{"prompt_tokens":11,"completion_tokens":4,"total_tokens":15}}',
        'data: [DONE]',
    ]))

    content, _, usage = await collect_openai_chat_stream(
        client,
        "https://example.test/chat/completions",
        headers={},
        payload={"model": "m"},
        timeout=httpx.Timeout(10),
    )
    assert content == "hi"
    assert usage == {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15}


@pytest.mark.anyio
async def test_collect_openai_chat_stream_raises_on_sse_error_event():
    client = FakeClient(FakeStreamResponse([
        ": connected",
        "event: error",
        'data: {"status":502,"error":"upstream failed"}',
    ]))

    with pytest.raises(RuntimeError, match="upstream failed"):
        await collect_openai_chat_stream(
            client,
            "https://example.test/chat/completions",
            headers={},
            payload={"model": "m"},
            timeout=httpx.Timeout(10),
        )


@pytest.mark.anyio
async def test_collect_openai_chat_stream_raises_with_error_body():
    client = FakeClient(FakeStreamResponse([], status_code=503, body=b"upstream timeout"))

    with pytest.raises(httpx.HTTPStatusError) as error:
        await collect_openai_chat_stream(
            client,
            "https://example.test/chat/completions",
            headers={},
            payload={"model": "m"},
            timeout=httpx.Timeout(10),
        )

    assert error.value.response.status_code == 503
    assert error.value.response.text == "upstream timeout"
