import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';
import { useTimerStore } from '../store/timerStore';

export function useTimerTick() {
  const tickAll = useTimerStore((s) => s.tickAll);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startTicking = () => {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(() => {
      tickAll();
    }, 1000);
  };

  const stopTicking = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    startTicking();

    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') startTicking();
    });

    return () => {
      stopTicking();
      subscription.remove();
    };
  }, [tickAll]);
}
