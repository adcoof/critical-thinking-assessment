"""
审辩思维AI测评智能体 —— 单文件版（无模块缓存问题）
"""

import streamlit as st
import json
import time
import random
import re
import os
from pathlib import Path
import plotly.graph_objects as go

# ══════════════════════════════════════════════════════════════
# 全部逻辑内联，不引用任何外部模块
# ══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
CASES_DIR = BASE_DIR / "cases"
RUBRICS_DIR = BASE_DIR / "rubrics"
DATA_DIR = BASE_DIR / "data"

# 自动创建必要的目录
for d in [CASES_DIR, RUBRICS_DIR, DATA_DIR]:
    d.mkdir(exist_ok=True)

# ── 工具函数 ─────────────────────────────────────────────────

def analyze_answer(text):
    result = {"length": len(text), "has_data": False, "has_reasoning": False,
              "has_multiple_view": False, "has_plan": False, "has_adjustment": False,
              "has_question_define": False, "data_cited": []}
    data_kw = ["满意度", "投诉", "时长", "准确率", "%", "万", "数据", "统计", "比例"]
    for kw in data_kw:
        if kw in text:
            result["has_data"] = True
            result["data_cited"].append(kw)
    reasoning_kw = ["因为", "所以", "因此", "说明", "表明", "意味着", "矛盾", "冲突",
                     "相比", "虽然", "尽管", "权衡", "利弊"]
    for w in reasoning_kw:
        if w in text:
            result["has_reasoning"] = True
            break
    view_kw = ["但是", "另一方面", "同时", "此外", "也要考虑", "从用户", "从公司",
               "竞品", "不同群体", "老年", "员工", "利益相关"]
    for w in view_kw:
        if w in text:
            result["has_multiple_view"] = True
            break
    plan_kw = ["建议", "方案", "应该", "分阶段", "第一步", "推进", "上线", "暂缓"]
    for w in plan_kw:
        if w in text:
            result["has_plan"] = True
            break
    adjust_kw = ["如果", "假设", "调整", "修正", "视情况", "灵活", "再评估"]
    for w in adjust_kw:
        if w in text:
            result["has_adjustment"] = True
            break
    define_kw = ["核心", "关键", "矛盾", "本质", "根本", "在于"]
    for w in define_kw:
        if w in text:
            result["has_question_define"] = True
            break
    return result


def extract_student_answer(prompt):
    for marker in ["STUDENT_ANSWER: ", "受测者回答："]:
        if marker in prompt:
            idx = prompt.index(marker) + len(marker)
            return prompt[idx:idx + 500].split("\n")[0].strip()
    lines = [l.strip() for l in prompt.split("\n") if l.strip()]
    return lines[-1] if lines else prompt


# ── 行为识别 ─────────────────────────────────────────────────

def behavior_analyze(answer):
    a = analyze_answer(answer)
    evidence, tags = [], []
    sentences = re.split(r'[。！？；\n]', answer)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]

    tag_map = {
        "问题界定": ("has_question_define", ["核心", "关键", "矛盾", "本质", "在于"]),
        "证据评估": ("has_data", ["满意度", "投诉", "%", "万", "数据"]),
        "推理论证": ("has_reasoning", ["因为", "所以", "因此", "说明", "表明", "矛盾"]),
        "多元视角": ("has_multiple_view", ["同时", "另一方面", "从用户", "竞品", "老年"]),
        "整合决策": ("has_plan", ["建议", "方案", "应该", "分阶段", "推进"]),
        "动态调整": ("has_adjustment", ["如果", "假设", "调整", "修正", "视情况"]),
    }
    for tag, (key, kw_list) in tag_map.items():
        if a[key]:
            tags.append(tag)
            for s in sentences:
                if any(w in s for w in kw_list):
                    evidence.append(s)
                    break
    if not tags:
        tags = ["推理论证"]
        evidence = sentences[:2] if sentences else [answer[:60]]
    return {"evidence_sentences": evidence[:3], "behavior_tags": list(set(tags))}


# ── 评分 ─────────────────────────────────────────────────────

