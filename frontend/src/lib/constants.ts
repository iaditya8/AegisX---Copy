export const TERMINAL_SCANRUN_STATES = [
  'completed',
  'failed',
  'cancelled',
] as const;

export type TerminalScanRunState = typeof TERMINAL_SCANRUN_STATES[number];
