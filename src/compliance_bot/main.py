"""CLI entrypoint for chatting with the Week 1 baseline chain."""

from compliance_bot.chains.baseline_chain import build_baseline_chain, invoke_baseline_chain
from compliance_bot.llms.siliconflow import build_siliconflow_llm


def main() -> None:
    """Run a simple terminal chat loop."""
    try:
        llm = build_siliconflow_llm()
    except (ValueError, ModuleNotFoundError, ImportError) as exc:
        print(f"LLM setup failed: {exc}")
        print("Set SILICONFLOW_API_KEY and install runtime dependencies.")
        return

    chain = build_baseline_chain(llm)

    print("Enter `quit` or `exit` to stop.")
    while True:
        question = input("\nQuestion: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            print("Question cannot be blank.")
            continue

        context = input("Context (optional): ").strip()
        result = invoke_baseline_chain(chain, question=question, context=context or None)

        print(f"\nanswer: {result.answer}")
        print(f"confidence: {result.confidence}")
        print(f"decision: {result.decision.value}")


if __name__ == "__main__":
    main()
