"use client";

import { useRef, useEffect, useState } from "react";
import {
  motion,
  useScroll,
  useTransform,
  useMotionValueEvent,
  MotionValue,
} from "framer-motion";

// ─── Constants ───────────────────────────────────────────────────────

const ACCENT = "rgba(0, 212, 255,";
const RING_COUNT = 6;
const RADAR_SWEEP_DURATION = 3; // seconds — faster for more energy
const PARTICLE_COUNT = 60;

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  alpha: number;
  life: number;
  maxLife: number;
}

function createParticle(w: number, h: number): Particle {
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.4,
    vy: (Math.random() - 0.5) * 0.4,
    size: Math.random() * 2 + 0.5,
    alpha: Math.random() * 0.5 + 0.15,
    life: Math.random() * 200,
    maxLife: 200 + Math.random() * 200,
  };
}

const STATUS_ITEMS = [
  { label: "RADAR MODULE", status: "ONLINE", color: "#00ff88" },
  { label: "SIGNAL PROCESSOR", status: "ONLINE", color: "#00ff88" },
  { label: "TRACKING ENGINE", status: "ONLINE", color: "#00ff88" },
  { label: "WALL PENETRATION", status: "READY", color: "#ffaa00" },
] as const;

// ─── Radar Canvas ────────────────────────────────────────────────────

