import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Haptics from 'expo-haptics';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { sendTimerFinishedNotification } from '../utils/notifications';
import { playAlertSound } from '../utils/sounds';

export type TimerStatus = 'running' | 'paused' | 'finished' | 'idle';
export type AlertLevel = 'low' | 'medium' | 'critical';
export type SequenceStatus = 'idle' | 'running' | 'paused' | 'waiting_ack' | 'finished';

export interface AudioConfig {
  presetId: AudioPresetId;
  /** 0–1, según preset (Suave más bajo, Caos al máximo). */
  playbackVolume: number;
  intervalsMs: {
    low: number;
    medium: number;
    critical: number;
    criticalEscalated: number;
  };
  escalation: {
    enabled: boolean;
    noAckSeconds: number;
    aggressiveness: number;
  };
}

export type AudioPresetId = 'suave' | 'normal' | 'intenso' | 'caos';

export interface AudioPresetDefinition {
  id: AudioPresetId;
  label: string;
  description: string;
  config: Omit<AudioConfig, 'presetId'>;
}

export const AUDIO_PRESETS: Record<AudioPresetId, AudioPresetDefinition> = {
  suave: {
    id: 'suave',
    label: 'Suave',
    description: 'Avisos tranquilos y espaciados.',
    config: {
      playbackVolume: 0.62,
      intervalsMs: {
        low: 9000,
        medium: 3200,
        critical: 1300,
        criticalEscalated: 700,
      },
      escalation: {
        enabled: true,
        noAckSeconds: 15,
        aggressiveness: 1,
      },
    },
  },
  normal: {
    id: 'normal',
    label: 'Normal',
    description: 'Equilibrio para servicio regular.',
    config: {
      playbackVolume: 0.88,
      intervalsMs: {
        low: 7000,
        medium: 2200,
        critical: 900,
        criticalEscalated: 420,
      },
      escalation: {
        enabled: true,
        noAckSeconds: 11,
        aggressiveness: 2,
      },
    },
  },
  intenso: {
    id: 'intenso',
    label: 'Intenso',
    description: 'Respuesta rapida para picos de trabajo.',
    config: {
      playbackVolume: 0.92,
      intervalsMs: {
        low: 5200,
        medium: 1500,
        critical: 620,
        criticalEscalated: 300,
      },
      escalation: {
        enabled: true,
        noAckSeconds: 8,
        aggressiveness: 3,
      },
    },
  },
  caos: {
    id: 'caos',
    label: 'Caos',
    description: 'Maxima insistencia para cocina ruidosa.',
    config: {
      playbackVolume: 1,
      intervalsMs: {
        low: 3600,
        medium: 980,
        critical: 420,
        criticalEscalated: 180,
      },
      escalation: {
        enabled: true,
        noAckSeconds: 5,
        aggressiveness: 4,
      },
    },
  },
};

export interface Timer {
  id: string;
  name: string;
  totalSeconds: number;
  remainingSeconds: number;
  endTime: number | null;
  pausedRemainingSeconds: number | null;
  status: TimerStatus;
  color: string;
  createdAt: number;
  finishedAt: number | null;
  alertDismissed: boolean;
  sequenceId: string | null;
  sequenceStepId: string | null;
  alertLevel: AlertLevel;
}

export interface TimerSequenceStep {
  id: string;
  name: string;
  durationSeconds: number;
  autostart: boolean;
  alertLevel: AlertLevel;
}

export interface TimerSequence {
  id: string;
  name: string;
  color: string;
  steps: TimerSequenceStep[];
  currentStepIndex: number;
  status: SequenceStatus;
  currentTimerId: string | null;
  waitingAckSince: number | null;
  pendingAckStepId: string | null;
  pendingAckExpectedAt: number | null;
  createdAt: number;
  finishedAt: number | null;
  lastCompletedStepId: string | null;
}

export interface TimerStore {
  timers: Timer[];
  sequences: TimerSequence[];
  audioConfig: AudioConfig;

  addTimer: (params: {
    name: string;
    totalSeconds: number;
    color: string;
    startRunning?: boolean;
  }) => void;
  removeTimer: (id: string) => void;
  clearAllTimers: () => void;
  pauseTimer: (id: string) => void;
  resumeTimer: (id: string) => void;
  resetTimer: (id: string) => void;
  dismissAlert: (id: string) => void;
  tickAll: () => void;

