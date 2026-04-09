import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { ensureAndroidChannel } from '../utils/notifications';
import { loadSounds } from '../utils/sounds';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export function useNotifications() {
  useEffect(() => {
    (async () => {
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== 'granted') {
        console.warn('Notificaciones no concedidas');
      }
      await ensureAndroidChannel();
      await loadSounds();
    })();
  }, []);
}
