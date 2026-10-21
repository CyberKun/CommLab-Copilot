import io
import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from test_flow import system
from commlab.common import DomainError
from commlab.knowledge.api import OllamaEmbedding
from commlab.retrieval.api import RetrievalRequest
from commlab.investigations.api import OllamaProvider


def test_pdf_preserves_page_and_warns_about_equations(system):
    services, _ = system
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"):font})})
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 30 740 Td (BPSK uses N0/2 real noise variance.) Tj ET")
    page[NameObject("/Contents")] = content
    stream = io.BytesIO()
    writer.write(stream)
    w = services.workspaces.create("pdf test")["id"]
    source = services.knowledge.upload(w,"synthetic.pdf",stream.getvalue(),"pdf-test")
    services.knowledge.ingest(w,source["id"])
    result = services.retrieval.search(w,RetrievalRequest(query="BPSK variance"))
    assert result.evidence[0].source.page == 1
    assert "N0/2" in result.evidence[0].text
    assert result.evidence[0].extraction_warnings


def test_embedding_identity_rejects_changed_model(monkeypatch):
    # Provider contract test double; this is not a live-provider quality test.
    monkeypatch.setattr(httpx,"get",lambda *a,**k: httpx.Response(200,json={"models":[{"name":"model:latest","digest":"new"}]},request=httpx.Request("GET","http://test")))
    provider = OllamaEmbedding("http://test","model","old")
    with pytest.raises(DomainError, match="digest changed"):
        provider.embed("BPSK")


def test_llm_adapter_validates_tool_and_records_real_usage_fields(monkeypatch):
    seen = {}
    def respond(*args, **kwargs):
        seen.update(kwargs["json"])
        return httpx.Response(200,json={"message":{"content":'{"tool":"search_references","arguments":{"query":"BPSK"}}'},
            "prompt_eval_count":99,"eval_count":21},request=httpx.Request("POST","http://test"))
    monkeypatch.setattr(httpx,"post",respond)
    result = OllamaProvider("http://test","test-model").decide("BPSK",[],[],1000)
    assert result.action.tool == "search_references"
    assert result.input_tokens == 99 and result.output_tokens == 21
    assert result.cost_usd is None
    assert seen["options"]["num_ctx"] <= 1000
    assert seen["options"]["num_predict"] <= 500