  setTimerDuration: (id: string, totalSeconds: number) => void;
  setTimersOrder: (timers: Timer[]) => void;
  setTimerName: (id: string, name: string) => void;

  syncAfterResumeFromBackground: (elapsedSeconds: number) => void;
  startSequence: (sequenceId: string) => void;
  addSequence: (params: {
    name: string;
    color: string;
    steps: Omit<TimerSequenceStep, 'id'>[];
  }) => TimerSequence;
  nextStep: (sequenceId: string) => void;
  jumpToStep: (sequenceId: string, stepIndex: number) => void;
  updateAudioConfig: (updates: {
    presetId?: AudioPresetId;
    intervalsMs?: Partial<AudioConfig['intervalsMs']>;
    escalation?: Partial<AudioConfig['escalation']>;
  }) => void;
  ackHighestPriorityWaiting: () => string | null;

  loadFromStorage: () => Promise<void>;
  saveToStorage: () => Promise<void>;
}

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function finishTimers(names: string[], audioConfig: AudioConfig): void {
  if (names.length === 0) return;
  const vol = resolveAudioConfig(audioConfig).playbackVolume;
  void playAlertSound(vol);
  void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
  void sendTimerFinishedNotification(names);
}

function toDuration(value: number): number {
  return Math.max(1, Math.floor(value));
}

/** Standalone timers may start at 00:00; cap at 24h. */
export const MAX_TIMER_SECONDS = 24 * 3600;

function clampStandaloneDuration(value: number): number {
  return Math.min(MAX_TIMER_SECONDS, Math.max(0, Math.floor(value)));
}

export const DEFAULT_AUDIO_CONFIG: AudioConfig = {
  presetId: 'normal',
  playbackVolume: AUDIO_PRESETS.normal.config.playbackVolume,
  intervalsMs: {
    ...AUDIO_PRESETS.normal.config.intervalsMs,
  },
  escalation: {
    ...AUDIO_PRESETS.normal.config.escalation,
  },
};

function mergeAudioConfig(
  base: AudioConfig,
  updates: {
    presetId?: AudioPresetId;
    intervalsMs?: Partial<AudioConfig['intervalsMs']>;
    escalation?: Partial<AudioConfig['escalation']>;
  }
): AudioConfig {
  const nextPresetId = updates.presetId ?? base.presetId;
  const preset = AUDIO_PRESETS[nextPresetId];
  const presetConfig = preset?.config ?? AUDIO_PRESETS.normal.config;
  const preserveExistingValues = updates.presetId == null;
  return {
    presetId: nextPresetId,
    playbackVolume: updates.presetId != null
      ? presetConfig.playbackVolume
      : preserveExistingValues
        ? (base.playbackVolume ?? presetConfig.playbackVolume)
        : presetConfig.playbackVolume,
    intervalsMs: {
      ...presetConfig.intervalsMs,
      ...(preserveExistingValues ? base.intervalsMs : {}),
      ...(updates.intervalsMs ?? {}),
    },
    escalation: {
      ...presetConfig.escalation,
      ...(preserveExistingValues ? base.escalation : {}),
      ...(updates.escalation ?? {}),
    },
  };
}

function isAudioPresetId(value: unknown): value is AudioPresetId {
  return typeof value === 'string' && value in AUDIO_PRESETS;
}

function normalizeAudioConfig(raw?: Partial<AudioConfig>): AudioConfig {
  const basePresetId = isAudioPresetId(raw?.presetId) ? raw.presetId : DEFAULT_AUDIO_CONFIG.presetId;
  const presetConfig = AUDIO_PRESETS[basePresetId].config;
  return {
    presetId: basePresetId,
    playbackVolume:
      typeof raw?.playbackVolume === 'number' && raw.playbackVolume >= 0 && raw.playbackVolume <= 1
        ? raw.playbackVolume
        : presetConfig.playbackVolume,
    intervalsMs: {
      ...presetConfig.intervalsMs,
      ...(raw?.intervalsMs ?? {}),
    },
    escalation: {
      ...presetConfig.escalation,
      ...(raw?.escalation ?? {}),
    },
  };
}

export function resolveAudioConfig(config?: Partial<AudioConfig>): AudioConfig {
  return normalizeAudioConfig(config);
}

