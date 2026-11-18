"""替代关系方向判定：防止“代替旧号”被当成新标准。"""

from __future__ import annotations


def is_backward_replacement(old_number: str, new_number: str) -> bool:
    """new_number 年份早于 old_number 时返回 True（不是真正的新标准）。"""
    from .std_utils import parse_std_number

    old_year = int((parse_std_number(old_number) or {}).get("year") or 0)
    new_year = int((parse_std_number(new_number) or {}).get("year") or 0)
    return bool(old_year and new_year and new_year < old_year)


def replacement_info(db, standard_number: str) -> dict[str, str]:
    """查替代标准；年份倒退（代替旧号误写）返回空。"""
    try:
        row = db.fetchone(
            "SELECT superseded_by FROM announcement_record "
            "WHERE standard_number=? AND COALESCE(superseded_by,'')<>'' LIMIT 1",
            (standard_number,),
        )
        if not row:
            return {}
        new_standard = str(row["superseded_by"] or "")
        if is_backward_replacement(standard_number, new_standard):
            return {}
        name_row = db.fetchone(
            "SELECT std_name, implement_date FROM announcement_record WHERE standard_number=? LIMIT 1",
            (new_standard,),
        )
        return {
            "new_standard": new_standard,
            "new_standard_name": str(name_row["std_name"] or "") if name_row else "",
            "new_standard_implementation_date": (
                str(name_row["implement_date"] or "")
                if name_row and "implement_date" in name_row.keys()
                else ""
            ),
        }
    except Exception as exc:  # noqa: BLE001 - 数据缺失时保持空替代，须留痕
        import logging

        logging.getLogger(__name__).warning("replacement lookup failed: %s", exc)
        return {}
