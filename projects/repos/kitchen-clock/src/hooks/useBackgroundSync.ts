import { useEffect, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import {
  cancelAllScheduledTimerNotifications,
  scheduleTimerEndNotification,
} from '../utils/notifications';
import { getRemainingSeconds, useTimerStore } from '../store/timerStore';

export function useBackgroundSync() {
  const syncAfterResumeFromBackground = useTimerStore(
    (s) => s.syncAfterResumeFromBackground
  );
  const lastBackgroundRef = useRef<number | null>(null);

  useEffect(() => {
    const onChange = async (next: AppStateStatus) => {
      if (next === 'background') {
        lastBackgroundRef.current = Date.now();
        await cancelAllScheduledTimerNotifications();
        const running = useTimerStore.getState().timers.filter((t) => t.status === 'running');
        for (const t of running) {
          const sec = Math.max(1, getRemainingSeconds(t));
          await scheduleTimerEndNotification(t.name, sec);
        }
        return;
      }

      if (next === 'active' && lastBackgroundRef.current != null) {
        const elapsed = Math.floor((Date.now() - lastBackgroundRef.current) / 1000);
        lastBackgroundRef.current = null;
        await cancelAllScheduledTimerNotifications();
        syncAfterResumeFromBackground(elapsed);
      }
    };

    const sub = AppState.addEventListener('change', onChange);
    return () => sub.remove();
  }, [syncAfterResumeFromBackground]);
}
