"""P2 — RAG grounding retriever + end-to-end grounding flow (offline)."""

from knowling.capabilities.retriever import SimpleRetriever, format_grounding, get_retriever
from knowling.engine import Config, generate_knowling
from knowling.schema import KnowledgePoint, SourceRef


def test_snippet_source():
    r = SimpleRetriever()
    chunks = r.fetch([SourceRef(id="s1", title="T", snippet="链式法则用于复合函数求导")])
    assert len(chunks) == 1
    assert "链式法则" in chunks[0].text
    assert "[T]" in format_grounding(chunks)


def test_file_source_and_ranking(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text(
        "无关段落讲别的东西。\n\n链式法则: 复合函数的导数等于外层导数乘以内层导数。\n\n又一段无关内容。",
        encoding="utf-8",
    )
    r = SimpleRetriever()
    chunks = r.fetch([SourceRef(id="d", uri=str(p))], query="链式法则 复合函数 导数", top_k=1)
    assert len(chunks) == 1
    assert "链式法则" in chunks[0].text  # highest-overlap paragraph ranked first


def test_get_retriever_default():
    assert get_retriever("auto").name == "simple"


def test_grounding_flows_through_pipeline(tmp_path):
    doc = tmp_path / "src.md"
    doc.write_text("欧姆定律: 电压等于电流乘以电阻 V=IR。", encoding="utf-8")
    kp = KnowledgePoint(id="phys.ohm", title="欧姆定律", description="V=IR",
                        source_refs=[SourceRef(id="src", uri=str(doc))])
    from knowling.capabilities.qa import QAConfig

    cfg = Config(provider_name="mock", quiet=True, qa=QAConfig(sandbox_name="static"))
    k = generate_knowling(kp, cfg, out_path=str(tmp_path / "o.html"))
    assert k.status in ("ready", "qa_failed")  # ran end-to-end with grounding
    assert k.knowledge_point_id == "phys.ohm"
