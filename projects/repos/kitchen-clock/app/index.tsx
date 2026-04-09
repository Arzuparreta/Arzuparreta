import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useKeepAwake } from 'expo-keep-awake';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActionSheetIOS,
  Alert,
  Animated,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { AudioSettings } from '../src/components/Settings/AudioSettings';
import { TimerCard } from '../src/components/TimerCard';
import { APP_BACKGROUND, TEXT_PRIMARY, TEXT_SECONDARY } from '../src/constants/colors';
import { Font } from '../src/theme/typography';
import { useAudioAlerts } from '../src/hooks/useAudioAlerts';
import { useBackgroundSync } from '../src/hooks/useBackgroundSync';
import { useNotifications } from '../src/hooks/useNotifications';
import { useProximityAck } from '../src/hooks/useProximityAck';
import { useTimerTick } from '../src/hooks/useTimerTick';
import { useVoiceAck } from '../src/hooks/useVoiceAck';
import { useWakeLock } from '../src/hooks/useWakeLock';
import { useTimerStore } from '../src/store/timerStore';
type ViewMode = 'service' | 'settings';

export default function MainScreen() {
  useKeepAwake();
  useWakeLock();
  useTimerTick();
  useNotifications();
  useBackgroundSync();
  useAudioAlerts();

  const insets = useSafeAreaInsets();
  const timers = useTimerStore((s) => s.timers);
  const sequences = useTimerStore((s) => s.sequences);
  const addTimer = useTimerStore((s) => s.addTimer);
  const addSequence = useTimerStore((s) => s.addSequence);
  const startSequence = useTimerStore((s) => s.startSequence);
  const ackHighestPriorityWaiting = useTimerStore((s) => s.ackHighestPriorityWaiting);
  const clearAllTimers = useTimerStore((s) => s.clearAllTimers);
  const { isListening, isSupported: isVoiceSupported } = useVoiceAck();
  const { isSupported: isProximitySupported, mode: proximityMode } = useProximityAck();
  const flashOpacity = React.useRef(new Animated.Value(0)).current;

  const [viewMode, setViewMode] = useState<ViewMode>('service');
  const hasCriticalAlert = useMemo(() => {
    return timers.some((timer) => {
      if (timer.alertLevel !== 'critical') return false;
      if (timer.status === 'finished' && !timer.alertDismissed) return true;
      if (!timer.sequenceId) return false;
      const sequence = sequences.find((s) => s.id === timer.sequenceId);
      return sequence?.status === 'waiting_ack';
    });
  }, [timers, sequences]);

  useEffect(() => {
    if (!hasCriticalAlert) {
      flashOpacity.stopAnimation();
      flashOpacity.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(flashOpacity, { toValue: 0.2, duration: 220, useNativeDriver: true }),
        Animated.timing(flashOpacity, { toValue: 0, duration: 340, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => {
      loop.stop();
      flashOpacity.setValue(0);
    };
  }, [hasCriticalAlert, flashOpacity]);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    if (typeof window === 'undefined' || typeof window.addEventListener !== 'function') return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code !== 'Space') return;
      const target = event.target as HTMLElement | null;
      const targetTag = target?.tagName?.toLowerCase();
      if (
        targetTag === 'input' ||
        targetTag === 'textarea' ||
        (target as { isContentEditable?: boolean } | null)?.isContentEditable
      ) {
        return;
      }
      event.preventDefault();
      ackHighestPriorityWaiting();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      if (typeof window.removeEventListener === 'function') {
        window.removeEventListener('keydown', onKeyDown);
      }
    };
  }, [ackHighestPriorityWaiting]);

  const serviceContent =
    timers.length === 0 ? (
      <View style={styles.empty}>
        <Text style={styles.emptyIcon}>⏱</Text>
        <Text style={styles.emptyText}>
          <Text style={styles.emptyTextBold}>Pulsa +</Text> para <Text style={styles.emptyTextBold}>Añadir</Text>{' '}
          un Temporizador{'\n'}
          <Text style={styles.emptyTextBold}>Mantén +</Text> para <Text style={styles.emptyTextBold}>Opciones</Text>{' '}
          de Temporizador
        </Text>
      </View>
    ) : (
      <ScrollView style={styles.timerList} contentContainerStyle={styles.grid}>
        {timers.map((timer) => (
          <View key={timer.id} style={styles.timerRowWrap}>
            <TimerCard timer={timer} compact />
          </View>
        ))}
      </ScrollView>
    );

  const onQuickAddTimer = () => {
    addTimer({
      name: `Timer ${timers.length + 1}`,
      totalSeconds: 0,
      color: '#007AFF',
      startRunning: false,
    });
  };

  const onQuickAddChain = (stepsCount: number) => {
    const normalized = Math.max(2, Math.min(8, Math.floor(stepsCount)));
    const sequence = addSequence({
      name: `Cadena ${sequences.length + 1}`,
      color: '#007AFF',
      steps: Array.from({ length: normalized }, (_, idx) => ({
        name: `Paso ${idx + 1}`,
        durationSeconds: 5 * 60,
        autostart: true,
        alertLevel: 'medium' as const,
      })),
    });
    startSequence(sequence.id);
  };

  const openChainCountMenu = () => {
    const counts = [2, 3, 4, 5, 6, 7, 8];
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          title: 'Cadena de contadores',
          options: [...counts.map((value) => `${value} contadores`), 'Cancelar'],
          cancelButtonIndex: counts.length,
        },
        (index) => {
          if (index < 0 || index >= counts.length) return;
          onQuickAddChain(counts[index] as number);
        }
      );
      return;
    }
    Alert.alert(
      'Cadena de contadores',
      'Selecciona cuantos contadores quieres crear',
      [
        ...counts.map((value) => ({
          text: `${value} contadores`,
          onPress: () => onQuickAddChain(value),
        })),
        { text: 'Cancelar', style: 'cancel' },
      ]
    );
  };

  const hasTimersOrSequences = timers.length > 0 || sequences.length > 0;

  const onClearAllTimers = () => {
    if (!hasTimersOrSequences) return;
    const confirm = () => clearAllTimers();
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          title: 'Se eliminarán todos los temporizadores y cadenas.',
          options: ['Borrar todo', 'Cancelar'],
          destructiveButtonIndex: 0,
          cancelButtonIndex: 1,
        },
        (index) => {
          if (index === 0) confirm();
        }
      );
      return;
    }
    Alert.alert(
      'Borrar temporizadores',
      '¿Eliminar todos los temporizadores y cadenas?',
      [
        { text: 'Cancelar', style: 'cancel' },
        { text: 'Borrar todo', style: 'destructive', onPress: confirm },
      ]
    );
  };

  const goBackFromSettings = useCallback(() => {
    setViewMode('service');
  }, []);

  const settingsPanResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponderCapture: (_, g) =>
          g.dx > 16 && g.dx > Math.abs(g.dy) * 1.15,
        onPanResponderRelease: (_, g) => {
          if (g.dx > 52) goBackFromSettings();
        },
      }),
    [goBackFromSettings]
  );

  const openAddMenu = () => {
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          title: 'Añadir Temporizador',
          options: ['Simple', 'En cadena', 'Cancelar'],
          cancelButtonIndex: 2,
        },
        (index) => {
          if (index === 0) onQuickAddTimer();
          if (index === 1) openChainCountMenu();
        }
      );
      return;
    }
    Alert.alert('Añadir Temporizador', undefined, [
      { text: 'Simple', onPress: onQuickAddTimer },
      { text: 'En cadena', onPress: openChainCountMenu },
      { text: 'Cancelar', style: 'cancel' },
    ]);
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top, backgroundColor: APP_BACKGROUND }]}>
      <View style={styles.header}>
        <Text style={styles.brand}>
          <Text style={styles.brandInitial}>K</Text>
          <Text style={styles.brandRest}>itchen</Text>
          <Text style={styles.brandInitial}>F</Text>
          <Text style={styles.brandRest}>low</Text>
        </Text>
        <View style={styles.headerActions}>
          {viewMode === 'settings' ? (
            <Pressable
              onPress={goBackFromSettings}
              accessibilityRole="button"
              accessibilityLabel="Volver"
              style={({ pressed }) => [
                styles.modeBtn,
                styles.modeBtnIconOnly,
                pressed && styles.modeBtnPressed,
              ]}
            >
              <Ionicons name="chevron-back" size={24} color={TEXT_PRIMARY} />
            </Pressable>
          ) : null}
          {viewMode === 'service' || hasTimersOrSequences ? (
            <Pressable
              onPress={onClearAllTimers}
              disabled={!hasTimersOrSequences}
              accessibilityRole="button"
              accessibilityLabel="Borrar todos los temporizadores"
              style={({ pressed }) => [
                styles.modeBtn,
                styles.modeBtnIconOnly,
                !hasTimersOrSequences && styles.modeBtnDisabled,
                pressed && hasTimersOrSequences && styles.modeBtnPressed,
              ]}
            >
              <MaterialCommunityIcons name="eraser" size={22} color={TEXT_PRIMARY} />
            </Pressable>
          ) : null}
          <Pressable
            onPress={() => setViewMode((m) => (m === 'settings' ? 'service' : 'settings'))}
            accessibilityRole="button"
            accessibilityLabel={viewMode === 'settings' ? 'Cerrar ajustes' : 'Ajustes'}
            style={[
              styles.modeBtn,
              styles.modeBtnIconOnly,
              viewMode === 'settings' && styles.modeBtnActive,
            ]}
          >
            <Ionicons name="settings-sharp" size={22} color={TEXT_PRIMARY} />
          </Pressable>
        </View>
      </View>

      {isVoiceSupported ? (
        <View style={styles.voicePill}>
          <View style={[styles.voiceDot, isListening ? styles.voiceDotActive : styles.voiceDotInactive]} />
          <Text style={styles.voiceText}>{isListening ? 'Modo Cocina Activo' : 'Micro en espera'}</Text>
        </View>
      ) : null}
      {isProximitySupported ? (
        <View style={styles.sensorPill}>
          <Text style={styles.sensorText}>
            Sensor {proximityMode === 'proximity' ? 'proximidad' : 'luz'} activo
          </Text>
        </View>
      ) : null}
      {viewMode === 'service' ? (
        <>
          {serviceContent}
        </>
      ) : (
        <View style={styles.settingsScreen} {...settingsPanResponder.panHandlers}>
          <ScrollView contentContainerStyle={styles.settingsWrap}>
            <AudioSettings />
          </ScrollView>
        </View>
      )}
      {Platform.OS !== 'web' ? (
        <Pressable
          style={({ pressed }) => [
            styles.fab,
            { bottom: Math.max(insets.bottom, 12) + 12 },
            pressed && styles.pressed,
          ]}
          onPress={onQuickAddTimer}
          onLongPress={openAddMenu}
          delayLongPress={350}
        >
          <Text style={styles.fabText}>+</Text>
        </Pressable>
      ) : null}
      <Animated.View pointerEvents="none" style={[styles.criticalOverlay, { opacity: flashOpacity }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: {
    height: 60,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#2C2C2E',
  },
  brand: {
    color: TEXT_PRIMARY,
  },
  brandInitial: {
    fontFamily: Font.brandBold,
    color: TEXT_PRIMARY,
    fontSize: 22,
    letterSpacing: 0.4,
  },
  brandRest: {
    fontFamily: Font.brandSemiBold,
    color: TEXT_PRIMARY,
    fontSize: 20,
    letterSpacing: 0.35,
  },
  headerActions: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  modeBtn: {
    minHeight: 42,
    borderWidth: 1,
    borderColor: '#3A3A3C',
    borderRadius: 10,
    paddingHorizontal: 10,
    justifyContent: 'center',
  },
  modeBtnIconOnly: {
    width: 42,
    height: 42,
    paddingHorizontal: 0,
    alignItems: 'center',
  },
  modeBtnActive: {
    borderColor: '#007AFF',
    backgroundColor: 'rgba(0,122,255,0.25)',
  },
  modeBtnDisabled: {
    opacity: 0.35,
  },
  modeBtnPressed: {
    opacity: 0.85,
  },
  voicePill: {
    minHeight: 34,
    borderRadius: 17,
    paddingHorizontal: 10,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  voiceDot: {
    width: 9,
    height: 9,
    borderRadius: 5,
  },
  voiceDotActive: {
    backgroundColor: '#34C759',
  },
  voiceDotInactive: {
    backgroundColor: '#8E8E93',
  },
  voiceText: {
    fontFamily: Font.sansSemiBold,
    color: TEXT_PRIMARY,
    fontSize: 12,
  },
  sensorPill: {
    minHeight: 34,
    borderRadius: 17,
    paddingHorizontal: 10,
    backgroundColor: 'rgba(52,199,89,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(52,199,89,0.45)',
    justifyContent: 'center',
  },
  sensorText: {
    fontFamily: Font.sansBold,
    color: '#D7FBD8',
    fontSize: 12,
  },
  pressed: {
    opacity: 0.85,
  },
  timerList: { flex: 1 },
  settingsScreen: { flex: 1 },
  grid: { paddingHorizontal: 12, paddingTop: 10, paddingBottom: 148, gap: 8 },
  timerRowWrap: {
    marginBottom: 8,
  },
  settingsWrap: { padding: 16, paddingBottom: 32, gap: 16 },
  empty: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 20,
  },
  emptyIcon: {
    fontSize: 72,
    marginBottom: 16,
    opacity: 0.35,
  },
  emptyText: {
    fontFamily: Font.sansRegular,
    color: TEXT_SECONDARY,
    fontSize: 15,
    lineHeight: 22,
    textAlign: 'center',
  },
  emptyTextBold: {
    fontFamily: Font.sansBold,
  },
  criticalOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#FF3B30',
  },
  fab: {
    position: 'absolute',
    right: 16,
    width: 70,
    height: 70,
    borderRadius: 35,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    shadowColor: '#000',
    shadowOpacity: 0.35,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  fabText: {
    fontFamily: Font.sansRegular,
    color: '#FFFFFF',
    fontSize: 34,
    marginTop: -3,
  },
});
