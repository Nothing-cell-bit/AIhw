from agent import MiniReActAgent


def print_steps(result) -> None:
    for step in result.steps:
        print(f"\n[Step {step.index}]")
        print(f"Thought: {step.thought}")
        if step.action:
            print(f"Action: {step.action}")
            print(f"Action Input: {step.action_input}")
            print(f"Observation: {step.observation}")
        if step.final_answer:
            print(f"Final Answer: {step.final_answer}")


def main() -> None:
    print("Mini ReAct Agent 已启动。输入 exit / quit 退出。")
    agent = MiniReActAgent()

    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("再见。")
            break
        if not user_input:
            continue

        result = agent.run(user_input)
        print_steps(result)
        print(f"\nAgent：{result.final_answer}")


if __name__ == "__main__":
    main()
