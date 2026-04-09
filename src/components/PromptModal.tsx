import React, { useEffect, useRef, useState } from 'react';
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { APP_BACKGROUND, TEXT_PRIMARY } from '../constants/colors';
import { Font } from '../theme/typography';

interface PromptModalProps {
  visible: boolean;
  title: string;
  initialValue: string;
  onCancel: () => void;
  onSubmit: (value: string) => void;
  /** Placeholder del campo (p. ej. indicar que puede quedar vacío). */
  inputPlaceholder?: string;
}

export function PromptModal({
  visible,
  title,
  initialValue,
  onCancel,
  onSubmit,
  inputPlaceholder = '…',
}: PromptModalProps) {
  const [value, setValue] = useState(initialValue);
  const inputRef = useRef<React.ElementRef<typeof TextInput>>(null);

  useEffect(() => {
    if (!visible) return;
    setValue(initialValue);
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const len = initialValue.length;
        inputRef.current?.setSelection(0, len);
      });
    });
    return () => cancelAnimationFrame(id);
  }, [visible, initialValue]);

  const submit = () => {
    onSubmit(value.trim());
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          accessibilityRole="button"
          accessibilityLabel="Guardar y cerrar"
          onPress={submit}
        />
        <View style={styles.box}>
          <Text style={styles.title}>{title}</Text>
          <TextInput
            ref={inputRef}
            value={value}
            onChangeText={setValue}
            style={styles.input}
            autoFocus
            selectTextOnFocus
            placeholderTextColor="#888"
            placeholder={inputPlaceholder}
            returnKeyType="done"
            blurOnSubmit
            onSubmitEditing={submit}
          />
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
  },
  input: {
    borderWidth: 1,
    borderColor: '#444',
    borderRadius: 8,
    color: TEXT_PRIMARY,
    fontFamily: Font.sansRegular,
    fontSize: 16,
    padding: 12,
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
  },
  btn: {
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  btnPrimary: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
  },
  btnText: {
    fontFamily: Font.sansSemiBold,
    color: TEXT_PRIMARY,
    fontSize: 16,
  },
});
