"use client";

import { useTransform, MotionValue } from "framer-motion";

const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=[]{}|;:,.<>?/~`█▓▒░";

function scrambleText(target: string, revealFraction: number): string {
  const chars = target.split("");
  const revealCount = Math.floor(chars.length * revealFraction);

  return chars
    .map((char, i) => {
      if (char === " ") return " ";
      if (i < revealCount) return char;
      // Use deterministic pseudo-random based on char index and fraction
      const seed = (i * 7 + Math.floor(revealFraction * 100)) % CHARS.length;
      return CHARS[seed];
    })
    .join("");
}

export function useHackerText(
  progress: MotionValue<number>,
  lines: string[],
  stagger: number = 0.2
) {
  const outputs = lines.map((line, lineIndex) => {
    const lineStart = lineIndex * stagger;
    const lineEnd = lineStart + stagger + 0.1;

    return useTransform(progress, (p: number) => {
      const clampedStart = Math.min(lineStart, 1);
      const clampedEnd = Math.min(lineEnd, 1);

      if (p <= clampedStart) return scrambleText(line, 0);
      if (p >= clampedEnd) return line;

      const fraction = (p - clampedStart) / (clampedEnd - clampedStart);
      return scrambleText(line, fraction);
    });
  });

  return outputs;
}
