import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AudioConfig,
  AudioPresetId,
  Timer,
  resolveAudioConfig,
  useTimerStore,
} from '../store/timerStore';
import { playAlertSound, playBeepSound, stopAllSounds } from '../utils/sounds';

type AudibleAlertLevel = 'low' | 'medium' | 'critical';
type EffectiveAudibleLevel = AudibleAlertLevel | 'critical_escalated';

const ALERT_PRIORITY: Record<AudibleAlertLevel, number> = {
  low: 1,
  medium: 2,
  critical: 3,
};

function assertNever(value: never): never {
  throw new Error(`Unexpected alert level: ${String(value)}`);
}

function isTimerAudible(timer: Timer, waitingAckSequenceIds: Set<string>): boolean {
  if (timer.status === 'finished' && !timer.alertDismissed) return true;
  if (!timer.sequenceId) return false;
  if (timer.status === 'running') return false;
  return waitingAckSequenceIds.has(timer.sequenceId);
}

function getHighestPriorityLevel(levels: AudibleAlertLevel[]): AudibleAlertLevel | null {
  if (levels.length === 0) return null;
  return levels.reduce((highest, current) =>
    ALERT_PRIORITY[current] > ALERT_PRIORITY[highest] ? current : highest
  );
}

/** Pitidos de cola tras el alert en nivel crítico: 1–4 según agresividad del preset. */
function criticalTailBeepsCount(config: AudioConfig): number {
  return Math.max(1, Math.min(4, config.escalation.aggressiveness));
}

const TAIL_GAP_TIGHT_MS = 95;
/** Agresión 2 (Normal): solo 2 pitidos; si el hueco es 95 ms suenan como uno solo. */
const TAIL_GAP_NORMAL_PRESET_MS = 175;

function gapBetweenTailBeepsMs(aggression: number): number {
  if (aggression === 2) return TAIL_GAP_NORMAL_PRESET_MS;
  return TAIL_GAP_TIGHT_MS;
}

/** Tiempos desde el inicio del tick del patrón hasta cada pitido de cola (primer pitido a 140 ms). */
function tailBeepOffsetsFromPatternStartMs(aggression: number, tailCount: number): number[] {
  const offsets: number[] = [];
  let t = 140;
  for (let i = 0; i < tailCount; i += 1) {
    offsets.push(t);
    if (i < tailCount - 1) {
      t += gapBetweenTailBeepsMs(aggression);
    }
  }
  return offsets;
}

