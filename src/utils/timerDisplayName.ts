/** Marcador en la tarjeta cuando no hay nombre guardado (guión largo tipográfico). */
export const TIMER_NAME_PLACEHOLDER_UI = '\u2014';

export function isTimerNameEmpty(name: string): boolean {
  return name.trim() === '';
}

/** Texto visible en la UI (píldora del timer). */
export function timerNameForDisplay(name: string): string {
  return isTimerNameEmpty(name) ? TIMER_NAME_PLACEHOLDER_UI : name.trim();
}

/** Texto en avisos / notificaciones (nunca cadena vacía). */
export function timerNameForNotification(name: string): string {
  return isTimerNameEmpty(name) ? 'Temporizador' : name.trim();
}