function alertLevelPriority(level: AlertLevel): number {
  switch (level) {
    case 'critical':
      return 3;
    case 'medium':
      return 2;
    case 'low':
      return 1;
    default:
      return 0;
  }
}

function getHighestPriorityWaitingAckSequenceId(state: Pick<TimerStore, 'sequences' | 'timers'>): string | null {
  const waiting = state.sequences.filter((seq) => seq.status === 'waiting_ack');
  if (waiting.length === 0) return null;
  const scored = waiting.map((sequence) => {
    const linkedTimers = state.timers.filter(
      (timer) => timer.sequenceId === sequence.id && !timer.alertDismissed
    );
    const highestAlert = linkedTimers.reduce<AlertLevel>(
      (highest, timer) =>
        alertLevelPriority(timer.alertLevel) > alertLevelPriority(highest) ? timer.alertLevel : highest,
      'low'
    );
    return {
      id: sequence.id,
      priority: alertLevelPriority(highestAlert),
      waitingSince: sequence.waitingAckSince ?? Number.MAX_SAFE_INTEGER,
    };
  });
  scored.sort((a, b) => {
    if (a.priority !== b.priority) return b.priority - a.priority;
    return a.waitingSince - b.waitingSince;
  });
  return scored[0]?.id ?? null;
}

export function getRemainingSeconds(timer: Timer, now = Date.now()): number {
  if (timer.status === 'finished') return 0;
  if (timer.status === 'running' && timer.endTime != null) {
    return Math.max(0, Math.ceil((timer.endTime - now) / 1000));
  }
  if (timer.pausedRemainingSeconds != null) {
    return Math.max(0, timer.pausedRemainingSeconds);
  }
  return Math.max(0, timer.remainingSeconds);
}

function startStepOnTimer(
  timer: Timer,
  sequence: TimerSequence,
  step: TimerSequenceStep,
  startAt: number
): Timer {
  const duration = toDuration(step.durationSeconds);
  return {
    ...timer,
    name: `${sequence.name}: ${step.name}`,
    totalSeconds: duration,
    remainingSeconds: duration,
    pausedRemainingSeconds: null,
    endTime: startAt + duration * 1000,
    status: 'running',
    finishedAt: null,
    alertDismissed: false,
    sequenceId: sequence.id,
    sequenceStepId: step.id,
    color: sequence.color,
    alertLevel: step.alertLevel,
  };
}

