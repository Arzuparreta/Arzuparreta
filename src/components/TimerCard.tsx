import * as Haptics from 'expo-haptics';
import { MaterialIcons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Animated,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { DANGER, SUCCESS, TEXT_PRIMARY, WARNING } from '../constants/colors';
import { Font } from '../theme/typography';
import { DurationPickerModal } from './DurationPickerModal';
import { getRemainingSeconds, Timer, useTimerStore } from '../store/timerStore';
import { isTimerNameEmpty, timerNameForDisplay } from '../utils/timerDisplayName';
import { formatTime } from '../utils/timeFormat';
import { PromptModal } from './PromptModal';

const ACTION_HIT_SLOP = { top: 6, bottom: 6, left: 4, right: 4 } as const;
/** Máx. ancho del área del nombre (nombres cortos de paso en cocina). */
const NAME_MAX_WIDTH = 228;
const ICON_SIDE = 24;
const ICON_PRIMARY = 26;

interface TimerCardProps {
  timer: Timer;
  compact?: boolean;
}

export function TimerCard({ timer, compact = false }: TimerCardProps) {
  const {
    id,
    name,
    status,
    alertDismissed,
  } = timer;

  const pauseTimer = useTimerStore((s) => s.pauseTimer);
  const resumeTimer = useTimerStore((s) => s.resumeTimer);
  const resetTimer = useTimerStore((s) => s.resetTimer);
  const removeTimer = useTimerStore((s) => s.removeTimer);
  const dismissAlert = useTimerStore((s) => s.dismissAlert);
  const setTimerName = useTimerStore((s) => s.setTimerName);
  const setTimerDuration = useTimerStore((s) => s.setTimerDuration);
  const nextStep = useTimerStore((s) => s.nextStep);
  const sequence = useTimerStore((s) =>
    timer.sequenceId ? s.sequences.find((seq) => seq.id === timer.sequenceId) ?? null : null
  );

  const [prompt, setPrompt] = useState<null | { kind: 'name'; current: string }>(null);
  const [durationOpen, setDurationOpen] = useState(false);
  const [durationInitialSeconds, setDurationInitialSeconds] = useState(0);

  const pulseAnim = useRef(new Animated.Value(1)).current;
  const bumpAnim = useRef(new Animated.Value(1)).current;
  const [nowTs, setNowTs] = useState(Date.now());
  const liveRemainingSeconds = getRemainingSeconds(timer, nowTs);
  const prevRemainingRef = useRef(liveRemainingSeconds);

  const isFinishedAlert = status === 'finished' && !alertDismissed;
  const isFinishedDismissed = status === 'finished' && alertDismissed;
  const isWaitingAck = sequence?.status === 'waiting_ack';
  const hasSequence = sequence != null && timer.sequenceId != null;
  const currentStepNumber = (sequence?.currentStepIndex ?? 0) + 1;
  const totalSteps = sequence?.steps.length ?? 0;
  const lastTen = status === 'running' && liveRemainingSeconds <= 10 && liveRemainingSeconds > 0;

  useEffect(() => {
    const idInterval = setInterval(() => setNowTs(Date.now()), 100);
    return () => clearInterval(idInterval);
  }, []);

  useEffect(() => {
    if ((status === 'finished' && !alertDismissed) || isWaitingAck) {
      const loop = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 0.62,
            duration: 520,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 520,
            useNativeDriver: true,
          }),
        ])
      );
      loop.start();
      return () => {
        loop.stop();
        pulseAnim.setValue(1);
      };
    }
    pulseAnim.stopAnimation();
    pulseAnim.setValue(1);
    return undefined;
  }, [status, alertDismissed, isWaitingAck, pulseAnim]);

  useEffect(() => {
    if (
      lastTen &&
      liveRemainingSeconds !== prevRemainingRef.current &&
      liveRemainingSeconds > 0
    ) {
      Animated.sequence([
        Animated.timing(bumpAnim, {
          toValue: 1.06,
          duration: 70,
          useNativeDriver: true,
        }),
        Animated.timing(bumpAnim, {
          toValue: 1,
          duration: 80,
          useNativeDriver: true,
        }),
      ]).start();
    }
    prevRemainingRef.current = liveRemainingSeconds;
  }, [liveRemainingSeconds, lastTen, bumpAnim]);

  const confirmRemove = () => {
    const message = isTimerNameEmpty(name)
      ? '¿Eliminar este temporizador?'
      : `¿Eliminar «${name.trim()}»?`;
    Alert.alert('Eliminar timer', message, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: () => removeTimer(id) },
    ]);
  };

  const openNameEditor = () => {
    setPrompt({ kind: 'name', current: name });
  };

  const onTimePress = () => {
    if (isFinishedAlert) {
      dismissAlert(id);
      return;
    }
    if (hasSequence) return;
    setDurationInitialSeconds(getRemainingSeconds(timer, Date.now()));
    setDurationOpen(true);
  };

  const toggleRun = () => {
    if (status === 'running') pauseTimer(id);
    else resumeTimer(id);
  };

  const timeSize = compact ? 26 : 32;

  let backgroundColor = '#131416';
  let borderColor = '#2C3036';
  let borderWidth = 1;
  let borderStyle: 'solid' | 'dashed' = 'solid';
  let timeColor = '#ECEEF2';
  let nameColor = '#D1D6DE';
  let buttonPressedOpacity = 0.75;

  if (status === 'paused') {
    backgroundColor = '#111214';
    borderColor = '#3A4049';
    borderWidth = 1;
    borderStyle = 'dashed';
    timeColor = '#8E96A3';
    nameColor = '#A8B0BC';
  } else if (isFinishedAlert) {
    backgroundColor = '#1C1818';
    borderColor = '#5C4A4C';
    borderWidth = 1;
    timeColor = '#F0F2F5';
    nameColor = '#D8DCE2';
  } else if (isFinishedDismissed) {
    backgroundColor = '#121315';
    borderColor = '#2E3238';
    borderWidth = 1;
    timeColor = '#8B939E';
    nameColor = '#9CA4AE';
  } else if (status === 'idle') {
    backgroundColor = '#121315';
    borderColor = '#2E3238';
    borderWidth = 1;
    timeColor = '#9098A4';
    nameColor = '#AEB6C2';
  }

  if (timer.alertLevel === 'critical') {
    backgroundColor = '#1E1B1A';
    borderColor = '#8A7A68';
    borderWidth = 1;
    borderStyle = 'solid';
    timeColor = '#F2F0ED';
    nameColor = '#E0DCD6';
  }

  if (lastTen) {
    backgroundColor = '#1A1917';
    borderColor = '#5E564C';
  }

  if (isWaitingAck) {
    backgroundColor = timer.alertLevel === 'critical' ? '#221E1C' : '#1A1817';
    borderColor = '#7A7268';
    borderWidth = Math.max(2, borderWidth);
    buttonPressedOpacity = 0.72;
  }

  const primaryLabel =
    status === 'running' ? 'Pausar' : status === 'paused' ? 'Reanudar' : 'Iniciar';

  const renderActionRow = () => {
    if (isFinishedAlert) {
      return (
        <View style={styles.actionRow}>
          <Pressable
            style={({ pressed }) => [styles.btnOkFull, { opacity: pressed ? buttonPressedOpacity : 1 }]}
            onPress={() => {
              void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
              dismissAlert(id);
            }}
            accessibilityRole="button"
            accessibilityLabel="Cerrar alerta de temporizador listo"
            hitSlop={ACTION_HIT_SLOP}
          >
            <MaterialIcons name="check-circle" size={ICON_PRIMARY} color="#E8FFF0" />
            <Text style={styles.btnOkFullText}>Entendido</Text>
          </Pressable>
        </View>
      );
    }

    if (status === 'finished' && alertDismissed) {
      return (
        <View style={[styles.actionRow, styles.actionRowEnd]}>
          <Pressable
            style={({ pressed }) => [styles.btnIconSquare, styles.btnReset, { opacity: pressed ? buttonPressedOpacity : 1 }]}
            onPress={() => resetTimer(id)}
            accessibilityRole="button"
            accessibilityLabel="Reiniciar temporizador"
            hitSlop={ACTION_HIT_SLOP}
          >
            <MaterialIcons name="replay" size={ICON_SIDE} color="#D8DDE4" />
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.btnIconSquare, styles.btnDelete, { opacity: pressed ? buttonPressedOpacity : 1 }]}
            onPress={confirmRemove}
            accessibilityRole="button"
            accessibilityLabel="Eliminar temporizador"
            hitSlop={ACTION_HIT_SLOP}
          >
            <MaterialIcons name="delete-outline" size={ICON_SIDE} color={DANGER} />
          </Pressable>
        </View>
      );
    }

    if (!isFinishedAlert && status !== 'finished') {
      return (
        <View style={styles.actionRow}>
          {isWaitingAck && timer.sequenceId ? (
            <Pressable
              style={({ pressed }) => [styles.btnIconSquare, styles.btnAck, { opacity: pressed ? buttonPressedOpacity : 1 }]}
              onPress={() => nextStep(timer.sequenceId as string)}
              accessibilityRole="button"
              accessibilityLabel="Confirmar paso de la cadena"
              hitSlop={ACTION_HIT_SLOP}
            >
              <MaterialIcons name="done-all" size={ICON_SIDE} color="#B8DAFF" />
            </Pressable>
          ) : null}
          <Pressable
            style={({ pressed }) => [
              styles.btnPrimary,
              status === 'running' ? styles.btnPrimaryPause : styles.btnPrimaryPlay,
              { opacity: pressed ? buttonPressedOpacity : 1 },
            ]}
            onPress={toggleRun}
            accessibilityRole="button"
            accessibilityLabel={
              status === 'running' ? 'Pausar temporizador' : 'Iniciar o reanudar temporizador'
            }
            hitSlop={ACTION_HIT_SLOP}
          >
            <MaterialIcons
              name={status === 'running' ? 'pause-circle-filled' : 'play-circle-filled'}
              size={ICON_PRIMARY}
              color={status === 'running' ? '#FFECD1' : '#D4F5DE'}
            />
            <Text
              style={[
                styles.btnPrimaryText,
                status === 'running' ? styles.btnPrimaryTextPause : styles.btnPrimaryTextPlay,
              ]}
              numberOfLines={1}
            >
              {primaryLabel}
            </Text>
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.btnIconSquare, styles.btnReset, { opacity: pressed ? buttonPressedOpacity : 1 }]}
            onPress={() => resetTimer(id)}
            accessibilityRole="button"
            accessibilityLabel="Reiniciar temporizador"
            hitSlop={ACTION_HIT_SLOP}
          >
            <MaterialIcons name="replay" size={ICON_SIDE} color="#C8CED8" />
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.btnIconSquare, styles.btnDelete, { opacity: pressed ? buttonPressedOpacity : 1 }]}
            onPress={confirmRemove}
            accessibilityRole="button"
            accessibilityLabel="Eliminar temporizador"
            hitSlop={ACTION_HIT_SLOP}
          >
            <MaterialIcons name="delete-outline" size={ICON_SIDE} color={DANGER} />
          </Pressable>
        </View>
      );
    }

    return null;
  };

  return (
    <View style={styles.cardRow}>
      <View
        style={[
          styles.card,
          {
            backgroundColor,
            borderColor,
            borderWidth,
            borderStyle,
          },
        ]}
      >
        <Animated.View style={{ opacity: isFinishedAlert || isWaitingAck ? pulseAnim : 1 }}>
          <View style={styles.cardBody}>
            <View style={styles.topRow}>
              <View style={styles.leftTimeWrap}>
                <Pressable onPress={onTimePress} hitSlop={12}>
                  <Animated.Text
                    style={[
                      styles.time,
                      {
                        fontSize: timeSize,
                        color: timeColor,
                        transform: [{ scale: bumpAnim }],
                      },
                    ]}
                  >
                    {formatTime(liveRemainingSeconds)}
                  </Animated.Text>
                </Pressable>
              </View>
              <View style={styles.centerNameWrap}>
                <Pressable
                  onPress={openNameEditor}
                  accessibilityRole="button"
                  accessibilityLabel={
                    isFinishedAlert
                      ? `${isTimerNameEmpty(name) ? 'Temporizador' : name.trim()} listo. Cambiar nombre del temporizador`
                      : `${isTimerNameEmpty(name) ? 'Sin nombre' : name.trim()}. Cambiar nombre del temporizador`
                  }
                  accessibilityHint="Abre el editor para poner un nombre que reconozcas en cocina"
                  hitSlop={{ top: 10, bottom: 8, left: 8, right: 8 }}
                  style={({ pressed }) => [
                    styles.namePressable,
                    pressed && styles.namePressablePressed,
                  ]}
                >
                  <View style={styles.nameRow}>
                    {hasSequence ? (
                      <View style={styles.stepBadgeCompact}>
                        <MaterialIcons name="format-list-numbered" size={12} color="#9AA3B0" />
                        <Text style={styles.stepBadgeCompactText}>{`${currentStepNumber}/${totalSteps}`}</Text>
                      </View>
                    ) : null}
                    <Text
                      style={[
                        styles.name,
                        { fontSize: compact ? 15 : 17 },
                        !isFinishedAlert && isTimerNameEmpty(name)
                          ? styles.namePlaceholder
                          : { color: nameColor },
                      ]}
                      numberOfLines={1}
                    >
                      {isFinishedAlert
                        ? isTimerNameEmpty(name)
                          ? 'Temporizador listo'
                          : `${name.trim()} listo`
                        : timerNameForDisplay(name)}
                    </Text>
                    <MaterialIcons
                      name="edit"
                      size={compact ? 17 : 19}
                      color="#8EC6FF"
                      style={styles.nameEditIcon}
                    />
                  </View>
                </Pressable>
              </View>
            </View>
            {renderActionRow()}
          </View>
        </Animated.View>
      </View>
      <PromptModal
        visible={prompt !== null}
        title="Nombre del temporizador"
        inputPlaceholder="Opcional · vacío = sin nombre"
        initialValue={prompt?.kind === 'name' ? prompt.current : name}
        onCancel={() => setPrompt(null)}
        onSubmit={(text) => {
          const trimmed = text.trim();
          if (prompt?.kind === 'name') {
            setTimerName(id, trimmed);
          }
          setPrompt(null);
        }}
      />
      <DurationPickerModal
        visible={durationOpen}
        initialSeconds={durationInitialSeconds}
        onCancel={() => setDurationOpen(false)}
        onConfirm={(seconds) => {
          setDurationOpen(false);
          setTimerDuration(id, seconds);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  cardRow: {
    marginBottom: 0,
  },
  card: {
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    justifyContent: 'center',
    width: '100%',
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  cardBody: {
    gap: 10,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: 8,
  },
  leftTimeWrap: {
    width: 108,
    alignItems: 'flex-start',
    justifyContent: 'center',
    flexShrink: 0,
  },
  centerNameWrap: {
    flexShrink: 1,
    maxWidth: NAME_MAX_WIDTH,
    minWidth: 0,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  namePressable: {
    alignSelf: 'flex-start',
    maxWidth: NAME_MAX_WIDTH,
    alignItems: 'flex-start',
    justifyContent: 'center',
    minHeight: 40,
    paddingVertical: 2,
  },
  namePressablePressed: {
    opacity: 0.88,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    justifyContent: 'flex-start',
    minWidth: 0,
    maxWidth: '100%',
    flexShrink: 1,
  },
  nameEditIcon: {
    flexShrink: 0,
    opacity: 0.95,
  },
  name: {
    fontFamily: Font.sansSemiBold,
    letterSpacing: 0.15,
    color: TEXT_PRIMARY,
    flexShrink: 1,
    flexGrow: 0,
  },
  namePlaceholder: {
    color: 'rgba(209, 214, 222, 0.38)',
    letterSpacing: 0.35,
  },
  stepBadgeCompact: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    backgroundColor: '#252830',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#3A4049',
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  stepBadgeCompactText: {
    fontFamily: Font.sansBold,
    color: '#B4BCC8',
    fontSize: 10,
    letterSpacing: 0.2,
  },
  time: {
    fontFamily: Font.monoBold,
    letterSpacing: 0.3,
    marginVertical: 0,
    minWidth: 96,
    textAlign: 'left',
    fontVariant: ['tabular-nums'],
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minHeight: 52,
  },
  actionRowEnd: {
    justifyContent: 'flex-end',
  },
  btnPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    minHeight: 52,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 2,
  },
  btnPrimaryPlay: {
    backgroundColor: 'rgba(48, 209, 88, 0.2)',
    borderColor: SUCCESS,
  },
  btnPrimaryPause: {
    backgroundColor: 'rgba(255, 159, 10, 0.2)',
    borderColor: WARNING,
  },
  btnPrimaryText: {
    fontFamily: Font.sansBold,
    fontSize: 16,
    letterSpacing: 0.3,
  },
  btnPrimaryTextPlay: {
    color: '#D4F5DE',
  },
  btnPrimaryTextPause: {
    color: '#FFECD1',
  },
  btnIconSquare: {
    width: 52,
    minHeight: 52,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 2,
  },
  btnReset: {
    backgroundColor: '#1E2228',
    borderColor: '#4A5563',
  },
  btnDelete: {
    backgroundColor: 'rgba(255, 59, 48, 0.12)',
    borderColor: DANGER,
  },
  btnAck: {
    backgroundColor: 'rgba(10, 132, 255, 0.22)',
    borderColor: '#0A84FF',
  },
  btnOkFull: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    minHeight: 52,
    borderRadius: 12,
    borderWidth: 2,
    backgroundColor: 'rgba(48, 209, 88, 0.22)',
    borderColor: SUCCESS,
  },
  btnOkFullText: {
    fontFamily: Font.sansBold,
    color: '#E8FFF0',
    fontSize: 16,
    letterSpacing: 0.35,
  },
});