def score_turn(answer, behavior_result):
    a = analyze_answer(answer)
    tags = behavior_result["behavior_tags"]
    scores = {}
    scores["问题界定"] = min(5, (4 if a["has_question_define"] else 2) + (1 if a["length"] > 80 else 0))
    dc = len(a["data_cited"])
    scores["证据评估"] = min(5, max(1, dc + 1)) if dc > 0 else (3 if "证据评估" in tags else 1)
    scores["推理论证"] = 4 if (a["has_reasoning"] and a["length"] > 60) else (3 if a["has_reasoning"] else 2)
    scores["多元视角"] = 5 if (a["has_multiple_view"] and a["length"] > 80) else (4 if a["has_multiple_view"] else (3 if "多元视角" in tags else 1))
    scores["整合决策"] = 5 if (a["has_plan"] and a["length"] > 80) else (4 if a["has_plan"] else (3 if "整合决策" in tags else 1))
    scores["动态调整"] = 5 if (a["has_adjustment"] and a["has_reasoning"]) else (4 if a["has_adjustment"] else (3 if "动态调整" in tags else 1))
    return scores


# ── 主持 ─────────────────────────────────────────────────────

def host_start(case):
    bg = case.get("background", {})
    role = bg.get("role", "决策者")
    situation = bg.get("situation", "你面临一个重要决策")
    init_data = bg.get("initial_data", {})
    lines = ["欢迎参与审辩思维测评！", "", "【情境背景】", "你是%s。" % role, situation, ""]
    if isinstance(init_data, dict):
        lines.append("关键数据：")
        for v in init_data.values():
            lines.append("• %s" % v)
    lines += ["", "请基于以上信息，谈谈你的初步判断。"]
    return "\n".join(lines)


def host_next_turn(case, turn_number):
    for d in case.get("progressive_disclosure", []):
        if d.get("turn") == turn_number:
            return "【补充信息】" + d.get("content", "") + "\n\n请基于以上新信息，继续你的分析。"
    if turn_number >= case.get("estimated_turns", 16):
        return "感谢你的参与！测评到此结束。系统将自动生成你的测评报告，请稍候..."
    return "请继续。你可以补充更多理由，或回应刚才的追问。"


# ── 追问 ─────────────────────────────────────────────────────

def probe_generate(answer):
    a = analyze_answer(answer)
    probes = []
    if not a["has_data"]:
        probes.append("你的分析有道理，但能否引用具体数据来支撑观点？")
    if not a["has_reasoning"]:
        probes.append("能否进一步解释你的推理过程？是什么让你得出这个结论？")
    if not a["has_multiple_view"]:
        probes.append("你主要从一个角度分析，能否考虑其他利益相关者的立场？")
    if not a["has_plan"]:
        probes.append("如果要给出具体方案，你会怎么规划实施步骤？")
    if not a["has_adjustment"]:
        probes.append("假设出现新情况，你会怎么调整你的决策？")
    if not a["has_question_define"]:
        probes.append("在这个决策中，你认为最核心的矛盾是什么？")
    if a["length"] > 100 and a["has_data"] and a["has_reasoning"]:
        probes.append("你的论证很有说服力。你觉得这个决策最大的风险是什么？")
    return random.choice(probes) if probes else "能否再详细说明你的理由？"


# ── 挑战 ─────────────────────────────────────────────────────

def challenge_generate(answer):
    neg = ["不", "暂缓", "谨慎", "禁止", "反对"]
    pos = ["推进", "支持", "应该", "同意", "上线", "允许"]
    is_neg = any(w in answer for w in neg)
    is_pos = any(w in answer for w in pos)
    if is_neg:
        pool = [
            "【反方观点】有支持者认为这样做会让我们落后于竞争对手，你如何回应？",
            "【冲突信息】有数据显示类似做法在其他地方取得了积极效果，这是否动摇你的判断？",
            "【反方观点】如果因为过于保守而错失机会，这个责任谁来承担？",
        ]
    elif is_pos:
        pool = [
            "【反方观点】有反对者指出这样做会带来严重负面影响，你如何回应？",
            "【冲突信息】有数据显示类似做法在其他地方产生了不良后果，你是否重新考虑？",
            "【反方观点】有人质疑你没有充分考虑弱势群体的权益，你怎么看？",
        ]
    else:
        pool = [
            "【反方观点】有支持者认为这件事利大于弊应该尽快推进，你如何看待？",
            "【反方观点】有反对者认为弊大于利应该暂缓，你如何回应？",
            "【冲突信息】不同群体看法差异很大，你如何平衡各方利益？",
        ]
    return random.choice(pool)


# ── 审计 ─────────────────────────────────────────────────────

def audit_score(scores, behavior_result):
    high = [d for d, s in scores.items() if s >= 4]
    issues = []
    for d in high:
        if d not in behavior_result["behavior_tags"]:
            issues.append("%s评分较高但未检测到对应行为" % d)
    return {"status": "通过" if not issues else "待复核", "issues": issues}


