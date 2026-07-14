"""轉成臺灣正體中文。

TMDB 的 zh-TW 資料摻雜簡體——類型清單整份是簡體（动作、纪录、惊悚），
部分片名與簡介也是——所以入庫前一律轉換。s2twp 連台灣慣用語也一併處理
（网络→網路）。非中文（英、日、韓）不受影響。
"""
import opencc

_converter = None


def to_tw(text):
    if not text:
        return text
    global _converter
    if _converter is None:
        _converter = opencc.OpenCC("s2twp")
    return _converter.convert(text)
