"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { RefObject } from "react";

interface ScrollProgressProps {
  containerRef: RefObject<HTMLElement | null>;
}

export function ScrollProgress({ containerRef }: ScrollProgressProps) {
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  const dotTop = useTransform(scrollYProgress, (v) => `${v * 100}%`);
  const glowIntensity = useTransform(scrollYProgress, (v) =>
    `0 0 8px rgba(0,212,255,${0.3 + v * 0.4}), 0 0 20px rgba(0,212,255,${0.1 + v * 0.2})`
  );

  return (
    <div className="pointer-events-none fixed left-0 top-0 z-50 h-full w-[3px]">
      {/* Track */}
      <div className="absolute inset-0 bg-white/[0.03]" />

      {/* Progress fill */}
      <motion.div
        className="absolute left-0 top-0 w-full origin-top"
        style={{
          scaleY: scrollYProgress,
          background:
            "linear-gradient(to bottom, rgba(0,212,255,0.8), rgba(0,212,255,0.3))",
          boxShadow: glowIntensity,
          height: "100%",
        }}
      />

      {/* Moving dot at progress tip — larger with glow */}
      <motion.div
        className="absolute left-1/2 h-2 w-2 -translate-x-1/2 rounded-full"
        style={{
          top: dotTop,
          background: "rgba(0,212,255,1)",
          boxShadow: "0 0 8px rgba(0,212,255,0.8), 0 0 16px rgba(0,212,255,0.4)",
        }}
      />

      {/* Trailing glow behind dot */}
      <motion.div
        className="absolute left-1/2 h-8 w-1 -translate-x-1/2 rounded-full blur-sm"
        style={{
          top: dotTop,
          background: "linear-gradient(to top, rgba(0,212,255,0.4), transparent)",
          transform: "translateX(-50%) translateY(-100%)",
        }}
      />
    </div>
  );
}
