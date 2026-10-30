"""我的邻居波杰克 —— Streamlit 聊天界面。

语气设定与后端调用复用 app.py 里的 SYSTEM_PROMPT 和 generate_text，
所以网页版和终端版的“波杰克味儿”是同一套，不会跑偏。

运行：streamlit run app_web.py
"""

import os

import streamlit as st

from app import API_KEY_ENV, SETUP_HINT, api_key_problems, generate_text

# ---------------------------------------------------------------- 页面配置
st.set_page_config(
    page_title="我的邻居波杰克",
    page_icon="🐴",
    layout="centered",
)


# ---------------------------------------------------------------- Key 来源
def resolve_api_key():
    """按 优先级 取 Key：st.secrets → 环境变量。

    Streamlit Community Cloud 没有 Windows 环境变量，Key 放在
    Settings → Secrets 里（本地开发时对应 .streamlit/secrets.toml）。
    本地终端 / 自建服务器则继续用环境变量。
    返回 (key, 来源说明)。
    """
    # 1) 云端 / 本地 secrets.toml
    try:
        key = str(st.secrets[API_KEY_ENV]).strip()
        if key:
            return key, "st.secrets"
    except Exception:
        # 没有 secrets.toml、没配这一项、或值类型不对，都当作“这一层没给”
        pass

    # 2) 环境变量
    key = os.environ.get(API_KEY_ENV, "").replace("\ufeff", "").strip()
    if key:
        return key, "环境变量"

    return "", ""


_api_key, _key_source = resolve_api_key()

# app.py 里统一按环境变量取值，这里把 secrets 里的值同步进去，
# 终端版 / 网页版共用同一套校验和客户端逻辑。
if _api_key and not os.environ.get(API_KEY_ENV):
    os.environ[API_KEY_ENV] = _api_key

# Key 缺失或格式不对时直接给操作步骤，不要让人对着一堆 traceback 猜
_problems = api_key_problems(_api_key)
if _problems:
    st.error(f"⚠️ 没有拿到可用的 {API_KEY_ENV}，页面无法调用 DeepSeek。")
    for _p in _problems:
        st.markdown(f"- {_p}")

    st.markdown(
        "**部署在 Streamlit Community Cloud 上**："
        "打开 App → Settings → Secrets，粘贴下面这一行后保存（会自动重启）：\n"
    )
    st.code(f'{API_KEY_ENV} = "sk-你的真实key"', language="toml")

    st.markdown("**在本地运行**：先在 PowerShell 里设好环境变量，再重启服务。\n")
    st.markdown(f"```text\n{SETUP_HINT}\n```")
    st.stop()

GREETING = (
    "（把杯子放下，看了你一眼）哦，你来了。坐吧，反正这地方也没别人会来。"
    "想聊点什么？先说好，别指望我给你什么人生建议——"
    "我自己的人生还在试用期，而且看样子是过不了考核的那种。"
)

SAMPLES = [
    "介绍一下你最近在忙什么",
    "我周一又得上班了",
    "怎么才能变得快乐一点",
]

# ---------------------------------------------------------------- 初始化
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]

# ---------------------------------------------------------------- 侧边栏
with st.sidebar:
    st.subheader("🐴 关于这个页面")
    st.caption(
        "人格取自《马男波杰克》：疲惫、自嘲、玩世不恭，"
        "最后一定用一句冷幽默收尾。内容全部原创，不复述剧中台词。"
    )

    st.divider()
    st.caption("试试这些话题：")
    for i, sample in enumerate(SAMPLES):
        if st.button(sample, key=f"sample_{i}", use_container_width=True):
            st.session_state.pending = sample
            st.rerun()

    st.divider()
    st.caption(f"当前对话轮数：{len(st.session_state.messages) // 2}")
    if st.button("清空对话记忆", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": GREETING}]
        st.rerun()

# ---------------------------------------------------------------- 标题
st.title("我的邻居波杰克")
st.caption("一个只会用波杰克语气说话的聊天机器人。别指望它温柔。")

# ---------------------------------------------------------------- 历史消息
for message in st.session_state.messages:
    avatar = "🐴" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# ---------------------------------------------------------------- 单轮对话
def handle_turn(prompt: str) -> None:
    """处理一次输入：立刻回显用户消息，再请求模型并把回答写回历史。"""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 传上一轮之前的上下文，generate_text 会自己补上本轮 prompt
    history = st.session_state.messages[:-1]

    with st.chat_message("assistant", avatar="🐴"):
        with st.spinner("它正在灌下一杯再开口……"):
            try:
                reply = generate_text(prompt, history)
            except Exception as e:
                st.error(f"❌ 报错了：{e}")
                # 失败的那轮用户消息留在屏幕上，但不进上下文
                st.session_state.messages.pop()
                return

        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

    # 重跑一次，让侧边栏的轮数等派生信息与本轮同步
    st.rerun()


# ---------------------------------------------------------------- 输入区
prompt = st.chat_input("跟波杰克说点什么……")

# 侧边栏示例按钮写入的待处理话题
pending = st.session_state.pop("pending", None)

if prompt or pending:
    handle_turn(prompt or pending)
