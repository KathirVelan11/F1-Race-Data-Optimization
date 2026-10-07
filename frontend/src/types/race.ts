/**
 * Race and data types for the frontend.
 */

export type TyreCompound =
  | 'SOFT'
  | 'MEDIUM'
  | 'HARD'
  | 'INTERMEDIATE'
  | 'WET'
  | 'ULTRASOFT'
  | 'SUPERSOFT'
  | 'HYPERSOFT';

export interface RaceSummary {
  raceId: number;
  year: number;
  raceName: string;
  totalLaps: number;
  driverCount: number;
}

export interface LapRecord {
  raceId: number;
  year: number;
  race: string;
  driver: string;
  team: string;
  lap: number;
  lapTime: string;
  lapTimeSeconds?: number;
  position: number;
  compound: TyreCompound;
  tyreLife: number;
  stint: number;
  pitDuration?: number;
}
