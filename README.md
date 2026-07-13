# 高分片週報

每週五 09:00（台北）自動撈取近 60 天的新片，篩出爛番茄 ≥ 85% 且 IMDb ≥ 7.5
的電影與影集，發布到 GitHub Pages。

- 最新報告：https://jsdryan.github.io/highscore-weekly/
- 資料來源：TMDB（候選與繁中詮釋資料）、OMDb（IMDb ＋爛番茄分數）
- 影集缺爛番茄分數時（OMDb 覆蓋限制），以 IMDb 單邊門檻入選並標「RT 無資料」

本地執行：`TMDB_API_KEY=... OMDB_API_KEY=... python3 -m highscore.main`
