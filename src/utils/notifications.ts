import * as Notifications from 'expo-notifications';
import { timerNameForNotification } from './timerDisplayName';

export async function ensureAndroidChannel(): Promise<void> {
  await Notifications.setNotificationChannelAsync('kitchen-timers', {
    name: 'Kitchen timers',
    importance: Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 250, 250, 250],
    sound: 'alert.mp3',
  });
}

export async function sendTimerFinishedNotification(timerNames: string[]): Promise<void> {
  if (timerNames.length === 0) return;
  const title =
    timerNames.length === 1
      ? '⏰ ¡Timer terminado!'
      : `⏰ ${timerNames.length} timers han terminado`;
  const body =
    timerNames.length === 1
      ? `${timerNameForNotification(timerNames[0])} ha terminado`
      : timerNames.map(timerNameForNotification).join(', ');
  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      sound: true,
      priority: Notifications.AndroidNotificationPriority.MAX,
    },
    trigger: null,
  });
}

export async function scheduleTimerEndNotification(
  name: string,
  seconds: number
): Promise<string | null> {
  if (seconds <= 0) return null;
  await ensureAndroidChannel();
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title: '⏰ ¡Timer terminado!',
      body: `${timerNameForNotification(name)} ha terminado`,
      sound: true,
      priority: Notifications.AndroidNotificationPriority.MAX,
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds,
      repeats: false,
      channelId: 'kitchen-timers',
    },
  });
  return id;
}

export async function cancelAllScheduledTimerNotifications(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
}
