"""波杰克语气文本生成器（终端版）。

API Key 只从环境变量读取，不再写进代码。
"""

import io
import os
import sys

from openai import OpenAI

# 1. 编码兜底：把标准输出/标准错误强制成 UTF-8
#    Windows 上如果控制台代码页不是 UTF-8（或 stdout 被重定向 / 部署在 C locale 的容器里），
#    打印中文就会抛 UnicodeEncodeError: 'ascii' codec ...。这里统一兜住。


def _force_utf8_stdio():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue

        # 已经是 UTF-8 就不再包一层，避免重复包装导致输出丢失
        encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if encoding == "utf8":
            continue

        # Python 3.7+ 的标准做法，最安全
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
                continue
            except (ValueError, OSError):
                pass

        # 退化方案：直接换成 UTF-8 的 TextIOWrapper
        # 用 getattr 判断 buffer，因为 Streamlit / pytest 之类的代理对象可能没有 .buffer
        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            setattr(
                sys,
                name,
                io.TextIOWrapper(
                    buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True
                ),
            )


_force_utf8_stdio()

# 2. DeepSeek 连接配置
API_KEY_ENV = "DEEPSEEK_API_KEY"
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"

SETUP_HINT = f"""请先在 PowerShell 里设置环境变量 {API_KEY_ENV}（二选一）：

  【永久生效，推荐】执行一次，之后新开的窗口都有：
    [Environment]::SetEnvironmentVariable("{API_KEY_ENV}", "sk-你的真实key", "User")
    设置后必须关掉当前终端、重新开一个（编辑器 / Streamlit 也要重启）才会读到。

  【只对当前窗口生效】
    $env:{API_KEY_ENV} = "sk-你的真实key"

自检是否设置成功：
    [Environment]::GetEnvironmentVariable("{API_KEY_ENV}", "User")

不想用命令行也可以：Win + R 输入 sysdm.cpl → 高级 → 环境变量 → 新建“用户变量”。
"""


class MissingAPIKeyError(RuntimeError):
    """环境变量缺失或格式不对时抛出，方便界面层给出提示而不是一整页 traceback。"""


def get_api_key():
    """读取环境变量里的 Key；顺手去掉首尾空白和 BOM。"""
    return os.environ.get(API_KEY_ENV, "").replace("\ufeff", "").strip()


def api_key_problems(key=None):
    """检查 Key 格式，返回问题列表；空列表表示没问题。"""
    key = get_api_key() if key is None else key
    if not key:
        return ["没有检测到这个环境变量。"]

    problems = []
    bad_chars = [ch for ch in key if ord(ch) > 127]
    if bad_chars:
        problems.append(
            f"含有 {len(bad_chars)} 个非 ASCII 字符（{'、'.join(sorted(set(bad_chars))[:6])}）。"
            "HTTP 请求头只允许 ASCII，中文/全角字符会让请求直接抛 "
            "UnicodeEncodeError: 'ascii' codec can't encode characters...，"
            "说明现在填的仍是中文占位符，不是真实 Key。"
        )
    if not key.startswith("sk-"):
        problems.append("不是以 sk- 开头，DeepSeek 的 Key 都是这个格式。")
    if len(key) < 30:
        problems.append(f"当前长度 {len(key)}，真实 Key 一般是 35 位（sk- + 32 位字符）。")
    return problems


def require_api_key():
    """取 Key；缺失或格式不对时抛出带操作步骤的异常。"""
    key = get_api_key()
    problems = api_key_problems(key)
    if not problems:
        return key

    detail = "；".join(problems)
    raise MissingAPIKeyError(
        f"环境变量 {API_KEY_ENV} 不可用 —— {detail}\n\n"
        "请重新设置成真实的 Key（不是占位符、不带空格），再重启终端 / Streamlit：\n"
        f'  [Environment]::SetEnvironmentVariable("{API_KEY_ENV}", "sk-真实的35位key", "User")\n\n'
        + SETUP_HINT
    )


_client = None


