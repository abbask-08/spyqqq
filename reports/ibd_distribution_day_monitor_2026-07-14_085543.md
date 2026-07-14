# IBD Distribution Day Monitor Report

- **As of:** 2026-07-14
- **Overall Risk Level:** **SEVERE**
- **Primary Signal Symbol:** SPY
- **Generated At:** 2026-07-14T13:55:43+00:00

## Index Results

### SPY — risk: **SEVERE**

- Today is Distribution Day: False
- d5 / d15 / d25 = 2 / 4 / 8
- Cluster: 5/15/25セッション経過以内: 2/4/8
- Trend filters: close_above_21ema=True, close_above_50sma=True, market_below_21ema_or_50ma=False

> SPYは本日Distribution Day非該当。 5/15/25セッション経過以内の有効Distribution Dayはそれぞれ 2/4/8 件。 リスク判定: SEVERE。

#### Active Distribution Days

| date | close | pct_change | volume_change_pct | age | expires_in | high_since | invalidation_price |
|------|-------|------------|-------------------|-----|------------|------------|---------------------|
| 2026-07-13 | 749.17 | -0.77% | 4.32% | 1 | 24 | 753.91 | 786.6285 |
| 2026-07-08 | 745.4 | -0.31% | 0.10% | 4 | 21 | 755.42 | 782.67 |
| 2026-06-26 | 728.99 | -0.72% | 31.23% | 11 | 14 | 755.42 | 765.4395000000001 |
| 2026-06-23 | 733.58 | -1.45% | 43.36% | 14 | 11 | 755.42 | 770.2590000000001 |
| 2026-06-17 | 740.96 | -1.25% | 28.10% | 17 | 8 | 755.42 | 778.008 |
| 2026-06-16 | 750.33 | -0.60% | 11.49% | 18 | 7 | 755.44 | 787.8465000000001 |
| 2026-06-09 | 737.05 | -0.29% | 77.79% | 23 | 2 | 756.68 | 773.9025 |
| 2026-06-05 | 737.55 | -2.58% | 88.27% | 25 | 0 | 756.68 | 774.4275 |

## Portfolio Action

- **Instrument:** QQQ
- **Recommended Action:** REDUCE_EXPOSURE_OR_HEDGE
- **Exposure:** current 100% → target 50% (delta -50%)
- **Trailing Stop:** 5%

> QQQ tracks Nasdaq-100 1x. Exposure cuts are smaller than TQQQ but still respond to clustered distribution.

## Audit

- **Data Source:** fmp
- **Symbols:** SPY
- **Audit Flags:** ['no_data_returned']
- **Rule Version:** ibd_dd_v1.0

