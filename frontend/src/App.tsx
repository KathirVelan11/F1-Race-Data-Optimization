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
  min_pit_stops?: number
  max_pit_stops?: number
  min_stint_length?: number
  min_pit_stops_valid_range?: [number, number]
  min_stint_length_valid_range?: [number, number]
  max_sets_per_compound?: Record<string, number>
  max_sets_per_compound_valid_range?: Record<string, [number, number]>
  risk_tiers?: Record<string, [number, number, number]>
  max_risk_tier_per_compound?: Record<string, number>
  risk_score?: number
  targets?: {
    target_race_time_seconds: number
    target_pit_stops: number
    target_risk_score: number
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [activeModelTab, setActiveModelTab] = useState<'model1' | 'model2'>('model1')
  const [overview, setOverview] = useState<DatasetOverview | null>(null)
  const [minPitStopsInput, setMinPitStopsInput] = useState<string>('')
  // Max pit stops (Model 2 only -- hard ceiling + Goal 2's target P*). '' means "no
  // extra ceiling beyond min pit stops" (backend defaults it to min_pit_stops itself).
  const [maxPitStopsInput, setMaxPitStopsInput] = useState<string>('')
  const [minStintLengthInput, setMinStintLengthInput] = useState<string>('')
  const [maxSoftSetsInput, setMaxSoftSetsInput] = useState<string>('')
  const [maxMediumSetsInput, setMaxMediumSetsInput] = useState<string>('')
  const [maxHardSetsInput, setMaxHardSetsInput] = useState<string>('')
  // Optional hard risk ceilings (Model 2 only). '' means "no limit" -- these are the
  // only tyre-related inputs that are NOT required, since a user with no opinion on
  // risk tolerance should just get the model's normal data-driven behavior.
  const [maxSoftRiskTier, setMaxSoftRiskTier] = useState<string>('')
  const [maxMediumRiskTier, setMaxMediumRiskTier] = useState<string>('')
  const [maxHardRiskTier, setMaxHardRiskTier] = useState<string>('')

  const RISK_TIER_NAMES = ['Low', 'Moderate', 'High', 'Very High']

  // Same 40%/70%/90%-of-durability split the backend uses (see
  // BackendOptimizationRunner._get_degradation_risk_tiers) -- mirrored here client-side
  // purely to show a reasonable estimate in the dropdown before the user has run a
  // comparison yet (dataset-wide average durability, from /api/dataset/overview, not
  // this specific race's real durability, which isn't known until a run completes).
  const estimateTiersFromDurability = (durability: number): [number, number, number] => {
    const t1 = Math.max(1, Math.round(durability * 0.4))
    const t2 = Math.max(t1 + 1, Math.round(durability * 0.7))
    const t3 = Math.max(t2 + 1, Math.round(durability * 0.9))
    return [t1, t2, t3]
  }

  // Builds the dropdown options for one compound, with lap-age cutoffs shown inline so
  // "Up to Moderate" never appears alone -- "Up to Moderate (tyre age <= 12 laps)" does.
  // Prefers this race's real risk_tiers (known once a comparison has run); before that,
  // falls back to a dataset-wide estimate from the overview stats, labeled "approx" since
  // it isn't specific to the selected race/circuit yet.
  const buildRiskTierOptions = (compound: string): { value: string; label: string }[] => {
    const realTiers = comparison?.scope2?.risk_tiers?.[compound]
    const estimatedDurability = overview?.mean_max_stint_life_by_compound?.[compound]
    const tiers = realTiers ?? (estimatedDurability ? estimateTiersFromDurability(estimatedDurability) : null)
    const approxSuffix = realTiers ? '' : ', approx'
    const ageFor = (tierIndex: number): string => {
      if (!tiers) return ''
      if (tierIndex === 3) return ` (age > ${tiers[2]} laps${approxSuffix})`
      return ` (age ≤ ${tiers[tierIndex]} laps${approxSuffix})`
    }
    return [
      { value: '', label: 'No limit' },
      { value: '0', label: `Low only${ageFor(0)}` },
      { value: '1', label: `Up to Moderate${ageFor(1)}` },
      { value: '2', label: `Up to High${ageFor(2)}` },
      { value: '3', label: 'Up to Very High (no limit)' },
    ]
  }

  const MAX_REASONABLE_SETS = 20

  // Parses one numeric input field. Every field here is required -- a blank value is
  // always an error, never silently treated as 0, so the Generate button stays disabled
  // until the user has explicitly entered all four values. Also flags every other edge
  // case this field could realistically hit: negative numbers, non-integer/garbage text,
  // and absurdly large values that are almost certainly a typo.
  const parseSetCount = (raw: string, label: string): { value: number; error: string | null } => {
    const trimmed = raw.trim()
    if (trimmed === '') return { value: 0, error: `${label}: required, please enter a value.` }

    const parsed = Number(trimmed)
    if (!Number.isFinite(parsed)) {
      return { value: 0, error: `${label}: enter a number.` }
    }
    if (!Number.isInteger(parsed)) {
      return { value: 0, error: `${label}: must be a whole number (no fractional tyre sets).` }
    }
    if (parsed < 0) {
      return { value: 0, error: `${label}: cannot be negative.` }
    }
    if (parsed > MAX_REASONABLE_SETS) {
      return { value: 0, error: `${label}: ${parsed} seems too high (max realistic value is ${MAX_REASONABLE_SETS}). Double-check this.` }
    }
    return { value: parsed, error: null }
  }

  const tyreSetValidation = useMemo(() => {
    const soft = parseSetCount(maxSoftSetsInput, 'Soft sets')
    const medium = parseSetCount(maxMediumSetsInput, 'Medium sets')
    const hard = parseSetCount(maxHardSetsInput, 'Hard sets')
    const pitStops = parseSetCount(minPitStopsInput, 'Min pit stops')

    // Max pit stops is optional (blank = no extra ceiling beyond min pit stops, same
    // convention as the risk-ceiling dropdowns) -- only validated when entered.
    const maxPitStopsTrimmed = maxPitStopsInput.trim()
    let maxPitStopsError: string | null = null
    let maxPitStopsValue: number | null = null
    if (maxPitStopsTrimmed !== '') {
      const parsed = Number(maxPitStopsTrimmed)
      if (!Number.isFinite(parsed)) {
        maxPitStopsError = 'Max pit stops: enter a number.'
      } else if (!Number.isInteger(parsed)) {
        maxPitStopsError = 'Max pit stops: must be a whole number.'
      } else if (parsed < 0) {
        maxPitStopsError = 'Max pit stops: cannot be negative.'
      } else if (pitStops.error === null && parsed < pitStops.value) {
        maxPitStopsError = `Max pit stops (${parsed}) cannot be less than min pit stops (${pitStops.value}).`
      } else {
        maxPitStopsValue = parsed
      }
    }

    const fieldErrors = [soft.error, medium.error, hard.error, pitStops.error, maxPitStopsError].filter(
      (error): error is string => error !== null
    )

    const totalSets = soft.value + medium.value + hard.value
    const stintsNeeded = pitStops.value + 1
    const feasibilityError =
      fieldErrors.length === 0 && totalSets < stintsNeeded
        ? `Not enough tyre sets: ${totalSets} entered (Soft ${soft.value} + Medium ${medium.value} + Hard ${hard.value}), ` +
          `but min pit stops = ${pitStops.value} needs at least ${stintsNeeded} stints. ` +
          `Add ${stintsNeeded - totalSets} more set(s), or lower min pit stops.`
        : null

    const allErrors = feasibilityError ? [...fieldErrors, feasibilityError] : fieldErrors

    return {
      isValid: allErrors.length === 0,
      errors: allErrors,
      totalSets,
      stintsNeeded,
      maxPitStopsValue,
    }
  }, [maxSoftSetsInput, maxMediumSetsInput, maxHardSetsInput, minPitStopsInput, maxPitStopsInput])

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

  // Ticking elapsed-time display while a solve is in flight. CBC runs as a black-box
  // subprocess with no real progress to stream back (no iteration count or % complete
  // is available), so this is honestly just "how long you've been waiting," not a
  // progress bar -- but it's enough to show the request is alive, not frozen.
  useEffect(() => {
    if (!loading) {
      setElapsedSeconds(0)
      return
    }
    const start = Date.now()
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - start) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [loading])

  const renderStrategyCard = (title: string, payload: StrategyPreview | null, highlight: 'fastest' | 'balanced') => {
    if (!payload || payload.strategy.length === 0) {
      const isValidationIssue = Boolean(payload?.message && payload.message !== 'Unable to generate strategy comparison.')
      return (
        <article className="card info-panel">
          <div className="panel-header">
            <h3>{title}</h3>
          </div>
          {isValidationIssue ? (
            <p className="empty-state empty-state--error">{payload!.message}</p>
          ) : (
            <p className="empty-state">No {title.toLowerCase()} strategy available yet.</p>
          )}
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
                <div><span>Target risk score (R*)</span><strong>{payload.targets.target_risk_score.toFixed(1)}</strong></div>
                {payload.risk_score !== undefined && (
                  <div><span>Achieved risk score</span><strong>{payload.risk_score.toFixed(1)}</strong></div>
                )}
              </div>
              {payload.max_risk_tier_per_compound && Object.keys(payload.max_risk_tier_per_compound).length > 0 && (
                <p className="block-hint">
                  Risk ceilings applied: {Object.entries(payload.max_risk_tier_per_compound)
                    .map(([compound, tier]) => {
                      const tiers = payload.risk_tiers?.[compound]
                      const tierName = RISK_TIER_NAMES[Number(tier)] ?? tier
                      const ageHint = tiers ? ` (age ≤ ${tiers[Number(tier)]} laps)` : ''
                      return `${compound} ≤ ${tierName}${ageHint}`
                    })
                    .join(', ')}
                </p>
              )}
            </div>
          )}

          {highlight === 'balanced' && (
            <div className="pit-stop-list">
              <p className="block-hint">
                Pit loss at this track: {pitLossKnown ? `${payload.pit_loss_seconds!.toFixed(1)}s` : 'unknown'} per stop (from recorded pit stop durations).
              </p>
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
      const minPitStops = minPitStopsInput.trim() === '' ? undefined : Number(minPitStopsInput)
      const maxPitStops = maxPitStopsInput.trim() === '' ? undefined : Number(maxPitStopsInput)
      const minStintLength = minStintLengthInput.trim() === '' ? undefined : Number(minStintLengthInput)

      const maxSetsPerCompound: Record<string, number> = {}
      if (maxSoftSetsInput.trim() !== '') maxSetsPerCompound.SOFT = Number(maxSoftSetsInput)
      if (maxMediumSetsInput.trim() !== '') maxSetsPerCompound.MEDIUM = Number(maxMediumSetsInput)
      if (maxHardSetsInput.trim() !== '') maxSetsPerCompound.HARD = Number(maxHardSetsInput)

      const maxRiskTierPerCompound: Record<string, number> = {}
      if (maxSoftRiskTier.trim() !== '') maxRiskTierPerCompound.SOFT = Number(maxSoftRiskTier)
      if (maxMediumRiskTier.trim() !== '') maxRiskTierPerCompound.MEDIUM = Number(maxMediumRiskTier)
      if (maxHardRiskTier.trim() !== '') maxRiskTierPerCompound.HARD = Number(maxHardRiskTier)

      const response = await fetch(`${API_BASE}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: selectedYear,
          race_name: selectedRace,
          driver_code: selectedDriver || undefined,
          weights,
          min_pit_stops: minPitStops,
          max_pit_stops: maxPitStops,
          min_stint_length: minStintLength,
          max_sets_per_compound: Object.keys(maxSetsPerCompound).length ? maxSetsPerCompound : undefined,
          max_risk_tier_per_compound: Object.keys(maxRiskTierPerCompound).length ? maxRiskTierPerCompound : undefined,
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

        <section className="card model-select-panel">
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
        </section>

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
                <label htmlFor="min-pit-stops">
                  Min pit stops
                  {comparison?.scope1?.min_pit_stops_valid_range && (
                    <small className="field-hint">
                      {' '}(typically {comparison.scope1.min_pit_stops_valid_range[0]}-{comparison.scope1.min_pit_stops_valid_range[1]})
                    </small>
                  )}
                </label>
                <input
                  id="min-pit-stops"
                  type="number"
                  min={0}
                  placeholder="Required"
                  value={minPitStopsInput}
                  onChange={(event) => setMinPitStopsInput(event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="max-pit-stops">
                  Max pit stops <small className="field-hint">(Model 2 only -- sets P*)</small>
                </label>
                <input
                  id="max-pit-stops"
                  type="number"
                  min={0}
                  placeholder="No extra limit"
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

          <div className="controls-group">
            <h4 className="controls-group-title">Tyre set allocation</h4>
            <p className="block-hint">
              How many sets of each compound you have available this weekend. All three
              fields are required (enter 0 if a compound isn't available). The total
              across all three must cover at least min pit stops + 1 stints, or the run
              will fail with an explanation.
            </p>
            <div className="controls-group-fields controls-group-fields--three">
              <div className="field">
                <label htmlFor="max-soft-sets">
                  Soft sets
                  {comparison?.scope1?.max_sets_per_compound_valid_range?.SOFT && (
                    <small className="field-hint">
                      {' '}(typically {comparison.scope1.max_sets_per_compound_valid_range.SOFT[0]}-{comparison.scope1.max_sets_per_compound_valid_range.SOFT[1]})
                    </small>
                  )}
                </label>
                <input
                  id="max-soft-sets"
                  type="number"
                  min={0}
                  placeholder="Required"
                  value={maxSoftSetsInput}
                  onChange={(event) => setMaxSoftSetsInput(event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="max-medium-sets">
                  Medium sets
                  {comparison?.scope1?.max_sets_per_compound_valid_range?.MEDIUM && (
                    <small className="field-hint">
                      {' '}(typically {comparison.scope1.max_sets_per_compound_valid_range.MEDIUM[0]}-{comparison.scope1.max_sets_per_compound_valid_range.MEDIUM[1]})
                    </small>
                  )}
                </label>
                <input
                  id="max-medium-sets"
                  type="number"
                  min={0}
                  placeholder="Required"
                  value={maxMediumSetsInput}
                  onChange={(event) => setMaxMediumSetsInput(event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="max-hard-sets">
                  Hard sets
                  {comparison?.scope1?.max_sets_per_compound_valid_range?.HARD && (
                    <small className="field-hint">
                      {' '}(typically {comparison.scope1.max_sets_per_compound_valid_range.HARD[0]}-{comparison.scope1.max_sets_per_compound_valid_range.HARD[1]})
                    </small>
                  )}
                </label>
                <input
                  id="max-hard-sets"
                  type="number"
                  min={0}
                  placeholder="Required"
                  value={maxHardSetsInput}
                  onChange={(event) => setMaxHardSetsInput(event.target.value)}
                />
              </div>
            </div>
          </div>

          {activeModelTab === 'model2' && (
            <div className="controls-group">
              <h4 className="controls-group-title">Max degradation-risk tier (Model 2 only)</h4>
              <p className="block-hint">
                Optional. Caps how worn a compound is ever allowed to get &mdash; a hard
                limit, not just a preference. Leave "No limit" if you don't want to
                restrict a compound.
                {!comparison?.scope2?.risk_tiers && (
                  <> Lap-age cutoffs shown below are dataset-wide approximations until
                  you run a comparison &mdash; after that, they're recalculated exactly
                  for the selected race's own tyre data.</>
                )}
              </p>
              <div className="controls-group-fields controls-group-fields--three">
                <div className="field">
                  <label htmlFor="max-soft-risk">Soft max risk</label>
                  <select
                    id="max-soft-risk"
                    value={maxSoftRiskTier}
                    onChange={(event) => setMaxSoftRiskTier(event.target.value)}
                  >
                    {buildRiskTierOptions('SOFT').map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="max-medium-risk">Medium max risk</label>
                  <select
                    id="max-medium-risk"
                    value={maxMediumRiskTier}
                    onChange={(event) => setMaxMediumRiskTier(event.target.value)}
                  >
                    {buildRiskTierOptions('MEDIUM').map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="max-hard-risk">Hard max risk</label>
                  <select
                    id="max-hard-risk"
                    value={maxHardRiskTier}
                    onChange={(event) => setMaxHardRiskTier(event.target.value)}
                  >
                    {buildRiskTierOptions('HARD').map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeModelTab === 'model2' && (
            <div className="controls-group controls-group--weights">
              <h4 className="controls-group-title">Goal priorities (Model 2 only)</h4>
              <p className="block-hint">
                Model 1 has a single objective (minimize race time) and no priorities to set.
                These weights only affect Model 2's balanced strategy.
              </p>
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
          )}

          {tyreSetValidation.errors.length > 0 && (
            <div className="validation-panel">
              {tyreSetValidation.errors.map((error) => (
                <p key={error} className="validation-error">{error}</p>
              ))}
            </div>
          )}

          <button
            type="button"
            className="primary-button"
            onClick={runStrategyPreview}
            disabled={loading || !tyreSetValidation.isValid}
          >
            {loading ? `Generating... ${elapsedSeconds}s` : 'Generate strategy comparison'}
          </button>
          {loading && (
            <p className="controls-hint">
              Solving both models (this can take a while for complex races) &mdash; the page is still working.
            </p>
          )}
          {!comparison && !loading && tyreSetValidation.isValid && (
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
