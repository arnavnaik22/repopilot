"""Optional hosted answer grader with a small, explicit key-fact rubric."""
import json

SCHEMA = {"name":"submit_grade","description":"Grade the answer against the reference facts.","input_schema":{"type":"object","properties":{"score":{"type":"number","enum":[0,0.5,1]},"reason":{"type":"string"}},"required":["score","reason"]}}


def judge_answer(case: dict, answer: str, llm) -> dict:
    prompt = json.dumps({"question":case["question"],"reference_answer":case.get("reference_answer",""),"key_facts":case.get("key_facts",[]),"candidate_answer":answer},ensure_ascii=False)
    response = llm.call(
        "Grade factual correctness using the reference answer and key facts. Score 1 if the answer covers the key facts without material errors, 0.5 if partly correct, and 0 if wrong or unsupported. Do not reward confident guesses. Call submit_grade.",
        [{"role":"user","content":prompt}], [SCHEMA], force_submit=True,
    )
    for block in response.content:
        if getattr(block,"type",None)=="tool_use" and block.name=="submit_grade":
            score=block.input.get("score")
            if score not in (0,0.5,1): raise ValueError("Invalid judge score")
            return {"score":score,"reason":str(block.input.get("reason",""))[:500]}
    raise ValueError("Judge did not submit a grade")
