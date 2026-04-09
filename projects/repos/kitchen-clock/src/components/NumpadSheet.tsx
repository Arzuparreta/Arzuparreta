import React, { useEffect, useState } from 'react';
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { APP_BACKGROUND, SUCCESS, TEXT_PRIMARY } from '../constants/colors';
import { formatTime } from '../utils/timeFormat';

const KEY_MIN = 80;

function digitsToTotalSeconds(digits: number[]): number {
  const str = digits.join('').padStart(6, '0');
  const hh = parseInt(str.slice(0, 2), 10) || 0;
  const mm = parseInt(str.slice(2, 4), 10) || 0;
  const ss = parseInt(str.slice(4, 6), 10) || 0;
  return hh * 3600 + mm * 60 + ss;
}

interface NumpadSheetProps {
  visible: boolean;
  onClose: () => void;
  onConfirm: (totalSeconds: number) => void;
}

export function NumpadSheet({ visible, onClose, onConfirm }: NumpadSheetProps) {
  const [digits, setDigits] = useState<number[]>([]);

  useEffect(() => {
    if (visible) setDigits([]);
  }, [visible]);

  const displaySeconds = digitsToTotalSeconds(digits);
  const displayText = formatTime(displaySeconds);

  const pushDigit = (d: number) => {
    setDigits((prev) => (prev.length >= 6 ? prev : [...prev, d]));
  };

  const backspace = () => {
    setDigits((prev) => prev.slice(0, -1));
  };

  const confirm = () => {
    onConfirm(digitsToTotalSeconds(digits));
    onClose();
  };

  const row = (a: number, b: number, c: number) => (
    <View style={styles.row}>
      <Pressable style={styles.key} onPress={() => pushDigit(a)}>
        <Text style={styles.keyText}>{a}</Text>
      </Pressable>
      <Pressable style={styles.key} onPress={() => pushDigit(b)}>
        <Text style={styles.keyText}>{b}</Text>
      </Pressable>
      <Pressable style={styles.key} onPress={() => pushDigit(c)}>
        <Text style={styles.keyText}>{c}</Text>
      </Pressable>
    </View>
  );

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <Pressable style={styles.fill} onPress={onClose} />
        <View style={styles.sheet}>
          <Text style={styles.display}>{displayText}</Text>
          {row(1, 2, 3)}
          {row(4, 5, 6)}
          {row(7, 8, 9)}
          <View style={styles.row}>
            <Pressable style={styles.key} onPress={backspace}>
              <Text style={styles.keyText}>⌫</Text>
            </Pressable>
            <Pressable style={styles.key} onPress={() => pushDigit(0)}>
              <Text style={styles.keyText}>0</Text>
            </Pressable>
            <Pressable style={[styles.key, styles.keyConfirm]} onPress={confirm}>
              <Text style={styles.keyConfirmText}>✓</Text>
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
    backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'flex-end',
  },
  fill: {
    flex: 1,
  },
  sheet: {
    backgroundColor: APP_BACKGROUND,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingTop: 20,
    paddingHorizontal: 20,
    paddingBottom: 28,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderColor: '#2C2C2E',
  },
  display: {
    color: TEXT_PRIMARY,
    fontSize: 44,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 20,
    fontVariant: ['tabular-nums'],
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginBottom: 12,
  },
  key: {
    minWidth: KEY_MIN,
    minHeight: KEY_MIN,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.12)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  keyText: {
    color: TEXT_PRIMARY,
    fontSize: 28,
    fontWeight: '600',
  },
  keyConfirm: {
    backgroundColor: SUCCESS,
  },
  keyConfirmText: {
    color: '#000',
    fontSize: 36,
    fontWeight: '800',
  },
});
