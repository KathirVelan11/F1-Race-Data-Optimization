import { useEffect, useMemo, useState } from 'react'
import './App.css'

type DashboardStats = {
  years: number[]
  years_range: string
  total_races: number
  total_drivers: number
  total_rows: number
  source: string
}

type DatasetOverview = {
  total_rows: number
  total_races: number
  total_drivers: number
  total_teams: number
  years_range: string
  races_per_year: Record<string, number>
  compound_distribution: Record<string, number>
  pit_stop_stats: {
    count: number
    mean_duration_seconds: number
    min_duration_seconds: number
    max_duration_seconds: number
  }
  mean_max_stint_life_by_compound: Record<string, number>
}

type StrategyStage = {
  compound: string
  start_lap: number
  end_lap: number
  lap_count: number
}

type StrategyPreview = {
  year: number
  race_name: string
  driver_code?: string
  total_laps?: number
  fastest_compound?: string
  estimated_race_time_seconds?: number
  balanced_race_time_seconds?: number
  pit_stop_count?: number
  pit_laps?: number[]
  time_delta_vs_fastest_seconds?: number
  strategy: StrategyStage[]
  message?: string
  solver_status?: string
  objective_value_z?: number
  pit_loss_seconds?: number
  max_pit_stops?: number
  min_stint_length?: number
  max_pit_stops_valid_range?: [number, number]
  min_stint_length_valid_range?: [number, number]
  targets?: {
    target_race_time_seconds: number
    target_pit_stops: number
    target_degradation_index: number
  }
}

type ComparisonResult = {
  scope1: StrategyPreview
  scope2: StrategyPreview
  time_delta_seconds: number
  comparison_note: string
}

type GoalWeights = {
  weight_time_w1: number
  weight_pit_stops_w2: number
  weight_degradation_w3: number
}