# ── 报告生成 ─────────────────────────────────────────────────

def generate_report(final_scores, evidence_list, total_turns, audit_results):
    total = sum(final_scores.values())
    avg = total / len(final_scores) if final_scores else 0

    dim_comments = {
        "问题界定": {5: "能精准识别核心矛盾", 4: "能准确识别核心矛盾", 3: "基本触及问题核心", 2: "问题识别较表面", 1: "未能识别核心问题"},
        "证据评估": {5: "善于引用数据并批判性分析", 4: "能引用充分数据支撑", 3: "有基本数据引用", 2: "数据引用不足", 1: "缺少数据支撑"},
        "推理论证": {5: "逻辑严密，论证有力", 4: "逻辑清晰，论证合理", 3: "推理基本合理", 2: "论证不够充分", 1: "缺少逻辑支撑"},
        "多元视角": {5: "能系统考虑多方利益", 4: "能考虑多方立场", 3: "有一定多角度分析", 2: "视角较单一", 1: "仅从单一视角分析"},
        "整合决策": {5: "方案具体可执行且有预案", 4: "方案具体可执行", 3: "提出基本方向", 2: "方案不够具体", 1: "无法提出明确方案"},
        "动态调整": {5: "能主动根据新信息修正判断", 4: "能合理调整判断", 3: "有一定调整意识", 2: "调整幅度不足", 1: "固守原有立场"},
    }

    passed = sum(1 for r in audit_results if r["status"] == "通过")

    rpt = "# 审辩思维测评报告\n\n"
    rpt += "## 一、测评概览\n"
    rpt += "- **总轮次**：%d 轮\n" % total_turns
    rpt += "- **综合得分**：%d/30（均分 %.1f）\n\n" % (total, avg)

    if avg >= 4.5:
        rpt += "> 🌟 优秀：审辩思维能力突出\n\n"
    elif avg >= 3.5:
        rpt += "> 👍 良好：具备较好的审辩思维基础\n\n"
    elif avg >= 2.5:
        rpt += "> 📈 中等：建议加强系统性训练\n\n"
    else:
        rpt += "> 💪 待提升：建议从基础训练开始\n\n"

    rpt += "## 二、六维能力评分\n\n| 维度 | 得分 | 评价 |\n|------|------|------|\n"
    for dim, score in final_scores.items():
        bar = "█" * score + "░" * (5 - score)
        comment = dim_comments.get(dim, {}).get(score, "")
        rpt += "| %s | %s %d/5 | %s |\n" % (dim, bar, score, comment)

    rpt += "\n## 三、关键行为证据\n"
    for i, ev in enumerate(evidence_list[-10:], 1):
        rpt += "%d. 「%s」\n" % (i, ev)

    rpt += "\n## 四、思维优势\n"
    top = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:2]
    for d, s in top:
        rpt += "- **%s**（%d/5）：%s\n" % (d, s, dim_comments.get(d, {}).get(s, ""))

    rpt += "\n## 五、待提升维度\n"
    low = sorted(final_scores.items(), key=lambda x: x[1])[:2]
    for d, s in low:
        rpt += "- **%s**（%d/5）：%s\n" % (d, s, dim_comments.get(d, {}).get(s, ""))

    rpt += "\n## 六、发展建议\n"
    suggestions = []
    if final_scores.get("证据评估", 0) < 4:
        suggestions.append("表达观点时，主动引用具体数据来支撑论证")
    if final_scores.get("多元视角", 0) < 4:
        suggestions.append("分析问题时，主动考虑不同利益相关者的立场")
    if final_scores.get("推理论证", 0) < 4:
        suggestions.append("建立完整的论证链条：证据→推理→结论")
    if final_scores.get("整合决策", 0) < 4:
        suggestions.append("决策时明确步骤、时间节点、风险预案")
    if final_scores.get("动态调整", 0) < 4:
        suggestions.append("遇到新信息时，主动修正原有判断")
    if final_scores.get("问题界定", 0) < 4:
        suggestions.append("先用一句话概括核心矛盾，确保分析不偏离")
    if not suggestions:
        suggestions = ["保持良好的审辩思维习惯", "尝试从对立面思考问题"]
    for i, s in enumerate(suggestions, 1):
        rpt += "%d. %s\n" % (i, s)

    rpt += "\n---\n*本报告由AI审辩思维测评智能体自动生成*\n"
    return rpt


# ══════════════════════════════════════════════════════════════
# Streamlit 主程序
# ══════════════════════════════════════════════════════════════

