"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { RefObject } from "react";
import { ShaderAnimation } from "./shader-animation";
import { Waves } from "./waves";

// Total scroll: 250vh (s1 hero) + 120vh (s2 skeleton) + 150vh (s3 activation) = ~520vh
const TOTAL = 520;
const S1_END = 250 / TOTAL;       // ~0.481
const S2_END = 370 / TOTAL;       // ~0.712

interface BackgroundLayersProps {
  containerRef: RefObject<HTMLElement | null>;
}

export function BackgroundLayers({ containerRef }: BackgroundLayersProps) {
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Shader: fully visible at start, crossfades out as hero text exits
  const shaderOpacity = useTransform(
    scrollYProgress,
    [0, S1_END * 0.5, S1_END],
    [1, 0.8, 0]
  );

  // Waves: fades in during section 1 exit, bridges into section 2, fades out into section 3
  const wavesOpacity = useTransform(
    scrollYProgress,
    [S1_END * 0.3, S1_END * 0.7, S1_END, S2_END, S2_END + 0.1, 1],
    [0, 0.4, 1, 0.8, 0.3, 0]
  );

  // Scanning grid: ramps up in section 2 for surveillance feel
  const gridOpacity = useTransform(
    scrollYProgress,
    [S1_END * 0.5, S1_END, S2_END, 1],
    [0, 0.07, 0.05, 0]
  );

  // Vignette: strong on hero, loosens to let waves breathe, tightens for activation
  const vignetteOpacity = useTransform(
    scrollYProgress,
    [0, S1_END * 0.6, S1_END, S2_END, 1],
    [1, 0.8, 0.4, 0.4, 0.7]
  );

  return (
    <div className="pointer-events-none fixed inset-0 z-0">
      {/* Layer 1: Three.js shader */}
      <motion.div
        className="absolute inset-0"
        style={{ opacity: shaderOpacity }}
      >
        <ShaderAnimation />
      </motion.div>

      {/* Layer 2: Waves */}
      <motion.div
        className="absolute inset-0"
        style={{ opacity: wavesOpacity }}
      >
        <Waves
          strokeColor="rgba(0, 212, 255, 0.22)"
          backgroundColor="transparent"
          pointerSize={0.5}
        />
      </motion.div>

      {/* Layer 3: Scanning grid */}
      <motion.div
        className="absolute inset-0"
        style={{
          opacity: gridOpacity,
          backgroundImage:
            "linear-gradient(rgba(0,212,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.3) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Vignette */}
      <motion.div
        className="absolute inset-0"
        style={{
          opacity: vignetteOpacity,
          background:
            "radial-gradient(ellipse at center, transparent 30%, rgba(5,5,7,0.7) 70%, rgba(5,5,7,0.95) 100%)",
        }}
      />
    </div>
  );
}
