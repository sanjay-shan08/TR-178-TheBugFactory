/**
 * VoiceBot — Continuous live voice assistant for FloorSense AI.
 *
 * Uses the browser's SpeechRecognition API (no recording, no backend call,
 * no "thinking" delay). Recognition runs continuously; commands are matched
 * the moment the user finishes speaking a phrase.
 *
 * Speaks back via speechSynthesis so visually impaired users hear confirmation.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ── Command intent map ────────────────────────────────────────────────────────
const COMMANDS = [
  {
    patterns: [/run pipeline|analyze|analyse|scan|process|start/],
    action:  'run_pipeline',
    reply:   'Starting floor plan analysis.',
  },
  {
    patterns: [/live nav|navigation|camera|live/],
    action:  'switch_to_livenav',
    reply:   'Switching to live navigation.',
  },
  {
    patterns: [/floor plan|home|back|upload/],
    action:  'switch_to_floorplan',
    reply:   'Going to the floor plan screen.',
  },
  {
    patterns: [/play.*audio|audio guide|read.*map|describe|narrate/],
    action:  'play_audio_guide',
    reply:   'Playing the audio guide.',
  },
  {
    patterns: [/stop.*speak|quiet|silence|shut up/],
    action:  'stop_audio',
    reply:   null,
  },
  {
    patterns: [/new floor|reset|clear|start over/],
    action:  'reset',
    reply:   'Resetting. Ready for a new floor plan.',
  },
  {
    patterns: [/tactile|map|visual/],
    action:  'show_tactile',
    reply:   'Showing tactile map.',
  },
  {
    patterns: [/screen reader|accessible|aria/],
    action:  'show_screen_reader',
    reply:   'Showing screen reader view.',
  },
  {
    patterns: [/help|what can (you|i)|commands/],
    action:  'help',
    reply:   'Available commands: analyze floor plan, live navigation, play audio guide, '
           + 'show tactile map, show screen reader, reset, and stop speaking.',
  },
];

// ── Speak helper ──────────────────────────────────────────────────────────────
function speak(text, rate = 1.0) {
  if (!text || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang  = 'en-US';
  utt.rate  = rate;
  utt.pitch = 1.05;
  window.speechSynthesis.speak(utt);
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function VoiceBot({ onCommand }) {
  const [listening,  setListening]  = useState(false);
  const [transcript, setTranscript] = useState('');
  const [lastCmd,    setLastCmd]    = useState('');
  const [supported,  setSupported]  = useState(true);

  const recogRef   = useRef(null);
  const activeRef  = useRef(false);
  const restartRef = useRef(null);

  const matchCommand = useCallback((text) => {
    const lower = text.toLowerCase();
    for (const cmd of COMMANDS) {
      for (const pat of cmd.patterns) {
        const matched = typeof pat === 'string'
          ? lower.includes(pat)
          : pat.test(lower);
        if (matched) return cmd;
      }
    }
    return null;
  }, []);

  const startListening = useCallback(() => {
    if (activeRef.current) return;

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setSupported(false); return; }

    const recog = new SR();
    recog.continuous      = true;
    recog.interimResults  = false;
    recog.lang            = 'en-US';
    recog.maxAlternatives = 1;

    recog.onstart = () => {
      activeRef.current = true;
      setListening(true);
    };

    recog.onend = () => {
      activeRef.current = false;
      setListening(false);
      if (!document.hidden) {
        restartRef.current = setTimeout(startListening, 400);
      }
    };

    recog.onerror = (e) => {
      if (e.error !== 'no-speech') {
        console.warn('[VoiceBot] SpeechRecognition error:', e.error);
      }
      activeRef.current = false;
      setListening(false);
    };

    recog.onresult = (e) => {
      const phrase = e.results[e.results.length - 1][0].transcript.trim();
      setTranscript(phrase);

      const cmd = matchCommand(phrase);
      if (cmd) {
        setLastCmd(cmd.action);
        if (cmd.reply) speak(cmd.reply);
        if (onCommand) onCommand(cmd.action, phrase);
      }
    };

    recogRef.current = recog;
    try {
      recog.start();
    } catch (_) {}
  }, [matchCommand, onCommand]);

  useEffect(() => {
    setTimeout(() => {
      speak('FloorSense AI is ready. Say "help" to hear available voice commands.', 0.95);
    }, 800);
    startListening();

    return () => {
      clearTimeout(restartRef.current);
      recogRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, [startListening]);

  // Pause recognition while the app is speaking to avoid feedback loop
  useEffect(() => {
    const onSpeak = () => recogRef.current?.stop();

    window.speechSynthesis?.addEventListener?.('start', onSpeak);
    return () => {
      window.speechSynthesis?.removeEventListener?.('start', onSpeak);
    };
  }, [startListening]);

  if (!supported) return null;

  return (
    <div
      aria-live="polite"
      aria-label="Voice assistant status"
      style={{
        position:    'fixed',
        bottom:      '24px',
        right:       '24px',
        zIndex:      9999,
        display:     'flex',
        flexDirection: 'column',
        alignItems:  'center',
        gap:         '6px',
        pointerEvents: 'none',
      }}
    >
      {transcript && (
        <div style={{
          background:   'rgba(0,0,0,0.75)',
          color:        '#fff',
          padding:      '6px 12px',
          borderRadius: '999px',
          fontSize:     '0.78rem',
          maxWidth:     '220px',
          textAlign:    'center',
          backdropFilter: 'blur(4px)',
        }}>
          "{transcript}"
        </div>
      )}

      {lastCmd && (
        <div style={{
          background:   '#3b82f6',
          color:        '#fff',
          padding:      '3px 10px',
          borderRadius: '999px',
          fontSize:     '0.72rem',
        }}>
          ✓ {lastCmd.replace(/_/g, ' ')}
        </div>
      )}

      <div
        title={listening ? 'Listening…' : 'Voice assistant'}
        style={{
          width:        '56px',
          height:       '56px',
          borderRadius: '50%',
          background:   listening ? '#22c55e' : '#475569',
          display:      'flex',
          alignItems:   'center',
          justifyContent: 'center',
          fontSize:     '26px',
          boxShadow:    listening
            ? '0 0 0 6px rgba(34,197,94,0.25), 0 4px 16px rgba(0,0,0,0.4)'
            : '0 4px 12px rgba(0,0,0,0.35)',
          transition:   'all 0.3s ease',
          animation:    listening ? 'pulse 1.8s infinite' : 'none',
        }}
      >
        {listening ? '🎙️' : '🔇'}
      </div>

      <style>{`
        @keyframes pulse {
          0%   { box-shadow: 0 0 0 0   rgba(34,197,94,0.5), 0 4px 16px rgba(0,0,0,0.4); }
          70%  { box-shadow: 0 0 0 12px rgba(34,197,94,0),   0 4px 16px rgba(0,0,0,0.4); }
          100% { box-shadow: 0 0 0 0   rgba(34,197,94,0),   0 4px 16px rgba(0,0,0,0.4); }
        }
      `}</style>
    </div>
  );
}
