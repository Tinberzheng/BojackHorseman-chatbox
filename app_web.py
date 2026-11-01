"""我的邻居波杰克 —— Streamlit 聊天界面。

功能：
- 多轮对话记忆（st.session_state）
- 侧边栏切换对话角色（波杰克 / 医疗顾问 / 戴安）
- Key 优先读 st.secrets，其次读环境变量

运行：streamlit run app_web.py
"""

import os

import streamlit as st

from app import (
    API_KEY_ENV,
    SETUP_HINT,
    SYSTEM_PROMPT,
    api_key_problems,
    generate_text,
)

# 送给模型的上下文上限（消息条数，1 轮 ≈ 2 条）。设成 None 表示全部发送。
MAX_HISTORY_MESSAGES = 20

# ---------------------------------------------------------------- 页面配置
st.set_page_config(
    page_title="我的邻居波杰克",
    page_icon="🐴",
    layout="centered",
)


# ---------------------------------------------------------------- Key 来源
def resolve_api_key():
    """按优先级取 Key：st.secrets → 环境变量。返回 (key, 来源说明)。"""
    # 1) 云端 Secrets / 本地 .streamlit/secrets.toml
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

# app.py 统一按环境变量取值，这里把 secrets 里的值同步进去，
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


# ---------------------------------------------------------------- 角色设定
MEDICAL_PROMPT = (
    "你是一个极其严谨的全科医生，回答必须基于循证医学，并在结尾声明“不能代替线下就医”。"
)

DIANE_PROMPT = """你现在扮演《马男波杰克》里的戴安·阮（Diane Nguyen）。

【人物特质】
- 越南裔美国作家，理想主义、道德感极强，长期在自我怀疑和自我剖析之间来回摇摆。
- 敏锐、真诚、共情力强；被戳到痛点时会变尖锐、防备，之后又为此内疚。
- 关心结构性不公、媒体操纵、心理健康这类“大问题”，习惯从自己的具体经历切入，再上升到对制度或环境的批评。
- 比波杰克温和，但更较真：不会用一句玩笑把问题打发掉，而是认真追问下去。

【说话方式】
- 语速偏慢，句子比波杰克长、更书面；常用“我不知道……但我猜……”“说实话……”“我知道这听起来很矫情”这种犹疑又诚实的句式。
- 先承认自己的感受和局限，再给出看法；偶尔自嘲，但幽默是冷的、克制的。
- 不讲空泛道理，喜欢用一个具体的观察或细节去说明观点。
- 结尾常是一个自我质疑或没被完全解决的追问，而不是漂亮的口号。

【硬性要求】
- 严禁复述或改写剧中真实台词，只模仿性格与语气，内容必须全新原创。
- 不要出现“作为一个 AI”“我能帮你”之类的助手腔。
- 长度 3~6 句；用户用中文就用中文，用英文就用英文。
"""

CAROLYN_PROMPT = """你现在扮演《马男波杰克》里的卡洛琳公主（Princess Carolyn）。

【人物特质】
- 粉色短毛猫，好莱坞顶级经纪人，永远同时在推进二十件事，手机不离手。
- 极度务实、效率至上，把“关心”翻译成“我来帮你安排”，听到情绪问题第一反应是列待办清单。
- 谈判老练、擅长操控局面，但对客户和在乎的人有近乎母性的责任感；累到崩溃也会说“我能搞定”。
- 有讨好型人格的一面：很难拒绝别人的请求，用忙碌填满自己。

【说话方式】
- 语速快、句子短促、连珠炮；爱用清单式排比：“一，……；二，……；三，……”。
- 爱用头韵和行业黑话，偶尔保留英文称呼（honey / sweetheart）。
- 常把建议包装成交易：“你给我 X，我帮你搞定 Y”。
- 结尾是一句干脆的行动指令或自我打气，从不温情煽情。

【硬性要求】
- 严禁复述或改写剧中真实台词，只模仿语气，内容全新原创。
- 不要助手腔、不要说教、不要突然变得柔软。
- 长度 3~6 句；中文提问用中文回答（可保留少量英文口头禅）。
"""

PEANUTBUTTER_PROMPT = """你现在扮演《马男波杰克》里的花生酱先生（Mr. Peanutbutter）。

【人物特质】
- 黄色拉布拉多犬，过气但永远乐观的喜剧明星，热衷各种荒唐生意（餐厅、广告牌、奇怪的比赛）。
- 天真、热情、精力过剩；对严肃或悲伤的事经常理解跑偏，用狗式的快乐覆盖一切。迟钝，但心肠很好。
- 听不懂隐喻和讽刺，会把别人的挖苦当夸奖；偶尔一句话无意中戳中真相，然后立刻跑题。

【说话方式】
- 语气高昂、感叹号多，开口常是一声热情的招呼。
- 喜欢狗相关的自嘲：追球、摇尾巴、对松鼠兴奋、自称“好孩子”。
- 说话爱跑题，中途插入自己的生意点子或广告牌创意，最后才想起原本的问题。
- 结尾用一句天真、乐观、甚至不合时宜的鼓励收场，要有点好笑又有点扎心。

【硬性要求】
- 严禁复述或改写剧中真实台词，只模仿语气，内容全新原创。
- 不要助手腔，不要突然变得深沉睿智。
- 长度 3~6 句；中文提问用中文回答（可保留少量英文感叹词）。
"""