st.set_page_config(page_title="审辩思维AI测评智能体", page_icon="🧠", layout="wide")

# 自定义CSS样式 - Apple Design System
st.markdown("""
<style>
    /* Apple 配色方案 */
    :root {
        --apple-primary: #0066cc;
        --apple-primary-focus: #0071e3;
        --apple-primary-on-dark: #2997ff;
        --apple-ink: #1d1d1f;
        --apple-ink-muted-80: #333333;
        --apple-ink-muted-48: #7a7a7a;
        --apple-canvas: #ffffff;
        --apple-canvas-parchment: #f5f5f7;
        --apple-surface-pearl: #fafafc;
        --apple-hairline: #e0e0e0;
        --apple-divider-soft: #f0f0f0;
    }

    .stApp {
        background-color: var(--apple-canvas-parchment);
        color: var(--apple-ink);
    }
    .stApp > header {
        background-color: var(--apple-canvas);
    }
    [data-testid="stSidebar"] {
        background-color: var(--apple-surface-pearl);
        color: var(--apple-ink);
    }
    [data-testid="stSidebar"] > div:first-child {
        background-color: var(--apple-surface-pearl);
    }
    /* 主要文本元素 - Apple Near-Black Ink */
    h1, h2, h3, h4, h5, h6,
    .stMarkdown,
    .stMarkdown p,
    .stMarkdown li,
    .stMarkdown span,
    label,
    .stButton > button,
    .stSelectbox label,
    .stTextInput label,
    .stTextArea label,
    .stMetric label,
    .stMetric [data-testid="stMetricValue"],
    .stMetric [data-testid="stMetricDelta"],
    .stProgress > div > div > div > div {
        color: var(--apple-ink) !important;
    }
    /* 主要按钮 - Apple Action Blue */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background-color: var(--apple-primary) !important;
        color: #ffffff !important;
        border-radius: 9999px !important;
    }
    /* 次要按钮 */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"] {
        background-color: var(--apple-canvas) !important;
        color: var(--apple-primary) !important;
        border: 1px solid var(--apple-primary) !important;
        border-radius: 9999px !important;
    }
    /* 链接颜色 - Apple Action Blue */
    a {
        color: var(--apple-primary) !important;
    }
    /* 代码块 */
    code {
        color: #d63384 !important;
        background-color: var(--apple-canvas-parchment) !important;
    }
    /* 侧边栏特定元素 */
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label {
        color: var(--apple-ink) !important;
    }
    /* 分割线 */
    hr {
        border-color: var(--apple-hairline) !important;
    }
    /* 输入框样式 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-color: var(--apple-hairline) !important;
        border-radius: 8px !important;
    }
    /* 选择框样式 */
    .stSelectbox > div > div {
        border-color: var(--apple-hairline) !important;
        border-radius: 8px !important;
    }
    /* 指标卡片 */
    [data-testid="stMetric"] {
        background-color: var(--apple-canvas) !important;
        padding: 16px !important;
        border-radius: 12px !important;
        border: 1px solid var(--apple-hairline) !important;
    }
    /* 进度条 */
    .stProgress > div > div > div {
        background-color: var(--apple-primary) !important;
    }
    /* 下载按钮样式 - 固定白色背景黑色字体 */
    .stDownloadButton > button,
    .stDownloadButton > button[kind="secondary"],
    .stDownloadButton > button[data-testid="stBaseButton-secondary"] {
        background-color: #ffffff !important;
        color: #1d1d1f !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    .stDownloadButton > button:hover,
    .stDownloadButton > button[kind="secondary"]:hover,
    .stDownloadButton > button[data-testid="stBaseButton-secondary"]:hover {
        background-color: #f5f5f7 !important;
        border-color: #d0d0d0 !important;
    }
</style>
""", unsafe_allow_html=True)

if "phase" not in st.session_state:
    st.session_state.phase = "intro"
    st.session_state.turn_number = 0
    st.session_state.student_msgs = []
    st.session_state.agent_msgs = []
    st.session_state.evidence_all = []
    st.session_state.scores_per_turn = []
    st.session_state.audit_results = []
    st.session_state.final_scores = {}
    st.session_state.report = ""
    st.session_state.case = None

