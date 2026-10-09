# Strategy Validation Sweep

Randomized-input validation of Model 1 (MILP) and Model 2 (Goal Programming) across 109 real F1 races. Each race was run once per model against a randomized-but-feasible set of user constraints — pit-stop minimums grounded in that race's real driver data, tyre-set limits, per-compound risk ceilings, and randomized goal-priority weights (seed 42) — and compared against the fastest finisher's actual race.

## Headline numbers

| Metric | Value |
|---|---|
| Model 1 solved | 109 / 109 (100%) — 108 proven optimal, 1 best-found within the time limit |
| Model 2 solved | 109 / 109 (100%) — 74 proven optimal, 35 best-found within the time limit |
| Model 1 avg solve time | 11.7s (range 0.4s – 21.6s) |
| Model 2 avg solve time | ~40s (35 of 109 hit the 20s cap on the final solve — best-found, not proven optimal) |

## All 109 races

Columns: real winner's actual time/driver vs. Model 1 (fastest-time) vs. Model 2 (balanced: time/stops/degradation-risk). Δ = seconds slower (+) or faster (−) than the real race time. "Min pit" is the randomized minimum-pit-stops constraint used for that race's run.

| Year | Race | Laps | Real driver | Real (s) | M1 (s) | M1 Δ | M2 (s) | M2 Δ | M2 Risk | M2 status | Min pit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2019 | Belgian Grand Prix | 44 | NOR | 4,980.8 | 5,096.7 | +116.0 | 5,110.7 | +129.9 | 24 | Optimal | 2 |
| 2019 | Azerbaijan Grand Prix | 51 | BOT | 5,512.9 | 5,649.2 | +136.3 | 5,671.4 | +158.5 | 39 | Optimal | 1 |
| 2019 | Bahrain Grand Prix | 57 | HAM | 5,661.3 | 5,757.5 | +96.2 | 6,038.8 | +377.5 | 55 | Optimal | 1 |
| 2019 | Canadian Grand Prix | 70 | VET | 5,345.7 | 5,487.4 | +141.7 | 5,493.2 | +147.4 | 50 | Optimal | 1 |
| 2019 | Australian Grand Prix | 58 | BOT | 5,127.3 | 5,256.2 | +128.9 | 5,290.8 | +163.5 | 16 | Optimal | 3 |
| 2019 | Abu Dhabi Grand Prix | 55 | HAM | 5,645.7 | 5,817.4 | +171.7 | 5,790.5 | +144.8 | 127 | Best found (time limit reached) | 2 |
| 2019 | Austrian Grand Prix | 71 | VER | 4,921.8 | 5,033.9 | +112.1 | 5,050.6 | +128.8 | 44 | Optimal | 2 |
| 2019 | French Grand Prix | 53 | HAM | 5,071.2 | 5,211.9 | +140.7 | 5,214.5 | +143.3 | 43 | Optimal | 1 |
| 2019 | Hungarian Grand Prix | 70 | HAM | 5,703.8 | 5,859.8 | +156.0 | 5,860.0 | +156.2 | 56 | Optimal | 1 |
| 2019 | Brazilian Grand Prix | 71 | VER | 5,594.7 | 5,615.6 | +20.9 | 5,677.4 | +82.7 | 169 | Best found (time limit reached) | 4 |
| 2019 | British Grand Prix | 52 | HAM | 4,868.4 | 4,997.6 | +129.2 | 5,032.8 | +164.3 | 21 | Optimal | 3 |
| 2019 | Russian Grand Prix | 53 | HAM | 5,619.0 | 5,701.2 | +82.2 | 5,714.4 | +95.4 | 51 | Optimal | 1 |
| 2019 | Mexican Grand Prix | 71 | HAM | 5,808.9 | 5,920.2 | +111.3 | 6,053.7 | +244.8 | 62 | Optimal | 1 |
| 2019 | Italian Grand Prix | 53 | LEC | 4,526.7 | 4,689.7 | +163.0 | 4,698.1 | +171.4 | 22 | Optimal | 3 |
| 2019 | Monaco Grand Prix | 78 | HAM | 6,208.4 | 6,276.3 | +67.8 | 6,276.3 | +67.8 | 40 | Optimal | 2 |
| 2019 | Japanese Grand Prix | 52 | BOT | 4,906.8 | 5,058.5 | +151.8 | 5,097.3 | +190.5 | 28 | Optimal | 2 |
| 2019 | United States Grand Prix | 56 | BOT | 5,635.6 | 5,772.7 | +137.0 | 5,772.7 | +137.0 | 56 | Optimal | 1 |
| 2019 | Chinese Grand Prix | 56 | HAM | 5,526.4 | 5,710.0 | +183.7 | 5,720.3 | +194.0 | 130 | Best found (time limit reached) | 2 |
| 2019 | Singapore Grand Prix | 61 | VET | 7,113.7 | 7,095.0 | -18.7 | 7,244.4 | +130.8 | 43 | Optimal | 2 |
| 2019 | Spanish Grand Prix | 66 | HAM | 5,750.4 | 5,774.5 | +24.1 | 5,788.3 | +37.9 | 57 | Optimal | 2 |
| 2020 | Belgian Grand Prix | 44 | HAM | 5,048.8 | 5,084.2 | +35.5 | 5,098.7 | +49.9 | 32 | Optimal | 1 |
| 2020 | Abu Dhabi Grand Prix | 55 | VER | 5,788.6 | 5,923.1 | +134.5 | 5,962.9 | +174.2 | 13 | Optimal | 3 |
| 2020 | British Grand Prix | 52 | HAM | 5,281.3 | 5,347.8 | +66.5 | 5,447.8 | +166.5 | 38 | Optimal | 1 |
| 2020 | 70th Anniversary Grand Prix | 52 | VER | 4,782.0 | 4,908.1 | +126.1 | 4,859.6 | +77.6 | 130 | Best found (time limit reached) | 3 |
| 2020 | Austrian Grand Prix | 68 | HAM | 5,183.3 | 5,213.0 | +29.6 | 5,150.4 | -33.0 | 170 | Best found (time limit reached) | 3 |
| 2020 | Emilia Romagna Grand Prix | 63 | HAM | 5,312.4 | 5,311.0 | -1.4 | 5,477.8 | +165.4 | 61 | Optimal | 1 |
| 2020 | Italian Grand Prix | 53 | SAI | 4,741.1 | 5,648.0 | +906.9 | 6,314.1 | +1,573.0 | 51 | Optimal | 1 |
| 2020 | Portuguese Grand Prix | 66 | HAM | 5,396.8 | 5,527.8 | +131.0 | 5,527.9 | +131.1 | 61 | Optimal | 1 |
| 2020 | Bahrain Grand Prix | 57 | HAM | 5,837.2 | 6,995.9 | +1,158.7 | 9,941.8 | +4,104.6 | 133 | Best found (time limit reached) | 2 |
| 2020 | Russian Grand Prix | 53 | BOT | 5,640.4 | 5,622.8 | -17.5 | 6,000.5 | +360.1 | 45 | Optimal | 1 |
| 2020 | Eifel Grand Prix | 60 | HAM | 5,749.6 | 5,784.4 | +34.8 | 5,829.2 | +79.6 | 140 | Best found (time limit reached) | 2 |
| 2021 | Abu Dhabi Grand Prix | 58 | VER | 5,417.4 | 5,547.4 | +130.1 | 5,638.4 | +221.1 | 58 | Optimal | 1 |
| 2021 | Austrian Grand Prix | 71 | VER | 5,034.5 | 5,151.0 | +116.5 | 5,448.5 | +413.9 | 71 | Optimal | 1 |
| 2020 | Styrian Grand Prix | 71 | HAM | 4,970.7 | 5,046.5 | +75.8 | 5,137.1 | +166.4 | 159 | Best found (time limit reached) | 2 |
| 2020 | Spanish Grand Prix | 66 | HAM | 5,505.3 | 5,674.8 | +169.6 | 5,675.4 | +170.2 | 51 | Optimal | 2 |
| 2020 | Sakhir Grand Prix | 87 | PER | 5,475.1 | 5,540.7 | +65.6 | 5,548.4 | +73.3 | 40 | Optimal | 4 |
| 2020 | Tuscan Grand Prix | 59 | BOT | 5,284.4 | 6,892.9 | +1,608.5 | 9,015.2 | +3,730.8 | 151 | Best found (time limit reached) | 5 |
| 2021 | Azerbaijan Grand Prix | 51 | LAT | 5,818.1 | 6,274.1 | +456.0 | 6,474.4 | +656.3 | 18 | Optimal | 2 |
| 2021 | French Grand Prix | 53 | VER | 5,245.8 | 5,301.7 | +56.0 | 5,308.8 | +63.0 | 41 | Optimal | 1 |
| 2021 | Italian Grand Prix | 53 | RIC | 4,914.4 | 4,946.3 | +31.9 | 6,507.7 | +1,593.4 | 51 | Optimal | 1 |
| 2021 | Monaco Grand Prix | 78 | VER | 5,936.8 | 6,040.7 | +103.9 | 6,055.3 | +118.5 | 67 | Optimal | 1 |
| 2021 | Dutch Grand Prix | 72 | VER | 5,405.4 | 5,603.8 | +198.4 | 5,570.4 | +165.1 | 170 | Best found (time limit reached) | 3 |
| 2021 | British Grand Prix | 52 | RUS | 4,862.6 | 5,081.4 | +218.8 | 5,125.3 | +262.8 | 29 | Optimal | 2 |
| 2021 | Bahrain Grand Prix | 56 | HAM | 5,523.9 | 5,572.3 | +48.4 | 5,761.1 | +237.2 | 34 | Optimal | 3 |
| 2021 | Mexico City Grand Prix | 71 | VER | 5,919.1 | 6,085.9 | +166.8 | 6,691.4 | +772.3 | 164 | Best found (time limit reached) | 2 |
| 2021 | Portuguese Grand Prix | 66 | HAM | 5,671.4 | 5,583.9 | -87.5 | 5,640.9 | -30.5 | 42 | Optimal | 3 |
| 2021 | Spanish Grand Prix | 66 | HAM | 5,587.7 | 5,697.2 | +109.5 | 5,704.1 | +116.4 | 51 | Optimal | 2 |
| 2021 | Qatar Grand Prix | 57 | HAM | 5,068.5 | 5,329.2 | +260.7 | 5,361.6 | +293.2 | 21 | Optimal | 3 |
| 2021 | Styrian Grand Prix | 71 | VER | 4,938.9 | 5,098.7 | +159.8 | 5,098.7 | +159.8 | 49 | Optimal | 2 |
| 2021 | Saudi Arabian Grand Prix | 50 | HAM | 5,082.6 | 5,949.8 | +867.2 | 5,587.2 | +504.6 | 116 | Best found (time limit reached) | 2 |
| 2022 | Azerbaijan Grand Prix | 51 | VER | 5,645.9 | 5,722.2 | +76.2 | 5,740.5 | +94.5 | 51 | Optimal | 1 |
| 2022 | Australian Grand Prix | 58 | LEC | 5,266.6 | 5,198.3 | -68.2 | 5,392.0 | +125.5 | 52 | Optimal | 1 |
| 2021 | São Paulo Grand Prix | 71 | HAM | 5,542.9 | 5,909.4 | +366.6 | 5,909.4 | +366.6 | 189 | Best found (time limit reached) | 5 |
| 2022 | Canadian Grand Prix | 70 | VER | 5,781.8 | 5,841.9 | +60.2 | 5,855.0 | +73.2 | 47 | Optimal | 2 |
| 2022 | Abu Dhabi Grand Prix | 58 | VER | 5,265.9 | 5,381.6 | +115.7 | 5,372.2 | +106.3 | 134 | Best found (time limit reached) | 2 |
| 2022 | French Grand Prix | 53 | VER | 5,402.1 | 5,601.6 | +199.4 | 5,620.1 | +218.0 | 38 | Optimal | 2 |
| 2021 | United States Grand Prix | 56 | VER | 5,676.6 | 5,890.1 | +213.6 | 5,839.1 | +162.5 | 130 | Best found (time limit reached) | 2 |
| 2022 | British Grand Prix | 52 | ALO | 5,075.7 | 5,384.5 | +308.8 | 9,021.0 | +3,945.3 | 120 | Best found (time limit reached) | 2 |
| 2022 | Belgian Grand Prix | 44 | VER | 5,152.9 | 5,209.3 | +56.4 | 5,255.5 | +102.6 | 110 | Best found (time limit reached) | 3 |
| 2022 | Bahrain Grand Prix | 57 | PER | 5,765.5 | 5,886.5 | +121.0 | 5,939.6 | +174.1 | 140 | Best found (time limit reached) | 3 |
| 2022 | Miami Grand Prix | 57 | MAG | 5,608.9 | 5,706.0 | +97.2 | 6,008.1 | +399.2 | 49 | Optimal | 1 |
| 2022 | Mexico City Grand Prix | 71 | VER | 5,916.7 | 6,044.2 | +127.5 | 6,053.1 | +136.3 | 68 | Optimal | 1 |
| 2022 | Italian Grand Prix | 53 | VER | 4,827.5 | 4,807.1 | -20.4 | 4,944.2 | +116.7 | 22 | Optimal | 3 |
| 2022 | Saudi Arabian Grand Prix | 50 | VER | 5,059.3 | 5,052.5 | -6.8 | 5,187.6 | +128.4 | 17 | Optimal | 2 |
| 2022 | Dutch Grand Prix | 72 | VER | 5,802.8 | 5,844.5 | +41.8 | 5,918.0 | +115.3 | 180 | Best found (time limit reached) | 3 |
| 2022 | Hungarian Grand Prix | 70 | VER | 5,975.9 | 6,085.6 | +109.7 | 6,094.0 | +118.0 | 49 | Optimal | 2 |
| 2023 | Abu Dhabi Grand Prix | 58 | SAI | 5,210.9 | 5,310.3 | +99.4 | 5,892.7 | +681.8 | 58 | Optimal | 1 |
| 2023 | Azerbaijan Grand Prix | 51 | PER | 5,562.4 | 5,686.4 | +124.0 | 6,043.3 | +480.8 | 51 | Optimal | 1 |
| 2023 | Australian Grand Prix | 58 | HAM | 4,968.5 | 6,479.7 | +1,511.2 | 19,011.6 | +14,043.1 | 34 | Optimal | 2 |
| 2022 | Spanish Grand Prix | 66 | VER | 5,840.5 | 5,989.7 | +149.2 | 5,942.6 | +102.1 | 154 | Best found (time limit reached) | 2 |
| 2022 | São Paulo Grand Prix | 71 | RUS | 5,914.0 | 6,033.8 | +119.8 | 6,010.8 | +96.8 | 167 | Best found (time limit reached) | 3 |
| 2022 | United States Grand Prix | 56 | VER | 6,131.7 | 6,186.2 | +54.5 | 6,238.5 | +106.8 | 130 | Best found (time limit reached) | 2 |
| 2023 | Austrian Grand Prix | 71 | VER | 5,133.6 | 5,258.6 | +124.9 | 5,496.9 | +363.3 | 183 | Best found (time limit reached) | 4 |
| 2023 | Italian Grand Prix | 51 | VER | 4,421.1 | 4,524.9 | +103.7 | 4,525.0 | +103.9 | 22 | Optimal | 2 |
| 2023 | British Grand Prix | 52 | VER | 5,116.9 | 5,034.6 | -82.3 | 5,077.8 | -39.1 | 24 | Optimal | 2 |
| 2023 | Japanese Grand Prix | 53 | VER | 5,458.4 | 5,385.4 | -73.0 | 6,698.8 | +1,240.3 | 51 | Optimal | 1 |
| 2023 | Las Vegas Grand Prix | 50 | VER | 5,348.3 | 5,333.6 | -14.7 | 5,488.1 | +139.8 | 50 | Optimal | 1 |
| 2023 | Bahrain Grand Prix | 57 | VER | 5,636.7 | 5,806.2 | +169.5 | 5,728.6 | +91.9 | 141 | Best found (time limit reached) | 3 |
| 2023 | Miami Grand Prix | 57 | VER | 5,258.2 | 5,341.4 | +83.2 | 5,483.3 | +225.1 | 55 | Optimal | 1 |
| 2023 | Belgian Grand Prix | 44 | VER | 4,950.4 | 5,062.8 | +112.4 | 5,062.8 | +112.4 | 42 | Optimal | 2 |
| 2023 | Saudi Arabian Grand Prix | 50 | PER | 4,874.9 | 4,893.0 | +18.1 | 4,893.0 | +18.1 | 50 | Optimal | 1 |
| 2023 | Hungarian Grand Prix | 70 | VER | 5,888.6 | 6,025.6 | +137.0 | 6,019.6 | +130.9 | 54 | Optimal | 2 |
| 2023 | Singapore Grand Prix | 62 | RUS | 6,298.9 | 6,384.5 | +85.6 | 6,384.5 | +85.6 | 62 | Optimal | 1 |
| 2024 | Abu Dhabi Grand Prix | 58 | NOR | 5,193.3 | 5,293.3 | +100.0 | 5,356.6 | +163.3 | 58 | Optimal | 1 |
| 2023 | Mexico City Grand Prix | 71 | SAR | 6,002.7 | 6,969.9 | +967.1 | 7,013.4 | +1,010.7 | 66 | Optimal | 3 |
| 2023 | Qatar Grand Prix | 57 | VER | 5,259.2 | 5,305.5 | +46.4 | 6,341.1 | +1,081.9 | 141 | Best found (time limit reached) | 3 |
| 2023 | Spanish Grand Prix | 66 | VER | 5,277.9 | 5,387.8 | +109.8 | 5,378.5 | +100.5 | 154 | Best found (time limit reached) | 2 |
| 2024 | Bahrain Grand Prix | 57 | VER | 5,504.7 | 5,643.0 | +138.3 | 5,644.1 | +139.3 | 49 | Optimal | 2 |
| 2024 | Azerbaijan Grand Prix | 51 | PIA | 5,578.0 | 5,722.5 | +144.4 | 5,755.0 | +177.0 | 35 | Optimal | 1 |
| 2023 | São Paulo Grand Prix | 71 | RIC | 5,399.7 | 6,339.4 | +939.7 | 7,929.9 | +2,530.1 | 177 | Best found (time limit reached) | 3 |
| 2023 | United States Grand Prix | 56 | VER | 5,721.4 | 5,829.3 | +108.0 | 5,912.7 | +191.3 | 139 | Best found (time limit reached) | 3 |
| 2024 | Belgian Grand Prix | 44 | RUS | 4,797.0 | 4,868.4 | +71.3 | 4,878.8 | +81.8 | 35 | Optimal | 2 |
| 2024 | Australian Grand Prix | 58 | SAI | 4,826.8 | 5,095.4 | +268.6 | 5,157.2 | +330.4 | 144 | Best found (time limit reached) | 3 |
| 2024 | Austrian Grand Prix | 71 | RUS | 5,062.8 | 5,191.6 | +128.8 | 5,362.8 | +300.0 | 183 | Best found (time limit reached) | 4 |
| 2024 | Hungarian Grand Prix | 70 | PIA | 5,882.0 | 5,973.6 | +91.6 | 6,019.8 | +137.8 | 70 | Optimal | 1 |
| 2024 | Italian Grand Prix | 53 | LEC | 4,480.7 | 4,579.6 | +98.9 | 4,866.8 | +386.0 | 51 | Optimal | 1 |
| 2024 | Emilia Romagna Grand Prix | 63 | VER | 5,125.2 | 5,269.0 | +143.7 | 5,269.7 | +144.4 | 29 | Optimal | 2 |
| 2024 | Dutch Grand Prix | 72 | NOR | 5,445.5 | 5,548.2 | +102.7 | 5,557.7 | +112.2 | 35 | Optimal | 2 |
| 2024 | Chinese Grand Prix | 56 | VER | 6,052.6 | 6,081.6 | +29.1 | 6,202.5 | +150.0 | 43 | Optimal | 2 |
| 2024 | Las Vegas Grand Prix | 50 | RUS | 4,926.0 | 5,015.5 | +89.5 | 5,126.9 | +200.9 | 50 | Optimal | 1 |
| 2024 | Miami Grand Prix | 57 | NOR | 5,449.9 | 5,498.1 | +48.2 | 5,501.5 | +51.6 | 55 | Optimal | 1 |
| 2024 | Japanese Grand Prix | 53 | VER | 5,152.4 | 6,503.3 | +1,350.9 | 6,503.3 | +1,350.9 | 48 | Optimal | 2 |
| 2024 | Mexico City Grand Prix | 71 | SAI | 6,055.8 | 6,086.6 | +30.8 | 6,261.7 | +205.9 | 177 | Best found (time limit reached) | 3 |
| 2024 | Saudi Arabian Grand Prix | 50 | VER | 4,843.3 | 4,888.2 | +44.9 | 4,913.4 | +70.1 | 11 | Optimal | 2 |
| 2024 | Singapore Grand Prix | 62 | NOR | 6,052.6 | 6,207.6 | +155.0 | 6,185.8 | +133.2 | 144 | Best found (time limit reached) | 2 |
| 2024 | Qatar Grand Prix | 57 | VER | 5,465.3 | 5,568.0 | +102.7 | 5,520.4 | +55.1 | 147 | Best found (time limit reached) | 4 |
| 2024 | Monaco Grand Prix | 78 | HAM | 6,126.7 | 6,722.4 | +595.8 | 6,127.4 | +0.7 | 194 | Best found (time limit reached) | 3 |
| 2024 | Spanish Grand Prix | 66 | VER | 5,300.2 | 5,436.6 | +136.4 | 5,387.0 | +86.8 | 162 | Best found (time limit reached) | 3 |
| 2024 | United States Grand Prix | 56 | LEC | 5,709.6 | 5,758.0 | +48.4 | 5,773.1 | +63.5 | 30 | Optimal | 2 |

Source: `scripts/validate_models_random.py` → `scripts/validation_random_results.csv`. One random-but-feasible input set (min pit stops, tyre-set limits, per-compound risk ceiling, goal-priority weights) shared by both models per race, generated directly from the backend's own constraint-resolution logic and verified against the real solver before use (seed 42). Full sweep: 109/109 races produced a result for both models, 0 errors, 0 skipped, ~21 minutes wall-clock with 6 parallel workers.