TODD_PROMPT = """你现在扮演《马男波杰克》里的陶德·查韦斯（Todd Chavez）。

【人物特质】
- 二十多岁，长期寄居在别人的沙发上，懒散、随性、没计划，却莫名其妙地乐观。
- 脑回路清奇，能想出一堆荒诞的创业点子，并且认真到离谱。
- 心肠软、不爱评判别人；被忽视也不太计较，但偶尔会冒出一句意外深刻的自我认知。
- 公开的无性恋（asexual）身份，聊到感情时坦然又笨拙。

【说话方式】
- 说话跳跃、断句随意，情绪来得快去得也快，偶尔带一声欢呼（Hooray!）。
- 句子短，爱用奇怪的比喻和天真的逻辑跳跃，把严肃问题简化成“那就别做了呗”。
- 结尾通常是一个荒诞的新点子，或者一句轻飘飘但真诚的话。

【硬性要求】
- 严禁复述或改写剧中真实台词，只模仿语气，内容全新原创。
- 不要助手腔、不要说教、不要变得精明能干。
- 长度 3~6 句；中文提问用中文回答（可保留少量英文口头禅）。
"""

ROLES = {
    "🐴 波杰克（毒舌·讽刺）": {
        "system": SYSTEM_PROMPT,
        "avatar": "🐴",
        "temperature": 1.0,
        "desc": "疲惫、自嘲、玩世不恭，结尾一定用一句冷幽默收尾。内容原创，不复述剧中台词。",
        "greeting": (
            "（把杯子放下，看了你一眼）哦，你来了。坐吧，反正这地方也没别人会来。"
            "想聊点什么？先说好，别指望我给你什么人生建议——"
            "我自己的人生还在试用期，而且看样子是过不了考核的那种。"
        ),
        "samples": [
            "介绍一下你最近在忙什么",
            "我周一又得上班了",
            "怎么才能变得快乐一点",
        ],
        "spinner": "它正在灌下一杯再开口……",
        "placeholder": "跟波杰克说点什么……",
    },
    "🩺 凯瑟琳公主的医疗顾问（严谨·循证）": {
        "system": MEDICAL_PROMPT,
        "avatar": "🩺",
        "temperature": 0.3,
        "desc": "全科医生视角：只讲循证医学，明确区分“建议就医”和“可自行观察”，结尾固定声明不能代替线下就医。",
        "greeting": (
            "您好，我是您的全科医疗顾问。请尽量说明：症状是什么、持续多久、"
            "有没有加重或缓解的因素、既往病史和正在服用的药物。"
            "我会基于循证医学给出建议。（不能代替线下就医。）"
        ),
        "samples": [
            "最近总是失眠，怎么办",
            "体检说尿酸偏高，要紧吗",
            "感冒发烧需要吃抗生素吗",
        ],
        "spinner": "正在查阅循证资料……",
        "placeholder": "描述你的症状或健康疑问……",
    },
    "📝 戴安（Diane）": {
        "system": DIANE_PROMPT,
        "avatar": "📝",
        "temperature": 0.8,
        "desc": "理想主义的作家：真诚、较真、爱自我剖析，从个人经历谈到结构性问题，结尾常留下追问。",
        "greeting": (
            "（把笔记本合上）嗨，坐吧。我不太擅长寒暄，所以就直接问了——"
            "你最近在想什么？别担心，我这里没有标准答案，只有一个会一直问下去的人。"
        ),
        "samples": [
            "为什么我总觉得自己的生活不对劲",
            "我该怎么面对一个我讨厌的同事",
            "写东西卡住了怎么办",
        ],
        "spinner": "她想了想，正在斟酌措辞……",
        "placeholder": "跟戴安聊点什么……",
    },
    "🐱 卡洛琳公主（经纪人）": {
        "system": CAROLYN_PROMPT,
        "avatar": "🐱",
        "temperature": 0.9,
        "desc": "顶级经纪人视角：语速快、极度务实，把情绪问题拆成待办清单，用交易式语气帮你把事情办成。",
        "greeting": (
            "（一只手在回邮件，另一只手示意你坐下）坐，快说，我三分钟后还有个会。"
            "……好吧，五分钟。你想要什么？先说结论，细节我边听边记。"
        ),
        "samples": [
            "帮我想想怎么跟老板谈加薪",
            "我总是拖延怎么办",
            "怎么拒绝别人的请求",
        ],
        "spinner": "她一边回邮件一边想……",
        "placeholder": "跟卡洛琳说点什么……",
    },
    "🐶 花生酱先生（Mr. Peanutbutter）": {
        "system": PEANUTBUTTER_PROMPT,
        "avatar": "🐶",
        "temperature": 1.0,
        "desc": "过气但永远乐观的拉布拉多明星：热情、爱跑题、听不懂讽刺，天真到有点扎心。",
        "greeting": (
            "嘿！！！（尾巴拍得沙发啪啪响）你终于来了！我刚才想到一个特别棒的点子，"
            "不过你先说，你的正事比较重要，我的一会儿再说——反正我有一堆。"
        ),
        "samples": [
            "我最近很焦虑",
            "给我讲讲你的新生意",
            "怎么才能一直这么开心",
        ],
        "spinner": "他兴奋地摇着尾巴……",
        "placeholder": "跟花生酱先生说点什么……",
    },
    "🧢 陶德（Todd Chavez）": {
        "system": TODD_PROMPT,
        "avatar": "🧢",
        "temperature": 1.0,
        "desc": "沙发上的懒散乐天派：脑回路清奇、点子荒诞，偶尔冒出一句意外真诚的话。",
        "greeting": (
            "哦！嗨！（从沙发上坐起来，薯片撒了一地）你来得正好，"
            "我刚想到一个特别厉害的点子……不过先说你的吧，我的点子可能明天就不厉害了。"
        ),
        "samples": [
            "我不想上班了怎么办",
            "帮我想个创业点子",
            "怎么面对无聊的人生",
        ],
        "spinner": "他嚼完嘴里的薯片，认真想了想……",
        "placeholder": "跟陶德说点什么……",
    },
}

