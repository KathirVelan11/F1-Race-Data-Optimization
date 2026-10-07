/**
 * Optimization and strategy types for the frontend.
 */
import type { TyreCompound } from './race';

export interface StintPlan {
  stintNumber: number;
  compound: TyreCompound;
  startLap: number;
  endLap: number;
  stintLength: number;
  predictedStintTime: number;
}

export interface Scope1Result {
  minimumPredictedRaceTime: number;
  optimalPitLaps: number[];
  pitStopCount: number;
  stints: StintPlan[];
  lapCompounds: Record<number, string>;
  solverStatus: string;
  solveDurationSeconds: number;
}

export interface GoalDeviations {
  d1Plus: number;
  d1Minus: number;
  d2Plus: number;
  d2Minus: number;
  d3Plus: number;
  d3Minus: number;
}

export interface Scope2Result {
  balancedRaceTimeSeconds: number;
  timeDeltaVsFastestSeconds: number;
  pitStopCount: number;
  optimalPitLaps: number[];
  stints: StintPlan[];
  deviations: GoalDeviations;
  objectiveValueZ: number;
  solverStatus: string;
  solveDurationSeconds: number;
}

export interface StrategyComparison {
  scope1Result: Scope1Result;
  scope2Result: Scope2Result;
  timeDeltaSeconds: number;
  pitStopsSaved: number;
  recommendationSummary: string;
}

export interface GoalWeights {
  weightTimeW1: number;
  weightPitStopsW2: number;
  weightDegradationW3: number;
}
