import DateTimePicker from '@react-native-community/datetimepicker';
import { Picker } from '@react-native-picker/picker';
import React, { useEffect, useRef, useState } from 'react';
import {
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { APP_BACKGROUND, TEXT_PRIMARY } from '../constants/colors';
import { Font } from '../theme/typography';
import { MAX_TIMER_SECONDS } from '../store/timerStore';
import { secondsFromParts } from '../utils/timeFormat';

interface DurationPickerModalProps {
  visible: boolean;
  initialSeconds: number;
  onCancel: () => void;
  onConfirm: (seconds: number) => void;
}

function secondsToCountdownDate(totalSeconds: number): Date {
  const s = Math.min(MAX_TIMER_SECONDS, Math.max(0, totalSeconds));
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  d.setHours(h, m, sec, 0);
  return d;
}

function dateToSeconds(d: Date): number {
  return Math.min(
    MAX_TIMER_SECONDS,
    Math.max(0, d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds())
  );
}

function splitSeconds(totalSeconds: number): { h: number; m: number; s: number } {
  const s = Math.min(MAX_TIMER_SECONDS, Math.max(0, totalSeconds));
  return {
    h: Math.floor(s / 3600),
    m: Math.floor((s % 3600) / 60),
    s: s % 60,
  };
}

export function DurationPickerModal({
  visible,
  initialSeconds,
  onCancel,
  onConfirm,
}: DurationPickerModalProps) {
  const [iosDate, setIosDate] = useState(() => secondsToCountdownDate(initialSeconds));
  const partsRef = useRef(splitSeconds(initialSeconds));
  const [h, setH] = useState(partsRef.current.h);
  const [m, setM] = useState(partsRef.current.m);
  const [sec, setSec] = useState(partsRef.current.s);

  useEffect(() => {
    if (!visible) return;
    const p = splitSeconds(initialSeconds);
    setIosDate(secondsToCountdownDate(initialSeconds));
    setH(p.h);
    setM(p.m);
    setSec(p.s);
  }, [visible, initialSeconds]);

  const submit = () => {
    if (Platform.OS === 'ios') {
      onConfirm(dateToSeconds(iosDate));
    } else {
      onConfirm(secondsFromParts(h, m, sec));
    }
  };

  const hoursItems = Array.from({ length: 24 }, (_, i) => i);
  const minSecItems = Array.from({ length: 60 }, (_, i) => i);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          accessibilityRole="button"
          accessibilityLabel="Guardar duración"
          onPress={submit}
        />
        <View style={styles.box}>
          <Text style={styles.title}>Duración</Text>
          {Platform.OS === 'ios' ? (
            <DateTimePicker
              value={iosDate}
              mode="countdown"
              display="spinner"
              onChange={(_, date) => {
                if (date) setIosDate(date);
              }}
              themeVariant="dark"
              style={styles.iosPicker}
            />
          ) : (
            <View style={styles.pickerRow}>
              <Picker
                selectedValue={h}
                onValueChange={(v) => setH(Number(v))}
                style={styles.picker}
                itemStyle={styles.pickerItem}
              >
                {hoursItems.map((i) => (
                  <Picker.Item key={`h-${i}`} label={`${i} h`} value={i} color={TEXT_PRIMARY} />
                ))}
              </Picker>
              <Picker
                selectedValue={m}
                onValueChange={(v) => setM(Number(v))}
                style={styles.picker}
                itemStyle={styles.pickerItem}
              >
                {minSecItems.map((i) => (
                  <Picker.Item key={`m-${i}`} label={`${i} min`} value={i} color={TEXT_PRIMARY} />
                ))}
              </Picker>
              <Picker
                selectedValue={sec}
                onValueChange={(v) => setSec(Number(v))}
                style={styles.picker}
                itemStyle={styles.pickerItem}
              >
                {minSecItems.map((i) => (
                  <Picker.Item key={`s-${i}`} label={`${i} s`} value={i} color={TEXT_PRIMARY} />
                ))}
              </Picker>
            </View>
          )}
          <View style={styles.row}>
            <Pressable style={styles.btn} onPress={onCancel}>
              <Text style={styles.btnText}>Cancelar</Text>
            </Pressable>
            <Pressable style={styles.btnPrimary} onPress={submit}>
              <Text style={styles.btnText}>OK</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    padding: 24,
  },
  box: {
    backgroundColor: APP_BACKGROUND,
    borderRadius: 14,
    padding: 20,
    borderWidth: 1,
    borderColor: '#333',
  },
  title: {
    fontFamily: Font.sansSemiBold,
    color: TEXT_PRIMARY,
    fontSize: 17,
    marginBottom: 12,
    textAlign: 'center',
  },
  iosPicker: {
    alignSelf: 'stretch',
    height: 200,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    justifyContent: 'space-between',
    gap: 4,
    minHeight: 200,
  },
  picker: {
    flex: 1,
    color: TEXT_PRIMARY,
  },
  pickerItem: {
    color: TEXT_PRIMARY,
    fontFamily: Font.sansRegular,
    fontSize: 18,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: 16,
  },
  btn: {
    paddingVertical: 14,
    paddingHorizontal: 20,
    minWidth: 100,
    alignItems: 'center',
  },
  btnPrimary: {
    paddingVertical: 14,
    paddingHorizontal: 20,
    minWidth: 100,
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
  },
  btnText: {
    fontFamily: Font.sansSemiBold,
    color: TEXT_PRIMARY,
    fontSize: 16,
  },
});