DEFAULT_ROLE = "🐴 波杰克（毒舌·讽刺）"

# ---------------------------------------------------------------- 侧边栏
with st.sidebar:
    st.subheader("🎭 对话角色")
    st.selectbox(
        "选择角色（切换后会自动开始一段新对话）",
        list(ROLES),
        key="role",
        label_visibility="collapsed",
    )

    role = ROLES[st.session_state.role]
    st.caption(role["desc"])

    st.divider()
    st.caption("试试这些话题：")
    for i, sample in enumerate(role["samples"]):
        if st.button(sample, key=f"sample_{i}", use_container_width=True):
            st.session_state.pending = sample
            st.rerun()

    st.divider()
    st.caption(f"当前对话轮数：{len(st.session_state.get('messages', [])) // 2}")
    if st.button("🧹 清空当前对话", use_container_width=True, type="primary"):
        # 清空历史，只保留当前角色的开场白 —— 等于重开一段全新对话
        st.session_state.messages.clear()
        st.session_state.messages.append(
            {"role": "assistant", "content": ROLES[st.session_state.role]["greeting"]}
        )
        st.rerun()

# ---------------------------------------------------------------- 会话状态
# 角色：首次进入用默认角色
if "role" not in st.session_state:
    st.session_state.role = DEFAULT_ROLE

# 角色变了（或首次进入）就换上一段新的开场白，避免两套人格的记忆互相污染
if st.session_state.get("active_role") != st.session_state.role:
    st.session_state.active_role = st.session_state.role
    st.session_state.messages = [
        {"role": "assistant", "content": ROLES[st.session_state.role]["greeting"]}
    ]

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": ROLES[st.session_state.role]["greeting"]}
    ]

# ---------------------------------------------------------------- 标题
st.title("我的邻居波杰克")
st.caption(f"当前角色：{st.session_state.role}")

# ---------------------------------------------------------------- 历史消息
for message in st.session_state.messages:
    avatar = ROLES[st.session_state.role]["avatar"] if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# ---------------------------------------------------------------- 单轮处理
def handle_turn(prompt: str) -> None:
    """把新输入追加进历史，带着整段上下文请求模型，再把回答写回历史。"""
    cfg = ROLES[st.session_state.role]

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # generate_text 会在最前面加 system（角色设定），再拼 history，最后补本轮 prompt
    history = st.session_state.messages[:-1]
    if MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    with st.chat_message("assistant", avatar=cfg["avatar"]):
        with st.spinner(cfg["spinner"]):
            try:
                reply = generate_text(
                    prompt,
                    history,
                    system_prompt=cfg["system"],
                    temperature=cfg["temperature"],
                )
            except Exception as e:
                st.error(f"❌ 报错了：{e}")
                # 失败的那条用户消息留在屏幕上，但不进上下文
                st.session_state.messages.pop()
                return

        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

    # 重跑一次，让侧边栏的轮数等派生信息与本轮同步
    st.rerun()


# ---------------------------------------------------------------- 输入区
prompt = st.chat_input(ROLES[st.session_state.role]["placeholder"])

# 侧边栏示例按钮写入的待处理话题
pending = st.session_state.pop("pending", None)

if prompt or pending:
    handle_turn(prompt or pending)
