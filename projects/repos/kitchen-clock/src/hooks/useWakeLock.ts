import { useEffect } from 'react';

interface WakeLockSentinelLike {
  release: () => Promise<void>;
}

interface WakeLockLike {
  request: (type: 'screen') => Promise<WakeLockSentinelLike>;
}

export function useWakeLock() {
  useEffect(() => {
    if (typeof navigator === 'undefined' || typeof document === 'undefined') return;
    const wakeLockApi = (navigator as Navigator & { wakeLock?: WakeLockLike }).wakeLock;
    if (!wakeLockApi?.request) return;

    let sentinel: WakeLockSentinelLike | null = null;
    let active = true;

    const requestLock = async () => {
      if (!active || document.visibilityState !== 'visible') return;
      try {
        sentinel = await wakeLockApi.request('screen');
      } catch {
        sentinel = null;
      }
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void requestLock();
      }
    };

    void requestLock();
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      active = false;
      document.removeEventListener('visibilitychange', onVisibilityChange);
      if (sentinel) {
        void sentinel.release().catch(() => {});
      }
    };
  }, []);
}
