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

    content, response_chars = await collect_openai_chat_stream(
        client,
        "https://example.test/chat/completions",
        headers={},
        payload={"model": "m", "stream": False},
        timeout=httpx.Timeout(10),
    )

    assert content == '{"a":1}'
    assert response_chars > 0
    assert client.payload["stream"] is True


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
