import { useCallback, useEffect, useRef, useState } from "react";
import cashUrl from "../assets/sounds/cash-register.mp3";
import rainUrl from "../assets/sounds/money-rain.mp3";

export const SOUND_URLS = { cash: cashUrl, rain: rainUrl } as const;
export type SoundKind = keyof typeof SOUND_URLS;

const GAP_MS = 1300; // intervalo entre sons quando várias vendas chegam juntas
const MAX_PER_BATCH = 5; // evita uma sequência longa depois de uma reconexão

/** Venda abaixo do corte = caixa registradora; a partir do corte = chuva de dinheiro. */
export function soundFor(valueC: number, thresholdC: number): SoundKind {
  return valueC >= thresholdC ? "rain" : "cash";
}

export function playOnce(kind: SoundKind, volume: number): Promise<void> {
  const audio = new Audio(SOUND_URLS[kind]);
  audio.volume = Math.max(0, Math.min(1, volume));
  return audio.play();
}

function audioLikelyBlocked(): boolean {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return false;
    const ctx = new Ctx();
    const blocked = ctx.state === "suspended";
    void ctx.close();
    return blocked;
  } catch {
    return false;
  }
}

/**
 * Toca os sons das vendas novas. Navegadores bloqueiam áudio até a primeira interação com a
 * página (exceto quiosques com autoplay liberado, como o Fully Kiosk). Quando bloqueado,
 * `blocked` fica true e a TV pede para apertar OK no controle uma vez.
 */
export function useSaleSounds(enabled: boolean, volume: number) {
  const [blocked, setBlocked] = useState(false);
  const volumeRef = useRef(volume);
  volumeRef.current = volume;

  useEffect(() => {
    if (enabled && audioLikelyBlocked()) setBlocked(true);
    const unlock = () => {
      setBlocked((wasBlocked) => {
        // Toca dentro do próprio gesto: é isso que libera o áudio no navegador
        if (wasBlocked) void playOnce("cash", volumeRef.current).catch(() => undefined);
        return false;
      });
    };
    window.addEventListener("keydown", unlock);
    window.addEventListener("pointerdown", unlock);
    return () => {
      window.removeEventListener("keydown", unlock);
      window.removeEventListener("pointerdown", unlock);
    };
  }, [enabled]);

  const play = useCallback((kinds: SoundKind[]) => {
    kinds.slice(0, MAX_PER_BATCH).forEach((kind, i) => {
      window.setTimeout(() => {
        playOnce(kind, volumeRef.current).catch((e: unknown) => {
          if (e instanceof DOMException && e.name === "NotAllowedError") setBlocked(true);
        });
      }, i * GAP_MS);
    });
  }, []);

  return { blocked, play };
}
