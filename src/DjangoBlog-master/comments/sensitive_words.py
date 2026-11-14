# ============================================================
# comments/sensitive_words.py —— 评论敏感词过滤
# ============================================================
# 对应《comments模块质量分析报告》Q4：评论提交无内容过滤。
# 集成点：views.CommentPostView.form_valid 在评论开关校验之后、
# 入库之前调用 check_sensitive_words()，命中即拒绝提交。
# 设计要点（见 doc/comments敏感词过滤设计方案.md）：
#   - 纯函数、无副作用：输入正文，输出命中词列表，便于单元测试
#   - 词库为模块级常量，集中一处；后续可替换为文件/数据库加载
#   - 匹配前统一小写，英文词不区分大小写；中文按子串匹配
# ============================================================

# 敏感词库（演示用小词表，可按需扩充；词库变更仅需改本文件）
SENSITIVE_WORDS = [
    "赌博",
    "博彩",
    "代开发票",
    "刷单",
    "诈骗",
    "色情",
]


def load_sensitive_words():
    """
    加载敏感词库。

    当前实现：直接返回模块常量（保持零依赖、零 IO）。
    预留扩展点：后续若需要运营侧动态维护词库，可将此处替换为
    读取文件 / BlogSettings / 数据库表，并配合缓存避免每次请求读库。
    """
    return SENSITIVE_WORDS


def check_sensitive_words(text):
    """
    检查文本中是否包含敏感词。

    参数:
        text: 待检查的评论正文（str）
    返回:
        命中的敏感词列表（去重、保持词库顺序）；无命中返回空列表 []

    匹配策略：
        ① text 统一转小写，实现英文词大小写归一化（'Spam' 等价 'spam'）
        ② 词库中每个词同样小写后做子串匹配（中文子串不受大小写影响）
        ③ 词库规模小（O(n*m)，m=正文长度上限 300），提交路径开销可忽略；
           词库扩充到千级以上时建议换 Aho-Corasick 多模式匹配
    """
    if not text:
        return []
    normalized = text.lower()
    return [
        word for word in load_sensitive_words()
        # 跳过空串/纯空白词：空串是任何文本的子串，会造成全量误命中
        if word.strip() and word.lower() in normalized
    ]
