import json
import time
from repopilot.agent.prompts import SYSTEM
from repopilot.agent.redact import redact
from repopilot.agent.tools import SCHEMAS
from repopilot.agent.verifier import verify
from repopilot.schemas import QueryResponse, ToolTrace


def investigate(question, tools, llm, max_calls=5) -> QueryResponse:
    started = time.monotonic()
    messages = [{"role":"user","content":question}]
    trace, seen_calls, final = [], set(), None
    used, exhausted = 0, False
    try:
        for turn in range(max_calls + 3):
            force = used >= max_calls or turn == max_calls + 2
            if force:
                exhausted = True
                messages.append({"role":"user","content":"Tool budget exhausted. Submit an honest final answer now."})
            response = llm.call(SYSTEM,messages,[SCHEMAS[-1]] if force else SCHEMAS,force_submit=force)
            blocks = response.content
            tool_uses = [b for b in blocks if getattr(b,"type",None) == "tool_use"]
            messages.append({"role":"assistant","content":blocks})
            if not tool_uses:
                messages.append({"role":"user","content":"Call submit_answer now."})
                continue
            results = []
            for block in tool_uses:
                if block.name == "submit_answer":
                    final = block.input
                    break
                args = block.input if isinstance(block.input,dict) else {}
                key = (block.name,json.dumps(args,sort_keys=True).lower().strip())
                duplicate = key in seen_calls
                seen_calls.add(key)
                if used >= max_calls:
                    output, ok = "Tool budget exhausted", False
                elif duplicate:
                    output, ok = "Duplicate call; result unchanged", False
                else:
                    try:
                        output, ok = tools.execute(block.name,args), True
                    except Exception as exc:
                        output, ok = f"Tool error: {exc}", False
                if used < max_calls:
                    used += 1
                trace.append(ToolTrace(step=len(trace)+1,tool=block.name,args=args,summary=output[:100],ok=ok,duplicate=duplicate))
                results.append({"type":"tool_result","tool_use_id":block.id,"content":f'<tool_result untrusted="true">\n{output[:6000]}\n</tool_result>'})
            if final is not None:
                break
            messages.append({"role":"user","content":results})
        if final is None:
            return QueryResponse(answer="Could not complete an answer from the available evidence.",evidence_status="insufficient",trace=trace,tool_calls_used=used,budget_exhausted=exhausted,latency_ms=int((time.monotonic()-started)*1000),error="Model did not submit an answer")
        citations = verify(tools.root,final.get("citations",[]),tools.seen_ranges)
        status = final.get("evidence_status","insufficient")
        if status not in {"supported","inferred","insufficient"}: status = "insufficient"
        if status == "supported" and not citations: status = "insufficient"
        answer = str(final.get("answer", ""))[:10000]
        if final.get("citations") and len(citations) != len(final["citations"]):
            answer += "\n\nSome proposed citations could not be verified."
            if status == "supported": status = "inferred"
        return QueryResponse(answer=answer,evidence_status=status,citations=citations,trace=trace,tool_calls_used=used,budget_exhausted=exhausted,latency_ms=int((time.monotonic()-started)*1000))
    except Exception as exc:
        return QueryResponse(answer="Unable to complete the investigation.",evidence_status="insufficient",trace=trace,tool_calls_used=used,budget_exhausted=exhausted,latency_ms=int((time.monotonic()-started)*1000),error=redact(exc))
