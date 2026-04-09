import { Audio } from 'expo-av';

let alertSound: Audio.Sound | null = null;
let beepSound: Audio.Sound | null = null;
let loadPromise: Promise<void> | null = null;

/** Evita solapar seek/play/stop en el mismo Sound (expo-av lanza "Seeking interrupted"). */
function createSoundOpQueue() {
  let chain: Promise<void> = Promise.resolve();
  return {
    enqueue(fn: () => Promise<void>): Promise<void> {
      const next = chain.then(fn, () => undefined);
      chain = next.catch(() => {});
      return next;
    },
  };
}

const alertOps = createSoundOpQueue();
const beepOps = createSoundOpQueue();

function isBenignAudioError(e: unknown): boolean {
  const msg = e instanceof Error ? e.message : String(e);
  return msg.includes('Seeking interrupted') || msg.includes('interrupted');
}

export async function loadSounds(): Promise<void> {
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    const { sound: a } = await Audio.Sound.createAsync(
      require('../../assets/sounds/alert.mp3')
    );
    const { sound: b } = await Audio.Sound.createAsync(
      require('../../assets/sounds/beep.mp3')
    );
    alertSound = a;
    beepSound = b;
    await Promise.all([a.setIsLoopingAsync(false), b.setIsLoopingAsync(false)]);

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      staysActiveInBackground: true,
      shouldDuckAndroid: false,
    });
  })();
  return loadPromise;
}

/** Refuerzo global (MP3 pueden ir bajos). Mantener ganancia moderada para que los presets sigan diferenciados. */
const PLAYBACK_GAIN = 1.12;

function clampVolume(volume: number): number {
  return Math.max(0, Math.min(1, volume * PLAYBACK_GAIN));
}

export async function playAlertSound(volume = 1): Promise<void> {
  if (!alertSound) return;
  return alertOps.enqueue(async () => {
    try {
      await alertSound!.setVolumeAsync(clampVolume(volume));
      await alertSound!.stopAsync();
      await alertSound!.setPositionAsync(0);
      await alertSound!.playAsync();
    } catch (e) {
      if (isBenignAudioError(e)) return;
      throw e;
    }
  });
}

export async function playBeepSound(volume = 1): Promise<void> {
  if (!beepSound) return;
  return beepOps.enqueue(async () => {
    try {
      await beepSound!.setVolumeAsync(clampVolume(volume));
      await beepSound!.stopAsync();
      await beepSound!.setPositionAsync(0);
      await beepSound!.playAsync();
    } catch (e) {
      if (isBenignAudioError(e)) return;
      throw e;
    }
  });
}

export async function stopAllSounds(): Promise<void> {
  await Promise.all([
    alertSound
      ? alertOps.enqueue(async () => {
          try {
            await alertSound!.stopAsync();
          } catch (e) {
            if (!isBenignAudioError(e)) throw e;
          }
        })
      : Promise.resolve(),
    beepSound
      ? beepOps.enqueue(async () => {
          try {
            await beepSound!.stopAsync();
          } catch (e) {
            if (!isBenignAudioError(e)) throw e;
          }
        })
      : Promise.resolve(),
  ]);
}