const API_BASE = 'http://localhost:8000/api'
const DEFAULT_WEIGHTS: GoalWeights = {
  weight_time_w1: 0.5,
  weight_pit_stops_w2: 0.25,
  weight_degradation_w3: 0.25,
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardStats | null>(null)
  const [seasons, setSeasons] = useState<number[]>([])
  const [selectedYear, setSelectedYear] = useState<number>(2024)
  const [races, setRaces] = useState<string[]>([])
  const [selectedRace, setSelectedRace] = useState<string>('')
  const [drivers, setDrivers] = useState<string[]>([])
  const [selectedDriver, setSelectedDriver] = useState<string>('')
  const [raceSummary, setRaceSummary] = useState<any>(null)
  const [strategy, setStrategy] = useState<StrategyPreview | null>(null)
  const [comparison, setComparison] = useState<ComparisonResult | null>(null)
  const [weights, setWeights] = useState<GoalWeights>(DEFAULT_WEIGHTS)
  const [loading, setLoading] = useState(false)
  const [activeModelTab, setActiveModelTab] = useState<'model1' | 'model2'>('model1')
  const [overview, setOverview] = useState<DatasetOverview | null>(null)
  const [maxPitStopsInput, setMaxPitStopsInput] = useState<string>('')
  const [minStintLengthInput, setMinStintLengthInput] = useState<string>('')

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const response = await fetch(`${API_BASE}/dashboard`)
        const data = await response.json()
        setDashboard(data)
        setSeasons(data.years || [])
        setSelectedYear((data.years && data.years[0]) || 2024)
      } catch (error) {
        console.error('Dashboard load failed', error)
      }
    }

    loadDashboard()
  }, [])

  useEffect(() => {
    const loadOverview = async () => {
      try {
        const response = await fetch(`${API_BASE}/dataset/overview`)
        const data = await response.json()
        setOverview(data)
      } catch (error) {
        console.error('Dataset overview load failed', error)
      }
    }

    loadOverview()
  }, [])

  useEffect(() => {
    const loadRaces = async () => {
      if (!selectedYear) return
      try {
        const response = await fetch(`${API_BASE}/races?year=${selectedYear}`)
        const data = await response.json()
        setRaces(data.races || [])
        setSelectedRace((data.races && data.races[0]) || '')
      } catch (error) {
        console.error('Race load failed', error)
      }
    }

    loadRaces()
  }, [selectedYear])

  useEffect(() => {
    const loadRaceDrivers = async () => {
      if (!selectedYear || !selectedRace) return
      try {
        const response = await fetch(`${API_BASE}/races/${selectedYear}/${encodeURIComponent(selectedRace)}/drivers`)
        const data = await response.json()
        setDrivers(data.drivers || [])
        setSelectedDriver((data.drivers && data.drivers[0]) || '')
      } catch (error) {
        console.error('Driver load failed', error)
      }
    }

    loadRaceDrivers()
  }, [selectedYear, selectedRace])

  useEffect(() => {
    const loadSummary = async () => {
      if (!selectedYear || !selectedRace) return
      try {
        const query = selectedDriver ? `?driver_code=${encodeURIComponent(selectedDriver)}` : ''
        const response = await fetch(`${API_BASE}/races/${selectedYear}/${encodeURIComponent(selectedRace)}/summary${query}`)
        if (!response.ok) return
        const data = await response.json()
        setRaceSummary(data)
      } catch (error) {
        console.error('Race summary load failed', error)
      }
    }

    loadSummary()
  }, [selectedYear, selectedRace, selectedDriver])

  const renderStrategyCard = (title: string, payload: StrategyPreview | null, highlight: 'fastest' | 'balanced') => {
    if (!payload || payload.strategy.length === 0) {
      return (
        <article className="card info-panel">
          <div className="panel-header">
            <h3>{title}</h3>
          </div>
          <p className="empty-state">No {title.toLowerCase()} strategy available yet.</p>
        </article>
      )
    }

    const stages = payload.strategy.map((stage) => ({
      ...stage,
      label: `${stage.compound} ${stage.start_lap}-${stage.end_lap}`,
    }))

    const estimateLabel = highlight === 'fastest'
      ? 'Estimated race time'
      : 'Balanced race time'

    const lapCountTotal = stages.reduce((sum, stage) => sum + stage.lap_count, 0)
    const totalLaps = payload.total_laps ?? lapCountTotal
    const normalizedTotalLaps = Math.max(1, totalLaps || 1)
    const summaryText = highlight === 'fastest'
      ? `Fastest option uses ${stages.length} stint${stages.length === 1 ? '' : 's'} with ${payload.pit_laps?.length ?? 0} pit stop${(payload.pit_laps?.length ?? 0) === 1 ? '' : 's'}.`
      : `Balanced option prioritizes a controlled trade-off across ${stages.length} stint${stages.length === 1 ? '' : 's'} and ${payload.pit_stop_count ?? 0} stop${(payload.pit_stop_count ?? 0) === 1 ? '' : 's'}.`

    // pit_loss_seconds is always computed server-side from real race/circuit pit-stop
    // data (see BackendOptimizationRunner._get_pit_loss_seconds); if it's ever missing,
    // that's a real API contract bug worth surfacing, not a silent fake default.
    const pitLossKnown = typeof payload.pit_loss_seconds === 'number'
    const pitStops = stages.slice(0, -1).map((stage, index) => ({
      stopNumber: index + 1,
      lap: stage.end_lap,
      fromCompound: stage.compound,
      toCompound: stages[index + 1]?.compound ?? '—',
      costSeconds: pitLossKnown ? payload.pit_loss_seconds! : null,
    }))

    return (
      <article className="card info-panel">
        <div className="panel-header">
          <h3>{title}</h3>
        </div>
        <div className="strategy-block">
          <div className="strategy-topline">
            <span className={highlight === 'balanced' ? 'balanced-tag' : ''}>{payload.fastest_compound ?? payload.strategy[0]?.compound}</span>
            <strong>{normalizedTotalLaps} laps</strong>
          </div>

          <div className="timeline-wrap" aria-label={`${title} tyre timeline`}>
            {stages.map((stage) => (
              <div
                key={`${stage.compound}-${stage.start_lap}`}
                className="timeline-segment"
                data-compound={stage.compound}
                style={{ width: `${(stage.lap_count / normalizedTotalLaps) * 100}%` }}
                title={`${stage.compound}: laps ${stage.start_lap}-${stage.end_lap}`}
              >
                <span>{stage.compound}</span>
              </div>
            ))}
          </div>

          {stages.map((stage) => (
            <div key={`${stage.compound}-${stage.start_lap}`} className="stage-chip">
              <span className="dot" data-compound={stage.compound}></span>
              <div>
                <strong>{stage.compound}</strong>
                <small>Laps {stage.start_lap}-{stage.end_lap}</small>
              </div>
            </div>
          ))}
          <div className="estimate-box">
            <span>{estimateLabel}</span>
            <strong>{((highlight === 'fastest' ? payload.estimated_race_time_seconds : payload.balanced_race_time_seconds) ?? 0).toFixed(1)} s</strong>
          </div>
          <p className="strategy-summary">{summaryText}</p>

          {highlight === 'fastest' && (
            <p className="block-hint">
              Model 1 optimizes for pure race time only &mdash; see Model 2 for the full
              pit-stop and degradation breakdown.
            </p>
          )}

          {highlight === 'balanced' && payload.targets && (
            <div className="goal-targets">
              <h4>Goal programming targets</h4>
              <div className="summary-list">
                <div><span>Target race time (T*)</span><strong>{payload.targets.target_race_time_seconds.toFixed(1)}s</strong></div>
                <div><span>Target pit stops (P*)</span><strong>{payload.targets.target_pit_stops}</strong></div>
                <div><span>Target degradation (D*)</span><strong>{payload.targets.target_degradation_index.toFixed(2)}</strong></div>
              </div>
            </div>
          )}

          {highlight === 'balanced' && (
            <div className="pit-stop-list">
              <p className="block-hint">Pit loss at this track: {PIT_LOSS_SECONDS.toFixed(1)}s per stop (from recorded pit stop durations).</p>
              <h4>Pit stops</h4>
              {pitStops.length === 0 ? (
                <p className="empty-state">No pit stops in this strategy.</p>
              ) : (
                <>
                  {pitStops.map((stop) => (
                    <div key={stop.stopNumber} className="pit-stop-row">
                      <span className="pit-stop-index">Stop {stop.stopNumber}</span>
                      <span className="pit-stop-lap">Lap {stop.lap}</span>
                      <span className="pit-stop-change">
                        <span className="dot" data-compound={stop.fromCompound}></span>
                        {stop.fromCompound}
                        <span className="pit-stop-arrow">&rarr;</span>
                        <span className="dot" data-compound={stop.toCompound}></span>
                        {stop.toCompound}
                      </span>
                      <span className="pit-stop-cost">
                        {stop.costSeconds !== null ? `+${stop.costSeconds.toFixed(1)}s` : 'unknown'}
                      </span>
                    </div>
                  ))}
                  <div className="pit-stop-total">
                    <span>Total pit time</span>
                    <strong>
                      {pitLossKnown ? `+${(pitStops.length * payload.pit_loss_seconds!).toFixed(1)}s` : 'unknown'}
                    </strong>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </article>
    )
  }

  const WEIGHT_KEYS: (keyof GoalWeights)[] = ['weight_time_w1', 'weight_pit_stops_w2', 'weight_degradation_w3']

  const updateWeight = (key: keyof GoalWeights, value: number) => {
    setWeights((previous) => {
      const newValue = Math.min(1, Math.max(0, Number(value)))
      const otherKeys = WEIGHT_KEYS.filter((k) => k !== key)
      const otherSum = otherKeys.reduce((sum, k) => sum + previous[k], 0)
      const remaining = Math.max(0, 1 - newValue)

      const next = { ...previous, [key]: newValue }
      if (otherSum <= 0) {
        // Split the remainder evenly if the other two are both zero.
        otherKeys.forEach((k) => { next[k] = remaining / otherKeys.length })
      } else {
        // Rescale the other two proportionally so the total always stays at 1.
        otherKeys.forEach((k) => { next[k] = (previous[k] / otherSum) * remaining })
      }

      // Round to avoid floating-point drift (e.g. 0.30000000000000004) breaking the
      // backend's strict sum-to-1 validation.
      const rounded = WEIGHT_KEYS.reduce((acc, k) => ({ ...acc, [k]: Math.round(next[k] * 100) / 100 }), {} as GoalWeights)
      const roundedSum = WEIGHT_KEYS.reduce((sum, k) => sum + rounded[k], 0)
      const drift = Math.round((1 - roundedSum) * 100) / 100
      if (drift !== 0) {
        // Absorb any leftover rounding drift into the largest of the other two weights.
        const adjustKey = otherKeys.reduce((a, b) => (rounded[a] >= rounded[b] ? a : b))
        rounded[adjustKey] = Math.round((rounded[adjustKey] + drift) * 100) / 100
      }
      return rounded
    })
  }

  const runStrategyPreview = async () => {
    if (!selectedYear || !selectedRace) return
    setLoading(true)
    try {
      const maxPitStops = maxPitStopsInput.trim() === '' ? undefined : Number(maxPitStopsInput)
      const minStintLength = minStintLengthInput.trim() === '' ? undefined : Number(minStintLengthInput)

      const response = await fetch(`${API_BASE}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: selectedYear,
          race_name: selectedRace,
          driver_code: selectedDriver || undefined,
          weights,
          max_pit_stops: maxPitStops,
          min_stint_length: minStintLength,
        }),
      })

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const data = await response.json()
      setComparison(data)
      setStrategy(data?.scope1 ?? null)
    } catch (error) {
      console.error('Comparison failed', error)
      const fallback: StrategyPreview = {
        year: selectedYear,
        race_name: selectedRace,
        strategy: [],
        message: 'Unable to generate strategy comparison.',
      }
      setComparison(null)
      setStrategy(fallback)
    } finally {
      setLoading(false)
    }
  }

  const pitStopsSaved = useMemo(() => {
    if (!comparison) return 0
    const scope1Stops = Array.isArray(comparison.scope1?.pit_laps) ? comparison.scope1.pit_laps.length : 0
    return Math.max(0, scope1Stops - (comparison.scope2?.pit_stop_count ?? 0))
  }, [comparison])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Operations Research Project</p>
          <h1>F1 Race Strategy Optimizer</h1>
        </div>
      </header>

      <main className="dashboard">
        <section className="hero-panel card">
          <div>
            <p className="section-label">Project objective</p>
            <h2>Find the fastest and smartest tyre strategy for each Grand Prix.</h2>
          </div>
          <p className="hero-text">
            This dashboard evaluates the race using both optimization models: the fastest strategy from a MILP
            and the balanced strategy from goal programming with a realistic trade-off between lap time, pit stops,
            and tyre degradation.
          </p>
        </section>

        <section className="stats-grid">
          <article className="card stat-card">
            <span>Seasons</span>
            <strong>{dashboard?.years?.length ?? 0}</strong>
            <small>{dashboard?.years_range ?? 'N/A'}</small>
          </article>
          <article className="card stat-card">
            <span>Total races</span>
            <strong>{dashboard?.total_races ?? 0}</strong>
            <small>Historical GP entries</small>
          </article>
          <article className="card stat-card">
            <span>Drivers</span>
            <strong>{dashboard?.total_drivers ?? 0}</strong>
            <small>Driver-lap records</small>
          </article>
          <article className="card stat-card">
            <span>Dataset rows</span>
            <strong>{dashboard?.total_rows ?? 0}</strong>
            <small>{dashboard?.source ?? 'combined_dataset.csv'}</small>
          </article>
        </section>

        {overview && (
          <section className="card overview-panel">
            <div className="panel-header">
              <h3>Dataset overview</h3>
              <p className="panel-subtitle">
                {overview.total_teams} teams &middot; {overview.total_drivers} drivers &middot; {overview.total_rows.toLocaleString()} lap records
                across {overview.years_range}
              </p>
            </div>

            <div className="overview-grid">
              <div className="overview-block">
                <h4>Races per season</h4>
                <div className="bar-list">
                  {Object.entries(overview.races_per_year).map(([year, count]) => {
                    const maxCount = Math.max(...Object.values(overview.races_per_year))
                    return (
                      <div className="bar-row" key={year}>
                        <span className="bar-label">{year}</span>
                        <div className="bar-track">
                          <div className="bar-fill" style={{ width: `${(count / maxCount) * 100}%` }} />
                        </div>
                        <span className="bar-value">{count}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="overview-block">
                <h4>Compound usage (lap records)</h4>
                <div className="bar-list">
                  {Object.entries(overview.compound_distribution).map(([compound, count]) => {
                    const maxCount = Math.max(...Object.values(overview.compound_distribution))
                    return (
                      <div className="bar-row" key={compound}>
                        <span className="bar-label">
                          <span className="dot" data-compound={compound}></span>
                          {compound}
                        </span>
                        <div className="bar-track">
                          <div className="bar-fill" data-compound={compound} style={{ width: `${(count / maxCount) * 100}%` }} />
                        </div>
                        <span className="bar-value">{count.toLocaleString()}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="overview-block">
                <h4>Mean max stint life (laps)</h4>
                <p className="block-hint">Used as the max stint durability constraint in both models, for every compound a race actually used.</p>
                <div className="chip-list">
                  {Object.entries(overview.mean_max_stint_life_by_compound)
                    .filter(([compound]) => compound !== 'UNKNOWN')
                    .sort(([, a], [, b]) => b - a)
                    .map(([compound, laps]) => (
                      <div key={compound} className="stage-chip">
                        <span className="dot" data-compound={compound}></span>
                        <div>
                          <strong>{compound}</strong>
                          <small>{laps} laps avg</small>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              <div className="overview-block">
                <h4>Pit stop statistics</h4>
                <div className="summary-list">
                  <div><span>Recorded stops</span><strong>{overview.pit_stop_stats.count.toLocaleString()}</strong></div>
                  <div><span>Mean duration</span><strong>{overview.pit_stop_stats.mean_duration_seconds.toFixed(2)}s</strong></div>
                  <div><span>Fastest stop</span><strong>{overview.pit_stop_stats.min_duration_seconds.toFixed(2)}s</strong></div>
                  <div><span>Slowest stop</span><strong>{overview.pit_stop_stats.max_duration_seconds.toFixed(2)}s</strong></div>
                </div>
              </div>
            </div>
          </section>
        )}

        <section className="controls card">
          <div className="controls-group">
            <h4 className="controls-group-title">Race selection</h4>
            <div className="controls-group-fields controls-group-fields--three">
              <div className="field">
                <label htmlFor="year">Season</label>
                <select id="year" value={selectedYear} onChange={(event) => setSelectedYear(Number(event.target.value))}>
                  {seasons.map((year) => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="race">Grand Prix</label>
                <select id="race" value={selectedRace} onChange={(event) => setSelectedRace(event.target.value)}>
                  {races.map((race) => (
                    <option key={race} value={race}>{race}</option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="driver">Driver</label>
                <select id="driver" value={selectedDriver} onChange={(event) => setSelectedDriver(event.target.value)}>
                  <option value="">All drivers</option>
                  {drivers.map((driver) => (
                    <option key={driver} value={driver}>{driver}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="controls-group">
            <h4 className="controls-group-title">Strategy constraints</h4>
            <div className="controls-group-fields controls-group-fields--two">
              <div className="field">
                <label htmlFor="max-pit-stops">
                  Max pit stops
                  {comparison?.scope1?.max_pit_stops_valid_range && (
                    <small className="field-hint">
                      {' '}(valid {comparison.scope1.max_pit_stops_valid_range[0]}-{comparison.scope1.max_pit_stops_valid_range[1]})
                    </small>
                  )}
                </label>
                <input
                  id="max-pit-stops"
                  type="number"
                  min={1}
                  placeholder="Auto (data-driven)"
                  value={maxPitStopsInput}
                  onChange={(event) => setMaxPitStopsInput(event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="min-stint-length">
                  Min stint length (laps)
                  {comparison?.scope1?.min_stint_length_valid_range && (
                    <small className="field-hint">
                      {' '}(valid {comparison.scope1.min_stint_length_valid_range[0]}-{comparison.scope1.min_stint_length_valid_range[1]})
                    </small>
                  )}
                </label>
                <input
                  id="min-stint-length"
                  type="number"
                  min={1}
                  placeholder="Auto (data-driven)"
                  value={minStintLengthInput}
                  onChange={(event) => setMinStintLengthInput(event.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="controls-group controls-group--weights">
            <h4 className="controls-group-title">Goal priorities (Model 2)</h4>
            <div className="weight-box">
              <div className="weight-row">
                <span>Time</span>
                <strong>{weights.weight_time_w1.toFixed(2)}</strong>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={weights.weight_time_w1} onChange={(event) => updateWeight('weight_time_w1', Number(event.target.value))} />
              <div className="weight-row">
                <span>Pit stops</span>
                <strong>{weights.weight_pit_stops_w2.toFixed(2)}</strong>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={weights.weight_pit_stops_w2} onChange={(event) => updateWeight('weight_pit_stops_w2', Number(event.target.value))} />
              <div className="weight-row">
                <span>Degradation</span>
                <strong>{weights.weight_degradation_w3.toFixed(2)}</strong>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={weights.weight_degradation_w3} onChange={(event) => updateWeight('weight_degradation_w3', Number(event.target.value))} />
              <small className="field-hint">Always sums to 1.00 &mdash; adjusting one rescales the others.</small>
            </div>
          </div>

          <button type="button" className="primary-button" onClick={runStrategyPreview} disabled={loading}>
            {loading ? 'Generating...' : 'Generate strategy comparison'}
          </button>
          {!comparison && !loading && (
            <p className="controls-hint">Select a race above and click Generate to run both models.</p>
          )}
        </section>

        <section className="content-grid">
          <article className="card info-panel">
            <div className="panel-header">
              <h3>Race summary</h3>
            </div>
            {raceSummary ? (
              <div className="summary-list">
                <div><span>Season</span><strong>{raceSummary.year}</strong></div>
                <div><span>Race</span><strong>{raceSummary.race_name}</strong></div>
                <div><span>Total laps</span><strong>{raceSummary.total_laps}</strong></div>
                <div><span>Drivers</span><strong>{raceSummary.drivers?.length ?? 0}</strong></div>
                <div><span>Average lap time</span><strong>{raceSummary.average_lap_time_seconds?.toFixed(3)}s</strong></div>
              </div>
            ) : (
              <p className="empty-state">Choose a race to inspect the available data.</p>
            )}
          </article>

          <article className="card info-panel model-tabs-panel">
            <div className="model-tabs">
              <button
                type="button"
                className={activeModelTab === 'model1' ? 'model-tab active' : 'model-tab'}
                onClick={() => setActiveModelTab('model1')}
              >
                Model 1 - Fastest (MILP)
              </button>
              <button
                type="button"
                className={activeModelTab === 'model2' ? 'model-tab active' : 'model-tab'}
                onClick={() => setActiveModelTab('model2')}
              >
                Model 2 - Balanced (Goal Programming)
              </button>
            </div>
            {activeModelTab === 'model1'
              ? renderStrategyCard('Fastest strategy', comparison?.scope1 ?? strategy, 'fastest')
              : renderStrategyCard('Balanced strategy', comparison?.scope2 ?? null, 'balanced')}
          </article>
        </section>

        {comparison && (
          <section className="card comparison-panel">
            <div className="panel-header">
              <h3>Optimization trade-off</h3>
            </div>

            <div className="comparison-grid">
              <div className="metric-box accent">
                <span>Time difference</span>
                <strong>{comparison.time_delta_seconds >= 0 ? '+' : '-'}{Math.abs(comparison.time_delta_seconds).toFixed(2)} s</strong>
              </div>
              <div className="metric-box">
                <span>Pit stops saved</span>
                <strong>{pitStopsSaved}</strong>
              </div>
              <div className="metric-box">
                <span>Balanced race time</span>
                <strong>{(comparison.scope2?.balanced_race_time_seconds ?? 0).toFixed(1)} s</strong>
              </div>
            </div>

            <p className="comparison-note">{comparison.comparison_note}</p>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