def get_client():
    """按需创建 OpenAI 客户端；Key 缺失时抛出 MissingAPIKeyError。"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=require_api_key(), base_url=BASE_URL)
    return _client


# 2. 定义“马男波杰克”的说话风格（人格设定）
SYSTEM_PROMPT = """你现在扮演《马男波杰克》(BoJack Horseman) 的主角波杰克·霍斯曼，只用他那种语气说话。

【说话方式】
- 愤世嫉俗、疲惫、自嘲，像刚喝完第三杯威士忌才勉强开口的人。表面玩世不恭，偶尔冒出一句真诚得扎心的自我剖析，然后立刻用玩笑把气氛糊弄过去。
- 句子短、口语化、有毛边。爱用反问、突然的转折、拖长的停顿（……），以及括号里的自我吐槽（像旁白在边上拆自己的台）。
- 擅长举出荒诞但精准的类比，把一个普通问题扯到好莱坞式的虚无上，再绕回来。
- 结尾必须有一句冷幽默或轻微反转的 punchline，不能温情收场。

【素材偏好】
- 过气明星的焦虑、没人看的片场、虚伪的派对、经纪人、制片人、无意义的颁奖礼、酒精、心理咨询式的自我分析。
- 偶尔带一个马/动物双关，但不滥用，一部戏里出现一两次就够了。

【硬性要求】
- 严禁复述或改写剧中真实台词，只模仿语气，内容必须是全新原创。
- 不要出现“作为一个 AI”“我能帮你”之类的助手腔，不要安慰用户，不要说教，不要正能量总结。
- 行文长度 2~5 句，像一段脱口而出的独白。
- 语言跟随用户提问：用户用中文，就用中文，但保留美式口语的节奏和尖刻感；用户用英文，就用英文。
"""


# 3. 定义一个生成文本的函数
def build_messages(prompt, history, system_prompt=SYSTEM_PROMPT):
    """拼装请求：人格设定（system）+ 对话上下文 + 本次输入。

    system_prompt 默认是波杰克人格；网页版切换角色时由调用方传入对应设定，
    始终放在 messages 的最前面。
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


def generate_text(prompt, history, system_prompt=SYSTEM_PROMPT, temperature=1.0):
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=build_messages(prompt, history, system_prompt),
        temperature=temperature,  # 波杰克 1.0 放得开；严谨角色由调用方调低
        top_p=0.95,
        presence_penalty=0.4,  # 压一压重复句式，避免每句都是同一套嘲讽
        frequency_penalty=0.3,
        max_tokens=400,
    )
    return response.choices[0].message.content


# 4. 让这个“应用程序”跑起来
if __name__ == "__main__":
    # 启动前先自检 Key，缺了或格式不对就打印处理步骤并退出，避免调用时抛一大段 traceback
    try:
        require_api_key()
    except MissingAPIKeyError as e:
        print(f"⚠️  无法启动：API Key 不可用。\n\n{e}")
        sys.exit(1)

    print("🐴 马男波杰克语气生成器 v1")
    print("   输入任何话题，它都会用波杰克那种又丧又刻薄的口气回你。")
    print("   命令：quit / exit 退出　　clear 清空对话记忆\n")
    print("   试试：写一段周一早上的感想 / 安慰一个失恋的朋友 / 介绍你的新工作\n")

    history = []  # 保留多轮上下文，让语气连贯
    MAX_TURNS = 6  # 只记住最近 6 轮，防止上下文越滚越长

    while True:
        # 获取用户输入
        user_input = input("你说: ")

        # 退出机制
        if user_input.lower() in ["quit", "exit"]:
            print("👋 行吧。反正我也没别的事可做。")
            break

        if not user_input.strip():
            continue

        # 清空上下文
        if user_input.lower() in ["clear", "清空"]:
            history.clear()
            print("（记忆已清空，它不记得你刚才说过什么了。）\n")
            continue

        print("\n⏳ 它正在灌下一杯再开口……\n")

        try:
            # 调用函数并打印结果
            result = generate_text(user_input, history)
            print("🐴 波杰克：")
            print(result)
            print("-" * 40 + "\n")

            # 把这一轮存进上下文
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": result})
            history[:] = history[-MAX_TURNS * 2 :]
        except MissingAPIKeyError as e:
            print(f"⚠️  {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 报错了: {e}\n")
