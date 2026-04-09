import { useEffect, useRef, useState } from 'react';
import { useTimerStore } from '../store/timerStore';

interface SensorLike {
  start: () => void;
  stop: () => void;
  addEventListener: (event: 'reading' | 'error', listener: () => void) => void;
  removeEventListener: (event: 'reading' | 'error', listener: () => void) => void;
  distance?: number;
  near?: boolean;
  illuminance?: number;
}

type SensorCtor = new (options?: { frequency?: number }) => SensorLike;
type SensorMode = 'none' | 'proximity' | 'ambient';

const ACK_COOLDOWN_MS = 1500;
const PROXIMITY_DROP_CM = 4;
const LUX_DROP = 40;

function clampLux(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(2000, value));
}

export function useProximityAck() {
  const ackHighestPriorityWaiting = useTimerStore((s) => s.ackHighestPriorityWaiting);
  const [isSupported, setIsSupported] = useState(false);
  const [mode, setMode] = useState<SensorMode>('none');
  const baselineRef = useRef<number | null>(null);
  const lastTriggerRef = useRef(0);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const runtimeWindow = window as typeof globalThis & {
      ProximitySensor?: SensorCtor;
      AmbientLightSensor?: SensorCtor;
    };
    const ProximitySensorCtor = runtimeWindow.ProximitySensor;
    const AmbientLightSensorCtor = runtimeWindow.AmbientLightSensor;

    const triggerAck = () => {
      const now = Date.now();
      if (now - lastTriggerRef.current < ACK_COOLDOWN_MS) return;
      const waitingAckId = useTimerStore
        .getState()
        .sequences.find((sequence) => sequence.status === 'waiting_ack')?.id;
      if (!waitingAckId) return;
      lastTriggerRef.current = now;
      ackHighestPriorityWaiting();
    };

    let sensor: SensorLike | null = null;
    let onReading: (() => void) | null = null;

    try {
      if (ProximitySensorCtor) {
        sensor = new ProximitySensorCtor({ frequency: 8 });
        setMode('proximity');
        onReading = () => {
          if (!sensor) return;
          const near = Boolean(sensor.near);
          const distance = Number.isFinite(sensor.distance) ? Number(sensor.distance) : null;

          if (near) {
            triggerAck();
            baselineRef.current = null;
            return;
          }
          if (distance == null) return;
          const baseline = baselineRef.current;
          if (baseline == null) {
            baselineRef.current = distance;
            return;
          }
          const drop = baseline - distance;
          baselineRef.current = baseline * 0.8 + distance * 0.2;
          if (drop >= PROXIMITY_DROP_CM) {
            triggerAck();
            baselineRef.current = null;
          }
        };
      } else if (AmbientLightSensorCtor) {
        sensor = new AmbientLightSensorCtor({ frequency: 8 });
        setMode('ambient');
        onReading = () => {
          if (!sensor) return;
          const lux = clampLux(Number(sensor.illuminance ?? 0));
          const baseline = baselineRef.current;
          if (baseline == null) {
            baselineRef.current = lux;
            return;
          }
          const drop = baseline - lux;
          baselineRef.current = baseline * 0.9 + lux * 0.1;
          if (drop >= LUX_DROP) {
            triggerAck();
            baselineRef.current = null;
          }
        };
      } else {
        setMode('none');
        setIsSupported(false);
        return;
      }

      if (!sensor || !onReading) return;
      sensor.addEventListener('reading', onReading);
      sensor.start();
      setIsSupported(true);
    } catch {
      setMode('none');
      setIsSupported(false);
      return;
    }

    return () => {
      baselineRef.current = null;
      if (sensor && onReading) {
        sensor.removeEventListener('reading', onReading);
      }
      try {
        sensor?.stop();
      } catch {
        // no-op
      }
    };
  }, [ackHighestPriorityWaiting]);

  return {
    isSupported,
    mode,
  };
}
