import asyncio
from backend.llm.gemini_client import generate_analysis

async def main():
    result = await generate_analysis(
        evidence={"bug_id": "BP-101", "status": "open", "severity": "high"},
        question="Summarize this bug"
    )
    print("RESULT:", result)

asyncio.run(main())