function startPattern(
  level: EffectiveAudibleLevel,
  config: AudioConfig
): ReturnType<typeof setInterval> {
  const v = config.playbackVolume;
  const aggression = Math.max(1, Math.min(4, config.escalation.aggressiveness));
  const criticalTailCount = criticalTailBeepsCount(config);
  const escalatedTailCount = Math.min(aggression + 1, 4);
  switch (level) {
    case 'low': {
      void playBeepSound(v);
      return setInterval(() => {
        void playBeepSound(v);
      }, config.intervalsMs.low);
    }
    case 'medium': {
      void playAlertSound(v);
      return setInterval(() => {
        void playAlertSound(v);
      }, config.intervalsMs.medium);
    }
    case 'critical': {
      void playAlertSound(v);
      return setInterval(() => {
        void playAlertSound(v);
        const offsets = tailBeepOffsetsFromPatternStartMs(aggression, criticalTailCount);
        for (const delay of offsets) {
          setTimeout(() => {
            void playBeepSound(v);
          }, delay);
        }
      }, config.intervalsMs.critical);
    }
    case 'critical_escalated': {
      void playAlertSound(v);
      setTimeout(() => {
        void playBeepSound(v);
      }, 80);
      return setInterval(() => {
        void playAlertSound(v);
        for (let i = 0; i < escalatedTailCount; i += 1) {
          const delay = 75 + i * 85;
          setTimeout(() => {
            void playBeepSound(v);
          }, delay);
        }
      }, config.intervalsMs.criticalEscalated);
    }
    default:
      return assertNever(level);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Siempre dos patrones críticos completos (no cortar uno a medias). */
const PREVIEW_CRITICAL_CYCLES = 2;

/** Duración de referencia = la prueba de Suave (2 ciclos + pausa entre ellos). */
const SUAVE_REFERENCE_CONFIG = resolveAudioConfig({ presetId: 'suave' });

/**
 * Tiempo aproximado de un ciclo de vista previa (mismos sleeps que el patrón reproducido + margen de audio).
 */
function estimateCriticalPreviewCycleMs(config: AudioConfig): number {
  const tails = criticalTailBeepsCount(config);
  const ag = Math.max(1, Math.min(4, config.escalation.aggressiveness));
  let scriptedDelaysMs = 140;
  for (let i = 1; i < tails; i += 1) {
    scriptedDelaysMs += gapBetweenTailBeepsMs(ag);
  }
  const playbackMarginMs = 280;
  return scriptedDelaysMs + playbackMarginMs;
}

function referencePreviewDurationMs(): number {
  const gap = SUAVE_REFERENCE_CONFIG.intervalsMs.critical;
  return (
    PREVIEW_CRITICAL_CYCLES * estimateCriticalPreviewCycleMs(SUAVE_REFERENCE_CONFIG) +
    (PREVIEW_CRITICAL_CYCLES - 1) * gap
  );
}

async function playCriticalPreviewCycle(
  volume: number,
  tailBeeps: number,
  aggression: number
): Promise<void> {
  await playAlertSound(volume);
  await sleep(140);
  await playBeepSound(volume);
  for (let i = 1; i < tailBeeps; i += 1) {
    await sleep(gapBetweenTailBeepsMs(aggression));
    await playBeepSound(volume);
  }
}

/**
 * Vista previa: dos ciclos del patrón **crítico** (misma cola de pitidos que la alarma en bucle).
 * La duración total se alinea con la de Suave (silencio extra entre ciclos solo en la prueba si hace falta).
 */
export async function testAudioPreset(presetId: AudioPresetId): Promise<void> {
  const config = resolveAudioConfig({ presetId });
  const v = config.playbackVolume;
  const tailBeeps = criticalTailBeepsCount(config);
  const aggression = Math.max(1, Math.min(4, config.escalation.aggressiveness));

  await stopAllSounds();

  const targetMs = referencePreviewDurationMs();
  const naturalMs =
    PREVIEW_CRITICAL_CYCLES * estimateCriticalPreviewCycleMs(config) +
    (PREVIEW_CRITICAL_CYCLES - 1) * config.intervalsMs.critical;
  const padBetweenCyclesMs = Math.max(0, targetMs - naturalMs);

  for (let c = 0; c < PREVIEW_CRITICAL_CYCLES; c += 1) {
    await playCriticalPreviewCycle(v, tailBeeps, aggression);
    if (c < PREVIEW_CRITICAL_CYCLES - 1) {
      await sleep(config.intervalsMs.critical + padBetweenCyclesMs);
    }
  }
}

export function useAudioAlerts() {
  const storeConfig = useTimerStore((s) => s.audioConfig);
  const mergedConfig = useMemo(() => resolveAudioConfig(storeConfig), [storeConfig]);
  const timers = useTimerStore((s) => s.timers);
  const sequences = useTimerStore((s) => s.sequences);
  const [clockMs, setClockMs] = useState(Date.now());

  useEffect(() => {
    const id = setInterval(() => setClockMs(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  const waitingAckSequenceIds = useMemo(() => {
    const ids = new Set<string>();
    for (const sequence of sequences) {
      if (sequence.status === 'waiting_ack') ids.add(sequence.id);
    }
    return ids;
  }, [sequences]);

  const hasEscalatedCritical = useMemo(() => {
    if (!mergedConfig.escalation.enabled) return false;
    const thresholdMs = Math.max(1, mergedConfig.escalation.noAckSeconds) * 1000;
    return sequences.some(
      (sequence) =>
        sequence.status === 'waiting_ack' &&
        sequence.waitingAckSince != null &&
        clockMs - sequence.waitingAckSince >= thresholdMs &&
        timers.some(
          (timer) =>
            timer.sequenceId === sequence.id &&
            timer.alertLevel === 'critical' &&
            !timer.alertDismissed
        )
    );
  }, [clockMs, mergedConfig.escalation, sequences, timers]);

  const activeLevel = useMemo((): EffectiveAudibleLevel | null => {
    const levels: AudibleAlertLevel[] = [];
    for (const timer of timers) {
      if (!isTimerAudible(timer, waitingAckSequenceIds)) continue;
      levels.push(timer.alertLevel);
    }
    const highest = getHighestPriorityLevel(levels);
    if (highest === 'critical' && hasEscalatedCritical) return 'critical_escalated';
    return highest;
  }, [timers, waitingAckSequenceIds, hasEscalatedCritical]);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentLevelRef = useRef<EffectiveAudibleLevel | null>(null);

  useEffect(() => {
    if (activeLevel === currentLevelRef.current) return;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    void stopAllSounds();
    currentLevelRef.current = activeLevel;
    if (activeLevel == null) return;
    intervalRef.current = startPattern(activeLevel, mergedConfig);
  }, [activeLevel, mergedConfig]);

  useEffect(
    () => () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      void stopAllSounds();
    },
    []
  );
}
