# -*- coding: utf-8 -*-
"""拼音切分（动态规划 DAG）

将连续拼音串切分为合法音节序列。
例：nihao -> [['ni', 'hao']]
    xian  -> [['xian'], ['xi', 'an']]

算法：构建有向无环图（DAG），节点为字符位置，边为合法音节。
枚举所有从起点到终点的路径即为所有合法切分。
"""
from .syllables import VALID_SYLLABLES, MAX_SYLLABLE_LEN


def _build_dag(s):
    """构建 DAG：{位置i: [可达位置j列表]}

    对每个位置 i，尝试所有长度 1..MAX_SYLLABLE_LEN 的子串 s[i:j]，
    若是合法音节则加入边 i->j。
    """
    n = len(s)
    dag = {i: [] for i in range(n + 1)}
    for i in range(n):
        max_j = min(i + MAX_SYLLABLE_LEN, n)
        for j in range(i + 1, max_j + 1):
            if s[i:j] in VALID_SYLLABLES:
                dag[i].append(j)
    return dag


def split_pinyin(s):
    """返回所有合法切分

    Args:
        s: 拼音串（仅小写字母）

    Returns:
        切分列表，如 [['ni','hao']]
        含非 a-z 字符、空串无切分、或无法切分时返回 [[s]]（echo fallback）
    """
    if not s:
        return [[]]

    # 仅接受纯小写字母；其他字符原样返回（echo fallback）
    if not all('a' <= c <= 'z' for c in s):
        return [[s]]

    n = len(s)
    dag = _build_dag(s)

    # 起点无出边，说明第一个字符就不能构成任何音节开头
    if not dag[0]:
        return [[s]]

    # DFS 枚举所有从 0 到 n 的路径
    results = []
    path = []

    def dfs(node):
        if node == n:
            results.append(list(path))
            return
        for next_node in dag[node]:
            path.append(s[node:next_node])
            dfs(next_node)
            path.pop()

    dfs(0)

    # 无任何完整路径（如 "qix"），原样返回
    if not results:
        return [[s]]

    return results


def best_split(s):
    """返回最优切分（音节数最少，即偏好长音节）

    符合 ABC 输入法习惯：nihao -> ['ni','hao'] 而非 ['n','i','h','a','o']

    多个切分音节数相同时，返回字典序最小的（保证确定性输出）。
    """
    all_splits = split_pinyin(s)
    if len(all_splits) == 1:
        return all_splits[0]
    # 按音节数升序，再按字典序
    all_splits.sort(key=lambda x: (len(x), x))
    return all_splits[0]


def mixed_split(s):
    """混合切分：贪婪匹配最长合法音节，剩余部分作为单字母

    用于支持"全拼+首字母"混合输入，如：
    - 'changy'   → ['chang', 'y']    (chang 是合法音节，y 是单字母)
    - 'cyong'    → ['c', 'yong']     (c 不是合法音节开头，yong 是)
    - 'changyong' → ['chang', 'yong'] (全拼切分，无单字母)
    - 'nh'       → ['n', 'h']        (都不是合法音节，全单字母)

    与 best_split 的区别：
    - best_split 只接受完整合法切分，否则走 echo
    - mixed_split 总能返回结果，单字母部分由调用方做首字母匹配

    Args:
        s: 拼音串（仅小写字母）

    Returns:
        切分列表，如 ['chang', 'y']。含非 a-z 字符时返回 [s]。
    """
    if not s:
        return []
    if not all('a' <= c <= 'z' for c in s):
        return [s]

    result = []
    i = 0
    n = len(s)
    while i < n:
        # 贪婪：从最长到最短尝试合法音节（至少 2 字符，单字母不作为音节）
        matched = False
        max_len = min(MAX_SYLLABLE_LEN, n - i)
        for length in range(max_len, 1, -1):  # length: 6,5,4,3,2
            substr = s[i:i + length]
            if substr in VALID_SYLLABLES:
                result.append(substr)
                i += length
                matched = True
                break
        if not matched:
            # 单字母（length=1）
            result.append(s[i])
            i += 1
    return result
