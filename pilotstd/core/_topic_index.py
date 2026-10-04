"""主题索引数据（聚合器专用）——**领域数据字典，非文案、勿 i18n**。

数据本体在 `topic_index_data.json`（数据与展示分离：Python 侧只做加载，不承载文案字面量）。

为什么不是文案：本表把「通知标题的渲染值」映射到**主题串**（`scan`/`download`/…），
用于聚合分组与托盘节流的「同主题」判定。它是**数据字典**，不是给用户看的文案：

- 表内的中文是 i18n 包中**真实标题**的取值（作为匹配契约），不是界面文案；
- 把它改成 i18n 键会让匹配退化为「先判语言再查表」，且三语需各维护一份关键词表
  （属数据结构变更，收益为负）；
- 因此本表按**数据字典**口径维护，不进 G-047 基线、也不做逐行豁免。

英文标题为何还有关键词兜底：i18n 契约表覆盖 `notification.*` 的真实标题；
`_LEGACY_TOPIC_KEYWORDS` 只作**跨语言兜底**（英文标题里出现 `backup`/`announce` 等词时
仍能归组），不承担主要判定。
"""

import json
from pathlib import Path

_DATA_PATH = Path(__file__).with_name("topic_index_data.json")


def _load() -> tuple[dict[str, str], tuple[tuple[str, tuple[str, ...]], ...]]:
    """读取数据文件；缺失即抛错（避免静默退化为空表导致主题分组全落兜底）。"""
    payload = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    by_event: dict[str, str] = {
        str(k): str(v) for k, v in payload["topic_by_event"].items()
    }
    legacy: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
        (str(topic), tuple(str(w) for w in words)) for topic, words in payload["legacy_topic_keywords"]
    )
    return by_event, legacy


_TOPIC_BY_EVENT, _LEGACY_TOPIC_KEYWORDS = _load()