export const useTimerStore = create<TimerStore>()(
  persist(
    (set, get) => ({
      timers: [],
      sequences: [],
      audioConfig: DEFAULT_AUDIO_CONFIG,

      addTimer: ({
        name,
        totalSeconds,
        color,
        startRunning = true,
      }) => {
        const now = Date.now();
        const duration = clampStandaloneDuration(totalSeconds);
        const canRun = duration > 0;
        const status: TimerStatus =
          startRunning && canRun ? 'running' : startRunning && !canRun ? 'idle' : 'idle';
        const remainingSeconds = duration;
        const timer: Timer = {
          id: newId(),
          name,
          totalSeconds: duration,
          remainingSeconds,
          endTime: status === 'running' ? now + duration * 1000 : null,
          pausedRemainingSeconds: status === 'running' ? null : duration,
          status,
          color,
          createdAt: now,
          finishedAt: null,
          alertDismissed: false,
          sequenceId: null,
          sequenceStepId: null,
          alertLevel: 'medium',
        };
        set((s) => ({ timers: [...s.timers, timer] }));
      },

      removeTimer: (id) => {
        set((s) => ({ timers: s.timers.filter((t) => t.id !== id) }));
      },

      clearAllTimers: () => {
        set({ timers: [], sequences: [] });
      },

      pauseTimer: (id) => {
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        const now = Date.now();
        set((s) => {
          const timers = s.timers.map((t) => {
            if (t.id !== id || t.status !== 'running') return t;
            const remaining = getRemainingSeconds(t, now);
            return {
              ...t,
              status: 'paused' as const,
              remainingSeconds: remaining,
              pausedRemainingSeconds: remaining,
              endTime: null,
            };
          });
          const target = timers.find((t) => t.id === id);
          const sequences = s.sequences.map((seq) =>
            target?.sequenceId === seq.id && seq.status === 'running'
              ? { ...seq, status: 'paused' as const, waitingAckSince: null }
              : seq
          );
          return { timers, sequences };
        });
      },

      resumeTimer: (id) => {
        const now = Date.now();
        set((s) => {
          const timers = s.timers.map((t) => {
            if (t.id !== id) return t;
            if (t.status === 'paused' || t.status === 'idle') {
              const remaining = Math.max(
                0,
                t.pausedRemainingSeconds ?? t.remainingSeconds ?? t.totalSeconds
              );
              if (remaining === 0) {
                void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
                return t;
              }
              void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              return {
                ...t,
                status: 'running' as const,
                remainingSeconds: remaining,
                pausedRemainingSeconds: null,
                endTime: now + remaining * 1000,
              };
            }
            return t;
          });
          const target = timers.find((t) => t.id === id);
          const sequences = s.sequences.map((seq) =>
            target?.sequenceId === seq.id &&
            (seq.status === 'paused' || seq.status === 'waiting_ack' || seq.status === 'idle')
              ? { ...seq, status: 'running' as const, waitingAckSince: null }
              : seq
          );
          return { timers, sequences };
        });
      },

      resetTimer: (id) => {
        set((s) => {
          const timers = s.timers.map((t) =>
            t.id === id
              ? {
                  ...t,
                  remainingSeconds: t.totalSeconds,
                  pausedRemainingSeconds: t.totalSeconds,
                  endTime: null,
                  status: 'idle' as const,
                  finishedAt: null,
                  alertDismissed: false,
                }
              : t
          );
          const target = timers.find((t) => t.id === id);
          const sequences = s.sequences.map((seq) =>
            target?.sequenceId === seq.id
              ? {
                  ...seq,
                  currentStepIndex: 0,
                  status: 'idle' as const,
                  waitingAckSince: null,
                  finishedAt: null,
                  lastCompletedStepId: null,
                  pendingAckStepId: null,
                  pendingAckExpectedAt: null,
                }
              : seq
          );
          return { timers, sequences };
        });
      },

      dismissAlert: (id) => {
        set((s) => ({
          timers: s.timers.map((t) =>
            t.id === id ? { ...t, alertDismissed: true } : t
          ),
        }));
      },

      tickAll: () => {
        const now = Date.now();
        const s = get();
        const newlyFinished: string[] = [];
        const timers = s.timers.map((timer) => ({ ...timer }));
        const sequences = s.sequences.map((sequence) => ({ ...sequence }));
        const sequenceIndexById = new Map<string, number>();
        for (let i = 0; i < sequences.length; i += 1) {
          sequenceIndexById.set(sequences[i].id, i);
        }

        for (let i = 0; i < timers.length; i += 1) {
          const t = timers[i];
          if (t.status !== 'running') continue;
          if (t.endTime == null) {
            const rem = getRemainingSeconds(t, now);
            if (rem <= 0) {
              if (!t.sequenceId) {
                t.remainingSeconds = 0;
                t.pausedRemainingSeconds = 0;
                t.endTime = null;
                t.status = 'finished';
                t.finishedAt = now;
                newlyFinished.push(t.name);
                continue;
              }
              t.endTime = now;
            } else {
              t.endTime = now + rem * 1000;
            }
          }
          const remaining = getRemainingSeconds(t, now);
          if (remaining > 0) {
            t.remainingSeconds = remaining;
            continue;
          }

          if (!t.sequenceId) {
            t.remainingSeconds = 0;
            t.pausedRemainingSeconds = 0;
            t.endTime = null;
            t.status = 'finished';
            t.finishedAt = now;
            newlyFinished.push(t.name);
            continue;
          }

          const sequenceIndex = sequenceIndexById.get(t.sequenceId);
          if (sequenceIndex == null) {
            t.remainingSeconds = 0;
            t.pausedRemainingSeconds = 0;
            t.endTime = null;
            t.status = 'finished';
            t.finishedAt = now;
            newlyFinished.push(t.name);
            continue;
          }

          let sequence = sequences[sequenceIndex];
          let stepEndCursor = t.endTime;
          let shouldStop = false;
          while (!shouldStop) {
            const currentStep = sequence.steps[sequence.currentStepIndex];
            const nextStepIndex = sequence.currentStepIndex + 1;
            const nextStep = sequence.steps[nextStepIndex];
            sequence = {
              ...sequence,
              lastCompletedStepId: currentStep?.id ?? sequence.lastCompletedStepId,
            };

            if (!nextStep) {
              sequence = {
                ...sequence,
                status: 'finished',
                waitingAckSince: null,
                pendingAckStepId: null,
                pendingAckExpectedAt: null,
                finishedAt: now,
                currentTimerId: t.id,
              };
              t.remainingSeconds = 0;
              t.pausedRemainingSeconds = 0;
              t.endTime = null;
              t.status = 'finished';
              t.finishedAt = now;
              t.alertDismissed = false;
              newlyFinished.push(t.name);
              shouldStop = true;
              continue;
            }

            sequence = { ...sequence, currentStepIndex: nextStepIndex };

            if (!currentStep?.autostart) {
              const waitDuration = toDuration(nextStep.durationSeconds);
              t.name = `${sequence.name}: ${nextStep.name}`;
              t.totalSeconds = waitDuration;
              t.remainingSeconds = waitDuration;
              t.pausedRemainingSeconds = waitDuration;
              t.endTime = null;
              t.status = 'paused';
              t.finishedAt = null;
              t.sequenceStepId = nextStep.id;
              t.alertDismissed = false;
              t.alertLevel = nextStep.alertLevel;
              sequence = {
                ...sequence,
                status: 'waiting_ack',
                currentTimerId: t.id,
                pendingAckStepId: currentStep?.id ?? null,
                pendingAckExpectedAt: stepEndCursor ?? now,
              };
              sequence.waitingAckSince = now;
              newlyFinished.push(`${sequence.name}: ${currentStep?.name ?? 'Paso completado'}`);
              shouldStop = true;
              continue;
            }

            const started = startStepOnTimer(t, sequence, nextStep, stepEndCursor);
            Object.assign(t, started);
            sequence = { ...sequence, status: 'running', currentTimerId: t.id };
            sequence.waitingAckSince = null;
            sequence.pendingAckStepId = null;
            sequence.pendingAckExpectedAt = null;
            stepEndCursor = started.endTime ?? now;
            const chainedRemaining = getRemainingSeconds(started, now);
            if (chainedRemaining > 0) {
              t.remainingSeconds = chainedRemaining;
              shouldStop = true;
            }
          }

          sequences[sequenceIndex] = sequence;
        }

        set({ timers, sequences });
        finishTimers(newlyFinished, s.audioConfig);
      },

      setTimerDuration: (id, totalSeconds) => {
        const duration = clampStandaloneDuration(totalSeconds);
        const now = Date.now();
        set((s) => ({
          timers: s.timers.map((t) => {
            if (t.id !== id) return t;
            if (t.sequenceId) return t;
            if (t.status === 'running') {
              return {
                ...t,
                totalSeconds: duration,
                remainingSeconds: duration,
                pausedRemainingSeconds: null,
                endTime: duration > 0 ? now + duration * 1000 : null,
                status: duration > 0 ? ('running' as const) : ('idle' as const),
                finishedAt: null,
                alertDismissed: false,
              };
            }
            if (t.status === 'paused' || t.status === 'idle') {
              return {
                ...t,
                totalSeconds: duration,
                remainingSeconds: duration,
                pausedRemainingSeconds: duration,
                endTime: null,
                status: t.status === 'paused' ? ('paused' as const) : ('idle' as const),
                finishedAt: null,
                alertDismissed: false,
              };
            }
            if (t.status === 'finished') {
              return {
                ...t,
                totalSeconds: duration,
                remainingSeconds: duration,
                pausedRemainingSeconds: duration,
                endTime: null,
                status: 'idle' as const,
                finishedAt: null,
                alertDismissed: false,
              };
            }
            return t;
          }),
        }));
      },

      setTimersOrder: (ordered) => {
        set({ timers: ordered });
      },

      setTimerName: (id, name) => {
        set((s) => ({
          timers: s.timers.map((t) => (t.id === id ? { ...t, name } : t)),
        }));
      },

      syncAfterResumeFromBackground: (elapsedSeconds) => {
        if (elapsedSeconds <= 0) return;
        get().tickAll();
      },

      startSequence: (sequenceId) => {
        const now = Date.now();
        set((state) => {
          const sequence = state.sequences.find((s) => s.id === sequenceId);
          if (!sequence || sequence.steps.length === 0) return state;
          const safeIndex = Math.min(
            Math.max(0, sequence.currentStepIndex),
            sequence.steps.length - 1
          );
          const step = sequence.steps[safeIndex];
          const timerId = sequence.currentTimerId ?? newId();
          const existingTimer = state.timers.find((t) => t.id === timerId);
          const baseTimer: Timer =
            existingTimer ??
            ({
              id: timerId,
              name: `${sequence.name}: ${step.name}`,
              totalSeconds: toDuration(step.durationSeconds),
              remainingSeconds: toDuration(step.durationSeconds),
              endTime: null,
              pausedRemainingSeconds: null,
              status: 'idle',
              color: sequence.color,
              createdAt: now,
              finishedAt: null,
              alertDismissed: false,
              sequenceId: sequence.id,
              sequenceStepId: step.id,
              alertLevel: step.alertLevel,
            } as Timer);

          const startedTimer = startStepOnTimer(baseTimer, sequence, step, now);
          const timers = existingTimer
            ? state.timers.map((t) => (t.id === timerId ? startedTimer : t))
            : [...state.timers, startedTimer];
          const sequences = state.sequences.map((s) =>
            s.id === sequenceId
              ? {
                  ...s,
                  currentStepIndex: safeIndex,
                  currentTimerId: timerId,
                  status: 'running' as const,
                  waitingAckSince: null,
                  pendingAckStepId: null,
                  pendingAckExpectedAt: null,
                  finishedAt: null,
                }
              : s
          );
          return { timers, sequences };
        });
      },

      addSequence: ({ name, color, steps }) => {
        const normalizedSteps: TimerSequenceStep[] = steps
          .map((step) => ({
            id: newId(),
            name: step.name.trim() || 'Paso',
            durationSeconds: toDuration(step.durationSeconds),
            autostart: Boolean(step.autostart),
            alertLevel: step.alertLevel ?? 'medium',
          }))
          .filter((step) => step.durationSeconds > 0);
        const sequence: TimerSequence = {
          id: newId(),
          name: name.trim() || 'Secuencia',
          color,
          steps: normalizedSteps,
          currentStepIndex: 0,
          status: 'idle',
          currentTimerId: null,
          createdAt: Date.now(),
          finishedAt: null,
          waitingAckSince: null,
          lastCompletedStepId: null,
          pendingAckStepId: null,
          pendingAckExpectedAt: null,
        };
        set((state) => ({ sequences: [...state.sequences, sequence] }));
        return sequence;
      },

      nextStep: (sequenceId) => {
        const now = Date.now();
        let acknowledged = false;
        set((state) => {
          const sequence = state.sequences.find((s) => s.id === sequenceId);
          if (!sequence || sequence.steps.length === 0) return state;
          if (sequence.status === 'finished') return state;
          const currentStep = sequence.steps[sequence.currentStepIndex];
          const timerId = sequence.currentTimerId;
          if (!timerId) return state;
          const timer = state.timers.find((t) => t.id === timerId);
          if (!timer) return state;
          const started = startStepOnTimer(timer, sequence, currentStep, now);
          const timers = state.timers.map((t) => (t.id === timerId ? started : t));
          const sequences = state.sequences.map((s) =>
            s.id === sequenceId
              ? {
                  ...s,
                  status: 'running' as const,
                  waitingAckSince: null,
                  pendingAckStepId: null,
                  pendingAckExpectedAt: null,
                }
              : s
          );
          acknowledged = true;
          return { timers, sequences };
        });
        if (acknowledged) {
          void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
        }
      },

      jumpToStep: (sequenceId, stepIndex) => {
        const now = Date.now();
        set((state) => {
          const sequence = state.sequences.find((s) => s.id === sequenceId);
          if (!sequence || sequence.steps.length === 0) return state;
          const clampedIndex = Math.min(Math.max(0, stepIndex), sequence.steps.length - 1);
          const step = sequence.steps[clampedIndex];
          const timerId = sequence.currentTimerId ?? newId();
          const existingTimer = state.timers.find((t) => t.id === timerId);
          const shouldRun = sequence.status === 'running';
          const duration = toDuration(step.durationSeconds);
          const nextTimer: Timer = shouldRun
            ? startStepOnTimer(
                existingTimer ??
                  ({
                    id: timerId,
                    name: `${sequence.name}: ${step.name}`,
                    totalSeconds: duration,
                    remainingSeconds: duration,
                    endTime: null,
                    pausedRemainingSeconds: duration,
                    status: 'idle',
                    color: sequence.color,
                    createdAt: now,
                    finishedAt: null,
                    alertDismissed: false,
                    sequenceId: sequence.id,
                    sequenceStepId: step.id,
                    alertLevel: step.alertLevel,
                  } as Timer),
                sequence,
                step,
                now
              )
            : {
                ...(existingTimer ??
                  ({
                    id: timerId,
                    name: `${sequence.name}: ${step.name}`,
                    totalSeconds: duration,
                    remainingSeconds: duration,
                    endTime: null,
                    pausedRemainingSeconds: duration,
                    status: 'idle',
                    color: sequence.color,
                    createdAt: now,
                    finishedAt: null,
                    alertDismissed: false,
                    sequenceId: sequence.id,
                    sequenceStepId: step.id,
                    alertLevel: step.alertLevel,
                  } as Timer)),
                name: `${sequence.name}: ${step.name}`,
                totalSeconds: duration,
                remainingSeconds: duration,
                pausedRemainingSeconds: duration,
                endTime: null,
                status: 'paused' as const,
                sequenceId: sequence.id,
                sequenceStepId: step.id,
                alertLevel: step.alertLevel,
                finishedAt: null,
                alertDismissed: false,
              };

          const timers = existingTimer
            ? state.timers.map((t) => (t.id === timerId ? nextTimer : t))
            : [...state.timers, nextTimer];
          const sequences = state.sequences.map((s) =>
            s.id === sequenceId
              ? {
                  ...s,
                  currentStepIndex: clampedIndex,
                  currentTimerId: timerId,
                  status: shouldRun ? ('running' as const) : ('paused' as const),
                  waitingAckSince: null,
                  finishedAt: null,
                  pendingAckStepId: null,
                  pendingAckExpectedAt: null,
                }
              : s
          );
          return { timers, sequences };
        });
      },

      updateAudioConfig: (updates) => {
        set((state) => ({
          audioConfig: mergeAudioConfig(state.audioConfig, updates),
        }));
      },

      ackHighestPriorityWaiting: () => {
        const state = get();
        const selectedId = getHighestPriorityWaitingAckSequenceId(state);
        if (!selectedId) return null;
        state.nextStep(selectedId);
        return selectedId;
      },

      loadFromStorage: async () => {
        await useTimerStore.persist.rehydrate();
      },

      saveToStorage: async () => {
        /* persist middleware persists automatically on each change */
      },
    }),
    {
      name: 'kitchenclock-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        timers: state.timers,
        sequences: state.sequences,
        audioConfig: state.audioConfig,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        const now = Date.now();
        state.timers = state.timers.map((t) => {
          const migrated: Timer = {
            ...t,
            endTime: t.endTime ?? null,
            pausedRemainingSeconds:
              t.pausedRemainingSeconds ??
              (t.status === 'running'
                ? getRemainingSeconds({ ...t, endTime: t.endTime ?? null } as Timer, now)
                : t.remainingSeconds),
            sequenceId: t.sequenceId ?? null,
            sequenceStepId: t.sequenceStepId ?? null,
            alertLevel: t.alertLevel ?? 'medium',
          };
          if (migrated.status === 'running') {
            const remaining = getRemainingSeconds(migrated, now);
            return {
              ...migrated,
              status: 'paused' as const,
              remainingSeconds: remaining,
              pausedRemainingSeconds: remaining,
              endTime: null,
            };
          }
          return migrated;
        });
        state.sequences = (state.sequences ?? []).map((seq) => ({
          ...seq,
          status: seq.status === 'running' ? 'paused' : seq.status,
          waitingAckSince: seq.waitingAckSince ?? null,
          pendingAckStepId: seq.pendingAckStepId ?? null,
          pendingAckExpectedAt: seq.pendingAckExpectedAt ?? null,
          currentStepIndex: Math.min(
            Math.max(0, seq.currentStepIndex ?? 0),
            Math.max(0, seq.steps.length - 1)
          ),
        }));
        state.audioConfig = normalizeAudioConfig(state.audioConfig ?? {});
      },
    }
  )
);
