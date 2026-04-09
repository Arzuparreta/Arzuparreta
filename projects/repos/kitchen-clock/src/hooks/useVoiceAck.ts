import { useEffect, useRef, useState } from 'react';
import { useTimerStore } from '../store/timerStore';

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onresult: ((event: { results?: ArrayLike<ArrayLike<{ transcript?: string }>> }) => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function normalizeTranscript(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

function hasAckKeyword(input: string): boolean {
  const normalized = normalizeTranscript(input);
  return normalized.includes('oido') || normalized.includes('siguiente');
}

export function useVoiceAck() {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const ackHighestPriorityWaiting = useTimerStore((s) => s.ackHighestPriorityWaiting);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const shouldRestartRef = useRef(true);
  const lastTriggerRef = useRef(0);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const maybeWindow = window as typeof globalThis & {
      SpeechRecognition?: SpeechRecognitionCtor;
      webkitSpeechRecognition?: SpeechRecognitionCtor;
    };
    const SpeechRecognition =
      maybeWindow.SpeechRecognition ?? maybeWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    setIsSupported(true);
    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'es-ES';
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onend = () => {
      setIsListening(false);
      if (!shouldRestartRef.current) return;
      try {
        recognition.start();
      } catch {
        // Browser may reject immediate restart; onend will fire again.
      }
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onresult = (event) => {
      const now = Date.now();
      if (now - lastTriggerRef.current < 1200) return;
      const results = event.results;
      if (!results || results.length === 0) return;
      const lastResult = results[results.length - 1];
      const candidate = lastResult?.[0]?.transcript ?? '';
      if (!hasAckKeyword(candidate)) return;
      const targetSequenceId = useTimerStore
        .getState()
        .sequences.find((sequence) => sequence.status === 'waiting_ack')?.id;
      if (!targetSequenceId) return;
      lastTriggerRef.current = now;
      ackHighestPriorityWaiting();
    };

    try {
      recognition.start();
    } catch {
      setIsListening(false);
    }

    return () => {
      shouldRestartRef.current = false;
      recognition.onstart = null;
      recognition.onend = null;
      recognition.onerror = null;
      recognition.onresult = null;
      try {
        recognition.stop();
      } catch {
        // no-op
      }
      recognitionRef.current = null;
    };
  }, [ackHighestPriorityWaiting]);

  return {
    isListening,
    isSupported,
  };
}