function RadarCanvas({ intensityMV }: { intensityMV: MotionValue<number> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);
  const intensityRef = useRef(0);

  // Read motion value directly into ref — no React re-renders
  useMotionValueEvent(intensityMV, "change", (v) => {
    intensityRef.current = v;
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    window.addEventListener("resize", resize);

    const startTime = performance.now();

    const initRect = canvas.getBoundingClientRect();
    const particles: Particle[] = Array.from({ length: PARTICLE_COUNT }, () =>
      createParticle(initRect.width, initRect.height)
    );

    const draw = (now: number) => {
      const t = (now - startTime) / 1000;
      const alpha = intensityRef.current;
      const rect = canvas.getBoundingClientRect();
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      const maxR = Math.max(cx, cy) * 0.85;

      ctx.clearRect(0, 0, rect.width, rect.height);

      if (alpha < 0.01) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      // ── Grid lines — batched into single path for performance
      ctx.globalAlpha = alpha * 0.08;
      ctx.strokeStyle = `${ACCENT}1)`;
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      const gridSpacing = 40;
      for (let y = cy % gridSpacing; y < rect.height; y += gridSpacing) {
        ctx.moveTo(0, y);
        ctx.lineTo(rect.width, y);
      }
      for (let x = cx % gridSpacing; x < rect.width; x += gridSpacing) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, rect.height);
      }
      ctx.stroke();

      // ── Concentric radar rings — batched with single shadowBlur
      ctx.strokeStyle = `${ACCENT}1)`;
      ctx.lineWidth = 1;
      ctx.shadowBlur = 6;
      ctx.shadowColor = `${ACCENT}0.4)`;
      const avgPulse = 0.08 + 0.04 * Math.sin(t * 2);
      ctx.globalAlpha = alpha * avgPulse;
      ctx.beginPath();
      for (let i = 1; i <= RING_COUNT; i++) {
        const r = (maxR / RING_COUNT) * i;
        ctx.moveTo(cx + r, cy);
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // ── Cross-hairs (brighter)
      ctx.globalAlpha = alpha * 0.06;
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(cx, cy - maxR);
      ctx.lineTo(cx, cy + maxR);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx - maxR, cy);
      ctx.lineTo(cx + maxR, cy);
      ctx.stroke();

      // ── Diagonal cross-hairs
      ctx.globalAlpha = alpha * 0.03;
      ctx.beginPath();
      ctx.moveTo(cx - maxR * 0.7, cy - maxR * 0.7);
      ctx.lineTo(cx + maxR * 0.7, cy + maxR * 0.7);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx + maxR * 0.7, cy - maxR * 0.7);
      ctx.lineTo(cx - maxR * 0.7, cy + maxR * 0.7);
      ctx.stroke();

      // ── Sweeping radar arm (more intense)
      const sweepAngle =
        ((t % RADAR_SWEEP_DURATION) / RADAR_SWEEP_DURATION) * Math.PI * 2 - Math.PI / 2;
      const sweepGrad = ctx.createConicGradient(sweepAngle - 0.6, cx, cy);
      sweepGrad.addColorStop(0, `${ACCENT}0)`);
      sweepGrad.addColorStop(0.1, `${ACCENT}${(alpha * 0.2).toFixed(3)})`);
      sweepGrad.addColorStop(0.2, `${ACCENT}0)`);

      ctx.globalAlpha = 1;
      ctx.fillStyle = sweepGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx.fill();

      // ── Sweep line (brighter, with glow)
      ctx.globalAlpha = alpha * 0.7;
      ctx.strokeStyle = `${ACCENT}0.8)`;
      ctx.lineWidth = 2;
      ctx.shadowBlur = 12;
      ctx.shadowColor = `${ACCENT}0.6)`;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(
        cx + Math.cos(sweepAngle) * maxR,
        cy + Math.sin(sweepAngle) * maxR
      );
      ctx.stroke();
      ctx.shadowBlur = 0;

      // ── Second sweep arm (opposite direction, dimmer)
      const sweepAngle2 =
        (((t * 0.7) % RADAR_SWEEP_DURATION) / RADAR_SWEEP_DURATION) * Math.PI * 2 + Math.PI / 2;
      ctx.globalAlpha = alpha * 0.25;
      ctx.strokeStyle = `${ACCENT}0.4)`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(
        cx + Math.cos(sweepAngle2) * maxR * 0.7,
        cy + Math.sin(sweepAngle2) * maxR * 0.7
      );
      ctx.stroke();

      // ── Pulsing rings (more, brighter)
      const pulseCount = 4;
      for (let i = 0; i < pulseCount; i++) {
        const phase = (t * 0.4 + i / pulseCount) % 1;
        const r = phase * maxR;
        const pulseAlpha = (1 - phase) * 0.15 * alpha;
        ctx.globalAlpha = pulseAlpha;
        ctx.strokeStyle = `${ACCENT}1)`;
        ctx.lineWidth = 2;
        ctx.shadowBlur = 8;
        ctx.shadowColor = `${ACCENT}0.3)`;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.shadowBlur = 0;

      // ── Center dot (larger, pulsing)
      const centerPulse = 0.7 + 0.3 * Math.sin(t * 3);
      ctx.globalAlpha = alpha * centerPulse;
      ctx.fillStyle = `${ACCENT}1)`;
      ctx.shadowBlur = 15;
      ctx.shadowColor = `${ACCENT}0.8)`;
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // ── Center glow (bigger)
      const centerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 50);
      centerGlow.addColorStop(0, `${ACCENT}${(alpha * 0.4).toFixed(3)})`);
      centerGlow.addColorStop(1, `${ACCENT}0)`);
      ctx.globalAlpha = 1;
      ctx.fillStyle = centerGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, 50, 0, Math.PI * 2);
      ctx.fill();

      // ── Target blips on sweep path
      const blipCount = 3;
      for (let i = 0; i < blipCount; i++) {
        const blipAngle = sweepAngle - 0.3 - i * 0.15;
        const blipDist = maxR * (0.3 + i * 0.2);
        const bx = cx + Math.cos(blipAngle) * blipDist;
        const by = cy + Math.sin(blipAngle) * blipDist;
        const blipFade = 1 - i * 0.3;

        ctx.globalAlpha = alpha * 0.5 * blipFade;
        ctx.fillStyle = `${ACCENT}1)`;
        ctx.shadowBlur = 10;
        ctx.shadowColor = `${ACCENT}0.6)`;
        ctx.beginPath();
        ctx.arc(bx, by, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;

      // ── Dot matrix pattern (sparse)
      ctx.globalAlpha = alpha * 0.04;
      ctx.fillStyle = `${ACCENT}1)`;
      const dotSpacing = 20;
      for (let x = cx % dotSpacing; x < rect.width; x += dotSpacing) {
        for (let y = cy % dotSpacing; y < rect.height; y += dotSpacing) {
          ctx.beginPath();
          ctx.arc(x, y, 0.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // ── Floating particles (more)
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        p.life += 1;

        if (
          p.life > p.maxLife ||
          p.x < 0 || p.x > rect.width ||
          p.y < 0 || p.y > rect.height
        ) {
          Object.assign(p, createParticle(rect.width, rect.height));
        }

        const lifeFrac = p.life / p.maxLife;
        const fadeAlpha = lifeFrac < 0.1
          ? lifeFrac / 0.1
          : lifeFrac > 0.8
            ? (1 - lifeFrac) / 0.2
            : 1;

        // Glow halo
        ctx.globalAlpha = alpha * p.alpha * fadeAlpha * 0.3;
        ctx.fillStyle = `${ACCENT}1)`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
        ctx.fill();

        // Core
        ctx.globalAlpha = alpha * p.alpha * fadeAlpha;
        ctx.fillStyle = `${ACCENT}1)`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full"
    />
  );
}

// ─── Animated Border Button ─────────────────────────────────────────

function ActivateButton({ visible }: { visible: boolean }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.div
      className="relative mt-10"
      initial={{ opacity: 0, y: 30, scale: 0.9 }}
      animate={
        visible
          ? { opacity: 1, y: 0, scale: 1 }
          : { opacity: 0, y: 30, scale: 0.9 }
      }
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.6 }}
    >
      {/* Outer pulsing glow */}
      <motion.div
        className="absolute -inset-6 rounded-3xl"
        animate={{
          opacity: isHovered ? [0.4, 0.6, 0.4] : [0.1, 0.2, 0.1],
        }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        style={{
          background: `radial-gradient(ellipse at center, ${ACCENT}0.15), transparent 70%)`,
        }}
      />

      {/* Electric particles around button */}
      <motion.div
        className="absolute -inset-8 overflow-hidden rounded-3xl"
        animate={{ opacity: isHovered ? 1 : 0 }}
        transition={{ duration: 0.3 }}
      >
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute h-1 w-1 rounded-full"
            style={{
              background: `${ACCENT}0.8)`,
              boxShadow: `0 0 6px ${ACCENT}0.6)`,
              left: `${10 + Math.random() * 80}%`,
              top: `${10 + Math.random() * 80}%`,
            }}
            animate={{
              x: [0, (Math.random() - 0.5) * 40],
              y: [0, (Math.random() - 0.5) * 40],
              opacity: [0, 1, 0],
              scale: [0, 1.5, 0],
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              delay: i * 0.25,
              ease: "easeOut",
            }}
          />
        ))}
      </motion.div>

      {/* Rotating border wrapper */}
      <div
        className="relative overflow-hidden rounded-xl p-[2px] transition-all duration-500"
        style={{
          background: isHovered
            ? `linear-gradient(135deg, ${ACCENT}0.6), ${ACCENT}0.2), ${ACCENT}0.6))`
            : `linear-gradient(135deg, ${ACCENT}0.3), ${ACCENT}0.08), ${ACCENT}0.3))`,
        }}
      >
        {/* Animated conic border */}
        <div
          className="absolute -inset-[100%] animate-[spin_3s_linear_infinite]"
          style={{
            background: `conic-gradient(from 0deg, transparent, ${ACCENT}${isHovered ? "0.6" : "0.3"}), transparent, ${ACCENT}${isHovered ? "0.3" : "0.15"}), transparent)`,
          }}
        />

        {/* Secondary counter-spinning border */}
        <div
          className="absolute -inset-[100%] animate-[spin_5s_linear_infinite_reverse]"
          style={{
            background: `conic-gradient(from 180deg, transparent, ${ACCENT}${isHovered ? "0.3" : "0.1"}), transparent, transparent)`,
          }}
        />

        {/* Inner button */}
        <button
          className="relative z-10 flex items-center gap-4 rounded-[10px] px-12 py-6 transition-all duration-300"
          style={{
            background: isHovered
              ? "rgba(0, 212, 255, 0.06)"
              : "rgba(5, 5, 7, 0.92)",
            backdropFilter: "blur(20px)",
            boxShadow: isHovered
              ? `inset 0 0 30px ${ACCENT}0.05), 0 0 30px ${ACCENT}0.1)`
              : "none",
          }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          onClick={() => {
            window.location.href = "/dashboard";
          }}
        >
          {/* Pulse indicator */}
          <span className="relative flex h-3 w-3">
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
              style={{ backgroundColor: `${ACCENT}0.6)` }}
            />
            <span
              className="relative inline-flex h-3 w-3 rounded-full"
              style={{
                backgroundColor: `${ACCENT}1)`,
                boxShadow: `0 0 10px ${ACCENT}0.8)`,
              }}
            />
          </span>

          <span
            className="text-sm font-bold tracking-[0.3em] uppercase sm:text-base md:text-lg"
            style={{
              fontFamily: "var(--font-orbitron), sans-serif",
              color: isHovered ? "rgba(0, 212, 255, 1)" : "rgba(255,255,255,0.9)",
              textShadow: isHovered
                ? "0 0 20px rgba(0,212,255,0.6), 0 0 40px rgba(0,212,255,0.3), 0 0 80px rgba(0,212,255,0.15)"
                : "0 0 10px rgba(0,212,255,0.15)",
              transition: "color 0.3s, text-shadow 0.3s",
            }}
          >
            Enter the System
          </span>

          {/* Arrow icon */}
          <motion.svg
            className="h-5 w-5"
            animate={{ x: isHovered ? 4 : 0 }}
            transition={{ duration: 0.3 }}
            style={{
              color: isHovered ? "rgba(0, 212, 255, 1)" : "rgba(255,255,255,0.5)",
              filter: isHovered ? "drop-shadow(0 0 4px rgba(0,212,255,0.5))" : "none",
            }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </motion.svg>
        </button>
      </div>

      {/* Bottom reflection glow */}
      <motion.div
        className="absolute -bottom-10 left-1/2 h-10 w-4/5 -translate-x-1/2 rounded-full blur-2xl"
        animate={{
          opacity: isHovered ? [0.6, 0.8, 0.6] : [0.15, 0.25, 0.15],
        }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        style={{
          background: `${ACCENT}0.2)`,
        }}
      />
    </motion.div>
  );
}

// ─── Status Line ─────────────────────────────────────────────────────

function StatusLine({
  label,
  status,
  color,
  index,
  visible,
}: {
  label: string;
  status: string;
  color: string;
  index: number;
  visible: boolean;
}) {
  return (
    <motion.div
      className="flex items-center justify-between gap-6 border-b border-white/[0.04] py-3 last:border-0"
      initial={{ opacity: 0, x: -20 }}
      animate={visible ? { opacity: 1, x: 0 } : { opacity: 0, x: -20 }}
      transition={{
        duration: 0.5,
        ease: [0.16, 1, 0.3, 1],
        delay: index * 0.12 + 0.2,
      }}
    >
      <span
        className="text-[10px] tracking-[0.3em] uppercase opacity-50 sm:text-xs"
        style={{ fontFamily: "var(--font-geist-mono), monospace" }}
      >
        {label}
      </span>
      <div className="flex items-center gap-2.5">
        {/* Status dot with stronger glow */}
        <span className="relative flex h-2.5 w-2.5">
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50"
            style={{
              backgroundColor: color,
              animationDuration: "1.5s",
              animationDelay: `${index * 0.3}s`,
            }}
          />
          <span
            className="relative inline-flex h-2.5 w-2.5 rounded-full"
            style={{
              backgroundColor: color,
              boxShadow: `0 0 8px ${color}aa, 0 0 16px ${color}44`,
            }}
          />
        </span>
        <span
          className="text-[10px] font-semibold tracking-[0.2em] uppercase sm:text-xs"
          style={{
            fontFamily: "var(--font-geist-mono), monospace",
            color,
            textShadow: `0 0 8px ${color}66`,
          }}
        >
          {status}
        </span>
      </div>
    </motion.div>
  );
}

// ─── Main Section ────────────────────────────────────────────────────

export function SystemActivation() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [panelVisible, setPanelVisible] = useState(false);
  const panelVisibleRef = useRef(false);

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end end"],
  });

  const sectionOpacity = useTransform(
    scrollYProgress,
    [0, 0.15, 0.35],
    [0, 0.5, 1]
  );

  const sectionScale = useTransform(
    scrollYProgress,
    [0, 0.3],
    [0.92, 1]
  );

  const radarOpacityMV = useTransform(
    scrollYProgress,
    [0.05, 0.4],
    [0, 1]
  );

  const panelY = useTransform(
    scrollYProgress,
    [0.15, 0.45],
    [60, 0]
  );

  // Extract scanline opacity outside of JSX for better performance
  const scanlineOpacity = useTransform(sectionOpacity, (v) => v * 0.06);

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    const shouldBeVisible = v > 0.25;
    if (shouldBeVisible !== panelVisibleRef.current) {
      panelVisibleRef.current = shouldBeVisible;
      setPanelVisible(shouldBeVisible);
    }
  });

  return (
    <section ref={sectionRef} id="activate" className="relative h-[150vh]">
      <div className="sticky top-0 flex h-screen w-full items-center justify-center overflow-hidden">
        {/* Radar background */}
        <motion.div
          className="absolute inset-0"
          style={{ opacity: sectionOpacity }}
        >
          <RadarCanvas intensityMV={radarOpacityMV} />
        </motion.div>

        {/* Large pulsing radial glow behind everything */}
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{
            width: "800px",
            height: "800px",
            background: `radial-gradient(circle, ${ACCENT}0.08) 0%, ${ACCENT}0.03) 30%, transparent 60%)`,
            opacity: sectionOpacity,
          }}
          animate={{ scale: [1, 1.08, 1], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        />

        {/* Content */}
        <motion.div
          className="relative z-10 flex flex-col items-center"
          style={{
            opacity: sectionOpacity,
            scale: sectionScale,
            y: panelY,
          }}
        >
          {/* Section label */}
          <motion.div
            className="mb-8"
            initial={{ opacity: 0 }}
            animate={panelVisible ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <div
              className="glass rounded-full px-5 py-1.5"
              style={{
                boxShadow: "0 0 15px rgba(0,212,255,0.06)",
              }}
            >
              <p
                className="text-[9px] tracking-[0.5em] uppercase opacity-50"
                style={{ fontFamily: "var(--font-geist-mono), monospace" }}
              >
                System Activation
              </p>
            </div>
          </motion.div>

          {/* Glassmorphic status panel */}
          <motion.div
            className="glass relative w-[340px] rounded-xl px-6 py-5 sm:w-[420px] sm:px-8 sm:py-6"
            initial={{ opacity: 0, y: 20 }}
            animate={
              panelVisible
                ? { opacity: 1, y: 0 }
                : { opacity: 0, y: 20 }
            }
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
            style={{
              boxShadow: panelVisible
                ? `0 0 40px ${ACCENT}0.06), inset 0 0 30px ${ACCENT}0.03)`
                : "none",
            }}
          >
            {/* Top shimmer line */}
            <div className="absolute top-0 left-0 right-0 h-[1px] overflow-hidden rounded-t-xl">
              <motion.div
                className="h-full w-1/3"
                animate={{ x: ["-100%", "400%"] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                style={{ background: `linear-gradient(90deg, transparent, ${ACCENT}0.4), transparent)` }}
              />
            </div>

            {/* Panel header */}
            <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
              <span
                className="text-[10px] font-semibold tracking-[0.25em] uppercase"
                style={{
                  fontFamily: "var(--font-orbitron), sans-serif",
                  color: `${ACCENT}0.8)`,
                  textShadow: `0 0 10px ${ACCENT}0.3)`,
                }}
              >
                Subsystem Status
              </span>
              <motion.span
                className="text-[9px] tracking-[0.15em] uppercase"
                style={{ fontFamily: "var(--font-geist-mono), monospace", color: `${ACCENT}0.3)` }}
                animate={{ opacity: [0.2, 0.4, 0.2] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                v2.0
              </motion.span>
            </div>

            {/* Status lines */}
            {STATUS_ITEMS.map((item, i) => (
              <StatusLine
                key={item.label}
                label={item.label}
                status={item.status}
                color={item.color}
                index={i}
                visible={panelVisible}
              />
            ))}
          </motion.div>

          {/* Activate button */}
          <ActivateButton visible={panelVisible} />

          {/* Bottom helper text */}
          <motion.p
            className="mt-8 text-[9px] tracking-[0.3em] uppercase"
            style={{
              fontFamily: "var(--font-geist-mono), monospace",
              color: `${ACCENT}0.3)`,
            }}
            initial={{ opacity: 0 }}
            animate={panelVisible ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.8, delay: 1 }}
          >
            All systems nominal
          </motion.p>
        </motion.div>

        {/* HUD Corner brackets — flashier with pulsing */}
        <motion.div
          className="pointer-events-none absolute inset-8 sm:inset-12"
          style={{ opacity: sectionOpacity }}
        >
          {/* Top-left */}
          <motion.div
            className="absolute left-0 top-0"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            <div
              className="h-12 w-[2px]"
              style={{ background: `linear-gradient(to bottom, ${ACCENT}0.5), transparent)` }}
            />
            <div
              className="absolute left-0 top-0 h-[2px] w-12"
              style={{ background: `linear-gradient(to right, ${ACCENT}0.5), transparent)` }}
            />
          </motion.div>
          {/* Top-right */}
          <motion.div
            className="absolute right-0 top-0"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 0.75 }}
          >
            <div
              className="ml-auto h-12 w-[2px]"
              style={{ background: `linear-gradient(to bottom, ${ACCENT}0.5), transparent)` }}
            />
            <div
              className="absolute right-0 top-0 h-[2px] w-12"
              style={{ background: `linear-gradient(to left, ${ACCENT}0.5), transparent)` }}
            />
          </motion.div>
          {/* Bottom-left */}
          <motion.div
            className="absolute bottom-0 left-0"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
          >
            <div
              className="h-12 w-[2px]"
              style={{ background: `linear-gradient(to top, ${ACCENT}0.5), transparent)` }}
            />
            <div
              className="absolute bottom-0 left-0 h-[2px] w-12"
              style={{ background: `linear-gradient(to right, ${ACCENT}0.5), transparent)` }}
            />
          </motion.div>
          {/* Bottom-right */}
          <motion.div
            className="absolute bottom-0 right-0"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 2.25 }}
          >
            <div
              className="ml-auto h-12 w-[2px]"
              style={{ background: `linear-gradient(to top, ${ACCENT}0.5), transparent)` }}
            />
            <div
              className="absolute bottom-0 right-0 h-[2px] w-12"
              style={{ background: `linear-gradient(to left, ${ACCENT}0.5), transparent)` }}
            />
          </motion.div>

          {/* HUD label bottom-right */}
          <motion.div
            className="absolute bottom-0 right-0 -translate-y-8 pr-2"
            initial={{ opacity: 0 }}
            animate={panelVisible ? { opacity: 0.3 } : { opacity: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <p
              className="text-[8px] tracking-[0.3em] uppercase"
              style={{
                fontFamily: "var(--font-geist-mono), monospace",
                color: `${ACCENT}0.5)`,
              }}
            >
              WALLSENSE SYS v2.0
            </p>
          </motion.div>

          {/* HUD label top-left */}
          <motion.div
            className="absolute left-0 top-0 translate-y-8 pl-2"
            initial={{ opacity: 0 }}
            animate={panelVisible ? { opacity: 0.3 } : { opacity: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            <p
              className="text-[8px] tracking-[0.3em] uppercase"
              style={{
                fontFamily: "var(--font-geist-mono), monospace",
                color: `${ACCENT}0.5)`,
              }}
            >
              SEC CLEARANCE: ALPHA
            </p>
          </motion.div>
        </motion.div>

        {/* Scan line effect (more visible) */}
        <motion.div
          className="pointer-events-none absolute inset-0 overflow-hidden"
          style={{ opacity: scanlineOpacity }}
        >
          <div
            className="absolute inset-0 animate-[scanline_6s_linear_infinite]"
            style={{
              background: `linear-gradient(to bottom, transparent 0%, ${ACCENT}0.12) 50%, transparent 100%)`,
              backgroundSize: "100% 4px",
            }}
          />
        </motion.div>
      </div>
    </section>
  );
}
