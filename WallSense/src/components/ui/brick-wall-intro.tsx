"use client";

import { useRef, useEffect, useState } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

// ─── Floating particles behind the title ───────────────────────────

function HeroParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      canvas.width = canvas.offsetWidth * dpr;
      canvas.height = canvas.offsetHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const PARTICLE_COUNT = 60;
    const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
      x: Math.random() * canvas.offsetWidth,
      y: Math.random() * canvas.offsetHeight,
      vx: (Math.random() - 0.5) * 0.4,
      vy: -Math.random() * 0.3 - 0.1,
      size: Math.random() * 2 + 0.5,
      alpha: Math.random() * 0.5 + 0.1,
      pulse: Math.random() * Math.PI * 2,
    }));

    let raf = 0;
    const draw = (t: number) => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += 0.02;

        if (p.y < -10) { p.y = h + 10; p.x = Math.random() * w; }
        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;

        const flicker = 0.5 + 0.5 * Math.sin(p.pulse + t * 0.001);
        const a = p.alpha * flicker;

        // Glow
        ctx.globalAlpha = a * 0.3;
        ctx.fillStyle = "rgba(0, 212, 255, 1)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
        ctx.fill();

        // Core
        ctx.globalAlpha = a;
        ctx.fillStyle = "rgba(0, 212, 255, 1)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />;
}

// ─── Animated subtitle letters ──────────────────────────────────────

function AnimatedSubtitle({ text }: { text: string }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  return (
    <span className="inline-flex">
      {text.split("").map((char, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={mounted ? { opacity: 0.5, y: 0 } : {}}
          transition={{ duration: 0.4, delay: 1.2 + i * 0.04, ease: "easeOut" }}
          className="inline-block"
          style={{ minWidth: char === " " ? "0.5em" : undefined }}
        >
          {char}
        </motion.span>
      ))}
    </span>
  );
}

// ─── Main Component ─────────────────────────────────────────────────

export function BrickWallIntro() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end start"],
  });

  // Text fades as hero scrolls, blur overlay darkens the scene
  const textOpacity = useTransform(scrollYProgress, [0, 0.25, 0.5], [1, 0.8, 0]);
  const textScale = useTransform(scrollYProgress, [0, 0.5], [1, 0.88]);
  const textY = useTransform(scrollYProgress, [0, 0.5], [0, -50]);
  const particleOpacity = useTransform(scrollYProgress, [0, 0.35, 0.55], [1, 0.5, 0]);
  const blurOverlayOpacity = useTransform(scrollYProgress, [0.3, 0.6], [0, 1]);

  return (
    <section
      ref={sectionRef}
      id="system"
      className="relative h-[250vh]"
    >
      <div className="sticky top-0 flex h-screen w-full flex-col items-center justify-center overflow-hidden">
        {/* Floating particles */}
        <motion.div className="absolute inset-0 z-0" style={{ opacity: particleOpacity }}>
          <HeroParticles />
        </motion.div>

        {/* Pulsing radial glow behind title */}
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{
            opacity: textOpacity,
            width: "900px",
            height: "900px",
            background: "radial-gradient(circle, rgba(0,212,255,0.12) 0%, rgba(0,100,200,0.06) 30%, transparent 60%)",
          }}
          animate={{
            scale: [1, 1.05, 1],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />

        {/* WallSense title — GPU-accelerated (only transform + opacity) */}
        <motion.div
          className="relative z-10 flex flex-col items-center gap-4"
          style={{
            opacity: textOpacity,
            scale: textScale,
            y: textY,
          }}
        >
          {/* Top accent line */}
          <motion.div
            className="mb-2 h-[1px] w-0"
            animate={{ width: "120px" }}
            transition={{ duration: 1.5, delay: 0.5, ease: "easeOut" }}
            style={{
              background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.6), transparent)",
            }}
          />

          <h1
            className="text-6xl font-extrabold tracking-[0.15em] uppercase sm:text-8xl md:text-9xl"
            style={{
              fontFamily: "var(--font-orbitron), sans-serif",
              color: "rgba(255,255,255,0.95)",
              textShadow:
                "0 0 40px rgba(0,212,255,0.4), 0 0 80px rgba(0,212,255,0.2), 0 0 160px rgba(0,212,255,0.1), 0 2px 4px rgba(0,0,0,0.5)",
            }}
          >
            WallSense
          </h1>

          {/* Animated gradient divider */}
          <div className="relative h-[2px] w-64 overflow-hidden rounded-full">
            <div
              className="absolute inset-0"
              style={{
                background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.7), transparent)",
              }}
            />
            <motion.div
              className="absolute inset-0"
              animate={{ x: ["-100%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              style={{
                background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent)",
                width: "50%",
              }}
            />
          </div>

          <p
            className="text-xs tracking-[0.5em] uppercase"
            style={{ fontFamily: "var(--font-geist-mono), monospace" }}
          >
            <AnimatedSubtitle text="Through-Wall Detection" />
          </p>

          {/* Version badge */}
          <motion.div
            className="mt-4 rounded-full px-4 py-1"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 2, duration: 0.6 }}
            style={{
              background: "rgba(0, 212, 255, 0.06)",
              border: "1px solid rgba(0, 212, 255, 0.15)",
            }}
          >
            <span
              className="text-[9px] tracking-[0.3em] uppercase"
              style={{
                fontFamily: "var(--font-geist-mono), monospace",
                color: "rgba(0, 212, 255, 0.6)",
              }}
            >
              v2.0 — Active Sensing
            </span>
          </motion.div>
        </motion.div>

        {/* Dark overlay — fades in as hero exits */}
        <motion.div
          className="absolute inset-0 z-20"
          style={{
            opacity: blurOverlayOpacity,
            background: "rgba(5,5,7,1)",
          }}
        />

        {/* Scroll indicator */}
        <motion.div
          className="absolute bottom-12 flex flex-col items-center gap-2"
          animate={{ opacity: [0.2, 0.6, 0.2] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
        >
          <motion.div
            className="h-8 w-[1px]"
            style={{ background: "linear-gradient(to bottom, rgba(0,212,255,0.4), transparent)" }}
            animate={{ scaleY: [1, 1.5, 1] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          />
          <span
            className="text-[8px] tracking-[0.5em] uppercase"
            style={{ fontFamily: "var(--font-geist-mono), monospace", color: "rgba(0,212,255,0.4)" }}
          >
            Scroll
          </span>
        </motion.div>
      </div>
    </section>
  );
}
