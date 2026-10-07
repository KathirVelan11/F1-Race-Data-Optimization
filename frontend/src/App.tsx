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
        </div>
      </article>
    )
  }

  const updateWeight = (key: keyof GoalWeights, value: number) => {
    setWeights((previous) => ({
      ...previous,
      [key]: Number(value),
    }))
  }

  const runStrategyPreview = async () => {
    if (!selectedYear || !selectedRace) return
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: selectedYear,
          race_name: selectedRace,
          driver_code: selectedDriver || undefined,
          weights,
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
        <div className="status-pill">React + FastAPI</div>
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

        <section className="controls card">
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

          <div className="field">
            <label>Goal priorities</label>
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
            </div>
          </div>

          <button type="button" className="primary-button" onClick={runStrategyPreview} disabled={loading}>
            {loading ? 'Generating...' : 'Generate strategy comparison'}
          </button>
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

          {renderStrategyCard('Fastest strategy', comparison?.scope1 ?? strategy, 'fastest')}
          {renderStrategyCard('Balanced strategy', comparison?.scope2 ?? null, 'balanced')}
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
