import json

import streamlit as st

from agent import MiniReActAgent
from memory import ConversationMemory


st.set_page_config(page_title="Mini ReAct Agent", page_icon=":robot_face:", layout="wide")


def create_agent() -> MiniReActAgent:
    return MiniReActAgent(memory=ConversationMemory())


if "agent" not in st.session_state:
    st.session_state.agent = create_agent()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


st.title("Mini ReAct Agent")

with st.sidebar:
    st.subheader("工具")
    st.write("calculator")
    st.write("wikipedia_search")
    st.write("file_write")
    st.write("file_read")
    if st.button("清空对话"):
        st.session_state.agent = create_agent()
        st.session_state.chat_history = []
        st.rerun()


for item in st.session_state.chat_history:
    with st.chat_message(item["role"]):
        st.write(item["content"])
        if item.get("steps"):
            with st.expander("查看思考与工具调用"):
                for step in item["steps"]:
                    st.markdown(f"**Step {step.index}**")
                    st.write(f"Thought: {step.thought}")
                    if step.action:
                        st.code(
                            json.dumps(
                                {
                                    "action": step.action,
                                    "action_input": step.action_input,
                                    "observation": step.observation,
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            language="json",
                        )


prompt = st.chat_input("输入任务，例如：查一下爱因斯坦的出生年份和去世年份，然后计算他活了多少岁。")

if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agent 正在思考和调用工具..."):
            result = st.session_state.agent.run(prompt)
        st.write(result.final_answer)
        with st.expander("查看思考与工具调用", expanded=True):
            for step in result.steps:
                st.markdown(f"**Step {step.index}**")
                st.write(f"Thought: {step.thought}")
                if step.action:
                    st.code(
                        json.dumps(
                            {
                                "action": step.action,
                                "action_input": step.action_input,
                                "observation": step.observation,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        language="json",
                    )

    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": result.final_answer,
            "steps": result.steps,
        }
    )
