# 高分片週報 — 設計文件

日期：2026-07-13
狀態：已與用戶確認

## 目的

用戶想定期發現 Rotten Tomatoes 與 IMDb 上的高分新片（電影＋影集），但兩個網站的 UI（尤其爛番茄）讓人工搜尋費時。本工具每週自動產出一份雙高分新片網頁報告，用戶打開固定網址即可挑片。

## 需求（已確認）

- **內容範圍**：新上映電影、新開播影集、新一季開播的返場影集為主
- **交付方式**：排程自動執行，產出網頁報告（GitHub Pages，手機可開）
- **高分門檻**：嚴格雙高分 — 爛番茄 ≥ 85% 且 IMDb ≥ 7.5，附投票數門檻
- **頻率**：每週一次，週五 09:00 台北時間
- **串流平台標註**：不需要
- **報告語言**：繁體中文（台灣），片名附原文

## 架構

- GitHub public repo（免費帳號 Pages 限公開 repo；內容僅為分數清單，可公開）
- GitHub Actions 排程 workflow：cron `0 1 * * 5`（UTC）＝台北週五 09:00，另設 `workflow_dispatch` 手動觸發
- 一支 Python 腳本負責：撈候選 → 查分數 → 篩選 → 產出 HTML → commit 回 repo
- GitHub Pages 從 main branch 發布

### 產出物

| 檔案 | 用途 |
|---|---|
| `index.html` | 最新一期報告（固定網址） |
| `reports/YYYY-MM-DD.html` | 每期存檔，index 底部附歷期連結 |
| `state.json` | 歷次已入選片單（TMDB id → 首次入選日期），用於標記 🆕 |

## 資料流程

1. **TMDB Discover API**（免費）撈候選，60 天滾動窗口：
   - 電影：`primary_release_date` 在過去 60 天內，依熱門度排序，上限 150 部
   - 影集：`first_air_date` 在過去 60 天內（新劇）；以及窗口內有新一季開播的返場劇（以最新一季的 `air_date` 判定），標示季數；新劇＋返場合計上限 150 部
   - 候選合計上限 300 部/週（OMDb 免費額度 1,000 次/天，餘裕充足）
   - 以 `language=zh-TW` 取得繁中片名、簡介、海報
2. 每個候選經 TMDB `external_ids` 取得 IMDb ID；無 IMDb ID 者略過
3. 以 IMDb ID 查 **OMDb API** → IMDb 分數、IMDb 投票數、爛番茄分數
4. **篩選**：
   - 電影：RT ≥ 85% 且 IMDb ≥ 7.5 且投票數 ≥ 500
   - 影集：IMDb ≥ 7.5 且投票數 ≥ 500；RT 有資料時同樣要求 ≥ 85%，無資料則入選並標「RT 無資料」
5. 產出 HTML：電影／影集分區，卡片含海報、繁中＋原文片名、雙分數、類型、上映／開播日、簡介、IMDb 與 RT 連結；比對 `state.json`，本週新入選標 🆕

60 天滾動窗口的用意：新片分數需時間累積，慢熱片跨過門檻後仍會被撈到並以 🆕 標出，不漏片。

## 已知限制（已向用戶說明）

- Rotten Tomatoes 無公開 API。OMDb 的 RT 分數對電影覆蓋完整，對影集常缺 → 影集採 IMDb 單邊門檻 fallback 並標註
- 影集分數為整劇層級（OMDb 限制），非單季分數；報告標示第幾季開播供參考
- OMDb 免費額度 1,000 次/天；候選上限 300 部/週，餘裕充足

## 錯誤處理

- API 呼叫失敗：指數退避重試（3 次）；單部片失敗跳過，報告底部列「本次查詢失敗清單」
- 整體流程失敗：workflow 標紅，GitHub 自動寄失敗通知 email 給用戶
- OMDb 回應中 `N/A`／缺欄位視為無資料，不得當 0 分處理

## 測試與驗證

- 單元測試（pytest、固定 fixture）：篩選邏輯（雙門檻、影集 RT 缺資料 fallback、投票數門檻）、OMDb 回應解析（含 `N/A`）
- 端對端：本機以真實 key 跑完整流程，開瀏覽器實看報告
- 雲端：`workflow_dispatch` 手動觸發一次，確認 Actions 跑通、Pages 網址上線

## 一次性準備（用戶）

1. 註冊 TMDB API key（免費）
2. 註冊 OMDb API key（免費）
3. 兩個 key 存入 repo Actions secrets：`TMDB_API_KEY`、`OMDB_API_KEY`

用戶已授權：由 Claude 直接以 gh CLI 建立 repo、push、設定 secrets（key 由用戶提供）。
