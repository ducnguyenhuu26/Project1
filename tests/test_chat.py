import httpx
from fastapi.testclient import TestClient

from backend.main import build_app


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            response = httpx.Response(
                self.status,
                request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
            )
            raise httpx.HTTPStatusError("provider failed", request=response.request, response=response)

    def json(self):
        return self.body


def test_chat_uses_groq_for_grounded_kb_answer(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("timeout", kwargs["timeout"].read))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, headers, json):
            calls.append((url, headers, json))
            return FakeResponse({"choices": [{"message": {"content": "Hãy giữ chai sạch và kiểm tra nơi thu gom."}}]})

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr("backend.chat.httpx.AsyncClient", FakeClient)
    response = TestClient(build_app(mode="demo")).post(
        "/api/v1/chat", json={"message": "Chai nhựa xử lý thế nào?"}
    )
    assert response.status_code == 200
    assert response.json()["assistant"] == "groq"
    assert response.json()["grounded_in"] == "WasteWise curated knowledge base"
    request = calls[-1]
    assert request[0] == "https://api.groq.com/openai/v1/chat/completions"
    assert request[1] == {"Authorization": "Bearer test-key"}
    assert request[2]["model"] == "openai/gpt-oss-20b"
    assert request[2]["messages"][0]["role"] == "system"
    prompt = request[2]["messages"][-1]["content"]
    assert "NGUỒN KB PHÙ HỢP" in prompt and "Câu hỏi mới của người dùng:" in prompt


def test_chat_falls_back_to_kb_if_groq_fails(monkeypatch):
    class BrokenClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("backend.chat.httpx.AsyncClient", BrokenClient)
    response = TestClient(build_app(mode="demo")).post(
        "/api/v1/chat", json={"message": "Có nên đốt rác?"}
    )
    assert response.status_code == 200
    assert response.json()["assistant"] == "knowledge_base"
    assert "Không tự đốt" in response.json()["answer"]


def test_chat_asks_groq_even_when_kb_has_no_match(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    calls = []

    class FakeClient:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def post(self, _url, **kwargs):
            calls.append(kwargs["json"])
            return FakeResponse({"choices": [{"message": {"content": "Mình không có số liệu đã kiểm chứng để trả lời chính xác câu hỏi này."}}]})

    monkeypatch.setattr("backend.chat.httpx.AsyncClient", FakeClient)
    response = TestClient(build_app(mode="demo")).post(
        "/api/v1/chat", json={"message": "Lượng carbon chính xác là bao nhiêu?"}
    )
    assert response.status_code == 200
    assert response.json()["assistant"] == "groq"
    assert response.json()["grounded_in"] == "Groq general guidance"
    assert "Không tìm thấy mục KB phù hợp" in calls[0]["messages"][-1]["content"]
    assert "Thanh RAM là linh kiện điện tử không có pin tích hợp" in calls[0]["messages"][0]["content"]
    assert "chỉ khuyên giữ nguyên" in calls[0]["messages"][0]["content"]
    assert calls[0]["max_tokens"] >= 450


def test_electronic_item_questions_retrieve_e_waste_guidance(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, **kwargs):
            calls.append(kwargs["json"])
            return FakeResponse({"choices": [{"message": {"content": "Nếu bỏ loa cũ, hãy giữ nguyên thiết bị và chuyển tới chương trình thu hồi hoặc đơn vị có thẩm quyền được công bố. Không tự tháo, nghiền hoặc đốt."}}]})

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("backend.chat.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app(mode="demo"))
    for question in ("Có loa cũ thì nên làm gì?", "Thanh RAM cũ bị hỏng thì làm gì?"):
        response = client.post("/api/v1/chat", json={"message": question})
        assert response.status_code == 200
        assert response.json()["assistant"] == "groq"
        assert response.json()["material_id"] == "e_waste"
    assert len(calls) == 2
    assert all("đơn vị có thẩm quyền" in call["messages"][-1]["content"] for call in calls)


def test_chat_status_reports_configuration_without_exposing_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "sensitive-test-value")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    response = TestClient(build_app(mode="demo")).get("/api/v1/chat/status")
    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "provider": "Groq",
        "model": "openai/gpt-oss-20b",
    }
    assert "sensitive-test-value" not in response.text
