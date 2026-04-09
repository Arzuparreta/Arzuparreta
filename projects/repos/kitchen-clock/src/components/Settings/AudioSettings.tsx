import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { TEXT_PRIMARY, TEXT_SECONDARY } from '../../constants/colors';
import { Font } from '../../theme/typography';
import { testAudioPreset } from '../../hooks/useAudioAlerts';
import { AUDIO_PRESETS, resolveAudioConfig, useTimerStore } from '../../store/timerStore';

export function AudioSettings() {
  const audioConfig = useTimerStore((s) => s.audioConfig);
  const updateAudioConfig = useTimerStore((s) => s.updateAudioConfig);
  const resolvedConfig = React.useMemo(() => resolveAudioConfig(audioConfig), [audioConfig]);
  const presets = React.useMemo(() => Object.values(AUDIO_PRESETS), []);

  return (
    <View style={styles.root}>
      <Text style={styles.sectionTitle}>Ajustes de alarma</Text>
      <View style={styles.presetList}>
        {presets.map((preset) => {
          const isSelected = preset.id === resolvedConfig.presetId;
          return (
            <View
              key={preset.id}
              style={[styles.presetRow, isSelected && styles.presetRowSelected]}
            >
              <Pressable
                style={styles.presetMain}
                onPress={() => updateAudioConfig({ presetId: preset.id })}
              >
                <Text style={[styles.presetTitle, isSelected && styles.presetTitleSelected]}>
                  {preset.label}
                </Text>
                <Text style={styles.presetDescription}>{preset.description}</Text>
              </Pressable>
              <Pressable
                style={styles.presetTryBtn}
                hitSlop={{ top: 10, bottom: 10, left: 6, right: 10 }}
                onPress={() => void testAudioPreset(preset.id)}
                accessibilityLabel={`Probar sonido ${preset.label}`}
              >
                <Text style={styles.presetTryBtnText}>Probar</Text>
              </Pressable>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    gap: 12,
  },
  sectionTitle: {
    fontFamily: Font.sansSemiBold,
    fontSize: 17,
    letterSpacing: 0.2,
    color: TEXT_PRIMARY,
  },
  presetList: {
    gap: 8,
  },
  presetRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    gap: 0,
    borderWidth: 1,
    borderColor: '#2E3238',
    borderRadius: 10,
    backgroundColor: '#121315',
    overflow: 'hidden',
  },
  presetRowSelected: {
    borderColor: '#007AFF',
    backgroundColor: 'rgba(0, 122, 255, 0.18)',
  },
  presetMain: {
    flex: 1,
    paddingHorizontal: 12,
    paddingVertical: 12,
    gap: 4,
    minHeight: 72,
    justifyContent: 'center',
  },
  presetTryBtn: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 14,
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: '#2C3036',
    backgroundColor: '#16181C',
    minWidth: 84,
  },
  presetTryBtnText: {
    fontFamily: Font.sansBold,
    color: '#007AFF',
    fontSize: 15,
  },
  presetTitle: {
    fontFamily: Font.sansBold,
    color: TEXT_PRIMARY,
    fontSize: 16,
    letterSpacing: 0.15,
  },
  presetTitleSelected: {
    color: '#E8F1FF',
  },
  presetDescription: {
    fontFamily: Font.sansRegular,
    color: TEXT_SECONDARY,
    fontSize: 13,
  },
});