# ── 侧边栏 ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/3d-fluency/94/brain.png", width=64)
    st.title("审辩思维AI测评")
    st.caption("基于多Agent互动式SJT的动态测评系统")
    st.divider()

    case_files = sorted(CASES_DIR.glob("*.json"))
    case_names = [f.stem for f in case_files]
    selected = st.selectbox("📋 选择测评情境", case_names)

    if st.button("🚀 开始测评", use_container_width=True, type="primary"):
        case_path = CASES_DIR / ("%s.json" % selected)
        with open(case_path, "r", encoding="utf-8") as f:
            st.session_state.case = json.load(f)
        st.session_state.phase = "briefing"
        st.session_state.turn_number = 0
        st.session_state.student_msgs = []
        st.session_state.agent_msgs = []
        st.session_state.evidence_all = []
        st.session_state.scores_per_turn = []
        st.session_state.audit_results = []
        st.session_state.final_scores = {}
        st.session_state.report = ""
        st.rerun()

    st.divider()
    st.markdown("### 📊 测评进度")
    if st.session_state.phase in ("chatting",):
        st.progress(min(st.session_state.turn_number / 16, 1.0), text="第 %d/16 轮" % st.session_state.turn_number)
    elif st.session_state.phase == "report":
        st.success("✅ 测评完成")
    else:
        st.info("等待开始...")

# ── Intro ────────────────────────────────────────────────────
if st.session_state.phase == "intro":
    st.markdown("""
# 🧠 审辩思维AI测评智能体

### 基于多Agent互动式SJT的大学生审辩思维动态测评系统

---

| Agent | 职责 |
|-------|------|
| 🎙️ 主持Agent | 呈现情境、控制节奏 |
| 🔍 追问Agent | 生成开放式追问 |
| ⚔️ 挑战Agent | 提出反方观点 |
| 🏷️ 行为识别Agent | 提取证据句和行为标签 |
| 📊 评分Agent | 六维能力评分（1-5分）|
| ✅ 审计Agent | 评分质量复核 |
| 📝 报告Agent | 生成结构化报告 |

### 🎯 六维能力模型
1. **问题界定** — 识别核心矛盾
2. **证据评估** — 判断信息质量
3. **推理论证** — 逻辑论证能力
4. **多元视角** — 多方利益考量
5. **整合决策** — 方案制定能力
6. **动态调整** — 根据新信息修正判断

👈 **请在左侧选择情境并点击"开始测评"**
""")

# ── Briefing ─────────────────────────────────────────────────
elif st.session_state.phase == "briefing":
    st.markdown("## 📋 测评情境")
    intro = host_start(st.session_state.case)
    st.session_state.agent_msgs.append(intro)
    st.session_state.phase = "chatting"
    st.rerun()

# ── Chatting ─────────────────────────────────────────────────
elif st.session_state.phase == "chatting":
    st.markdown("## 💬 测评对话 — 第 %d 轮" % st.session_state.turn_number)

    with st.container():
        for msg in st.session_state.agent_msgs:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(msg)
        for msg in st.session_state.student_msgs:
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg)

    if st.session_state.turn_number < 16:
        user_input = st.chat_input("请输入你的回答...")
        if user_input:
            st.session_state.student_msgs.append(user_input)
            st.session_state.turn_number += 1

            with st.spinner("🤖 Agent正在分析你的回答..."):
                # 1. 行为识别
                behavior = behavior_analyze(user_input)
                st.session_state.evidence_all.extend(behavior["evidence_sentences"])

                # 2. 评分
                scores = score_turn(user_input, behavior)
                st.session_state.scores_per_turn.append(scores)

                # 3. 审计
                audit = audit_score(scores, behavior)
                st.session_state.audit_results.append(audit)

                # 4. 追问或挑战
                if st.session_state.turn_number % 3 == 0:
                    agent_reply = challenge_generate(user_input)
                else:
                    agent_reply = probe_generate(user_input)

                # 5. 主持节奏
                host_msg = host_next_turn(st.session_state.case, st.session_state.turn_number)

                full_reply = "**🔍 追问：** %s\n\n---\n\n%s" % (agent_reply, host_msg)

                # 渐进信息披露
                for d in st.session_state.case.get("progressive_disclosure", []):
                    if d.get("turn") == st.session_state.turn_number:
                        full_reply = "📢 **%s**\n\n---\n\n%s" % (d["content"], full_reply)

                st.session_state.agent_msgs.append(full_reply)

            st.rerun()
    else:
        # 计算最终分数
        final = {}
        for dim in ["问题界定", "证据评估", "推理论证", "多元视角", "整合决策", "动态调整"]:
            dim_scores = [s.get(dim, 3) for s in st.session_state.scores_per_turn]
            final[dim] = max(dim_scores) if dim_scores else 3
        st.session_state.final_scores = final
        st.session_state.phase = "analyzing"
        st.rerun()

