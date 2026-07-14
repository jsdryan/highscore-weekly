# 高分片週報

每週五 09:00（台北）自動撈取近 60 天的新片，篩出爛番茄 ≥ 85% 且 IMDb ≥ 7.5
的電影與影集，發布到 GitHub Pages。

- 最新報告：https://jsdryan.github.io/highscore-weekly/
- 資料來源：TMDB（候選與中文詮釋資料）、OMDb（IMDb ＋爛番茄分數）
- 影集缺爛番茄分數時（OMDb 覆蓋限制），以 IMDb 單邊門檻入選並標「RT 無資料」
- TMDB 的 zh-TW 資料摻雜簡體（類型清單整份是簡體），片名、簡介、類型一律經
  OpenCC `s2twp` 轉成臺灣正體中文；原文片名保留原樣

本地執行：`TMDB_API_KEY=... OMDB_API_KEY=... python3 -m highscore.main`