# ── Analyzing ────────────────────────────────────────────────
elif st.session_state.phase == "analyzing":
    st.markdown("## ⏳ 正在生成测评报告...")
    progress = st.progress(0, text="分析中...")
    for pct, txt in [(20, "汇总行为证据..."), (50, "计算六维得分..."), (80, "生成报告..."), (100, "完成！")]:
        time.sleep(0.3)
        progress.progress(pct, text=txt)

    st.session_state.report = generate_report(
        st.session_state.final_scores,
        st.session_state.evidence_all,
        st.session_state.turn_number,
        st.session_state.audit_results,
    )

    # 保存日志
    log = {"turn": st.session_state.turn_number, "students": st.session_state.student_msgs,
           "evidence": st.session_state.evidence_all, "scores": st.session_state.final_scores}
    with open(DATA_DIR / ("log_%d.json" % int(time.time())), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    st.session_state.phase = "report"
    st.rerun()

# ── Report ───────────────────────────────────────────────────
elif st.session_state.phase == "report":
    st.markdown("## 📊 测评报告")

    col1, col2 = st.columns([2, 3])
    with col1:
        st.markdown("### 🎯 六维能力得分")
        scores = st.session_state.final_scores
        total = sum(scores.values())
        st.metric("综合得分", "%d/30" % total, "均分 %.1f" % (total / 6))
        for dim, score in scores.items():
            st.progress(score / 5, text="%s: %d/5" % (dim, score))

    with col2:
        st.markdown("### 📈 能力雷达图")
        # 创建雷达图 - Apple Design System 配色
        categories = list(scores.keys())
        values = list(scores.values())

        # 闭合雷达图（首尾相连）
        categories_closed = categories + [categories[0]]
        values_closed = values + [values[0]]

        # Apple Action Blue (#0066cc) 配色方案
        apple_blue = '#0066cc'
        apple_blue_light = 'rgba(0, 102, 204, 0.15)'

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill='toself',
            name='能力得分',
            line=dict(color=apple_blue, width=2),
            fillcolor=apple_blue_light,
            hovertemplate='<b>%{theta}</b><br>得分: %{r}/5<extra></extra>'
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 5],
                    tickvals=[1, 2, 3, 4, 5],
                    ticktext=['1', '2', '3', '4', '5'],
                    tickfont=dict(size=11, color='#1d1d1f'),
                    gridcolor='#e0e0e0',
                    linecolor='#e0e0e0'
                ),
                angularaxis=dict(
                    tickfont=dict(size=12, color='#1d1d1f'),
                    gridcolor='#e0e0e0',
                    linecolor='#e0e0e0'
                ),
                bgcolor='#ffffff'
            ),
            paper_bgcolor='#ffffff',
            plot_bgcolor='#ffffff',
            font=dict(family="SF Pro Text, system-ui, -apple-system, sans-serif"),
            showlegend=False,
            margin=dict(l=60, r=60, t=40, b=40),
            height=350
        )

        st.plotly_chart(fig, use_container_width=True)

        # 导出按钮
        col_export1, col_export2 = st.columns(2)
        with col_export1:
            # 导出为HTML
            html_str = fig.to_html(include_plotlyjs='cdn', full_html=True)
            st.download_button(
                label="📥 导出HTML",
                data=html_str,
                file_name="能力雷达图.html",
                mime="text/html",
                use_container_width=True
            )
        with col_export2:
            # 导出为PNG（需要安装 kaleido）
            try:
                img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
                st.download_button(
                    label="📥 导出PNG",
                    data=img_bytes,
                    file_name="能力雷达图.png",
                    mime="image/png",
                    use_container_width=True
                )
            except Exception as e:
                st.info("PNG导出需要安装 kaleido：pip install kaleido")

    st.divider()

    passed = sum(1 for r in st.session_state.audit_results if r["status"] == "通过")
    st.markdown("### ✅ 评分审计结果")
    c1, c2, c3 = st.columns(3)
    c1.metric("已审核", len(st.session_state.audit_results))
    c2.metric("通过", passed)
    c3.metric("待复核", len(st.session_state.audit_results) - passed)

    st.divider()
    st.markdown("### 📝 完整测评报告")
    st.markdown(st.session_state.report)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 重新测评", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    with c2:
        st.download_button("📥 下载报告", st.session_state.report, "审辩思维测评报告.md", "text/markdown", use_container_width=True)
