"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { motion, useScroll, useTransform, useMotionValue, MotionValue, useMotionValueEvent } from "framer-motion";

// ─── Canvas-based dancing skeleton ─────────────────────────────────

const ACCENT = { r: 0, g: 212, b: 255 };
const ACCENT2 = { r: 0, g: 255, b: 136 }; // secondary accent for flashier joints
const BPM = 110;
const BEAT = 60 / BPM;

interface Joint { x: number; y: number; }

interface Skeleton {
  head: Joint; neck: Joint;
  lShoulder: Joint; rShoulder: Joint;
  lElbow: Joint; rElbow: Joint;
  lWrist: Joint; rWrist: Joint;
  spine: Joint; hip: Joint;
  lHip: Joint; rHip: Joint;
  lKnee: Joint; rKnee: Joint;
  lAnkle: Joint; rAnkle: Joint;
}

type JointName = keyof Skeleton;

const LIMBS: [JointName, JointName][] = [
  ["head", "neck"],
  ["neck", "lShoulder"], ["neck", "rShoulder"],
  ["lShoulder", "lElbow"], ["rShoulder", "rElbow"],
  ["lElbow", "lWrist"], ["rElbow", "rWrist"],
  ["neck", "spine"], ["spine", "hip"],
  ["hip", "lHip"], ["hip", "rHip"],
  ["lHip", "lKnee"], ["rHip", "rKnee"],
  ["lKnee", "lAnkle"], ["rKnee", "rAnkle"],
];

function computePose(t: number): Skeleton {
  const beat = t / BEAT;
  const s = Math.sin;
  const c = Math.cos;
  const bounce = Math.abs(s(beat * Math.PI)) * 8;
  const sway = s(beat * Math.PI) * 12;
  const weight = s(beat * Math.PI) * 0.5;
  const hipX = 250 + sway * 0.6;
  const hipY = 310 + bounce * 0.4;
  const spineX = hipX - sway * 0.15;
  const spineY = hipY - 65;
  const neckX = spineX - sway * 0.1;
  const neckY = spineY - 55;
  const headX = neckX + s(beat * Math.PI * 0.5) * 3;
  const headY = neckY - 30 - bounce * 0.2;
  const shoulderSpread = 45;
  const lShoulderX = neckX - shoulderSpread + s(beat * Math.PI) * 4;
  const lShoulderY = neckY + 15 + c(beat * Math.PI) * 2;
  const rShoulderX = neckX + shoulderSpread - s(beat * Math.PI) * 4;
  const rShoulderY = neckY + 15 - c(beat * Math.PI) * 2;
  const lArmRaise = (s(beat * Math.PI) + 1) * 0.5;
  const rArmRaise = (c(beat * Math.PI) + 1) * 0.5;
  const lElbowX = lShoulderX - 25 - lArmRaise * 15;
  const lElbowY = lShoulderY + 40 - lArmRaise * 55;
  const lWristX = lElbowX - 15 - lArmRaise * 20;
  const lWristY = lElbowY + 30 - lArmRaise * 50;
  const rElbowX = rShoulderX + 25 + rArmRaise * 15;
  const rElbowY = rShoulderY + 40 - rArmRaise * 55;
  const rWristX = rElbowX + 15 + rArmRaise * 20;
  const rWristY = rElbowY + 30 - rArmRaise * 50;
  const hipSpread = 22;
  const lHipX = hipX - hipSpread;
  const lHipY = hipY + 5 + weight * 4;
  const rHipX = hipX + hipSpread;
  const rHipY = hipY + 5 - weight * 4;
  const stepPhase = s(beat * Math.PI);
  const lKneeX = lHipX - 8 + stepPhase * 12;
  const lKneeY = lHipY + 65 + (stepPhase > 0 ? 0 : Math.abs(stepPhase) * 15);
  const lAnkleX = lKneeX - 5 + stepPhase * 8;
  const lAnkleY = lKneeY + 65 - (stepPhase > 0 ? 0 : Math.abs(stepPhase) * 10);
  const rKneeX = rHipX + 8 - stepPhase * 12;
  const rKneeY = rHipY + 65 + (stepPhase < 0 ? 0 : Math.abs(stepPhase) * 15);
  const rAnkleX = rKneeX + 5 - stepPhase * 8;
  const rAnkleY = rKneeY + 65 - (stepPhase < 0 ? 0 : Math.abs(stepPhase) * 10);

  return {
    head: { x: headX, y: headY }, neck: { x: neckX, y: neckY },
    lShoulder: { x: lShoulderX, y: lShoulderY }, rShoulder: { x: rShoulderX, y: rShoulderY },
    lElbow: { x: lElbowX, y: lElbowY }, rElbow: { x: rElbowX, y: rElbowY },
    lWrist: { x: lWristX, y: lWristY }, rWrist: { x: rWristX, y: rWristY },
    spine: { x: spineX, y: spineY }, hip: { x: hipX, y: hipY },
    lHip: { x: lHipX, y: lHipY }, rHip: { x: rHipX, y: rHipY },
    lKnee: { x: lKneeX, y: lKneeY }, rKnee: { x: rKneeX, y: rKneeY },
    lAnkle: { x: lAnkleX, y: lAnkleY }, rAnkle: { x: rAnkleX, y: rAnkleY },
  };
}

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  pose: Skeleton,
  alpha: number,
  trailAlpha: number,
  prevPose: Skeleton | null,
  t: number
) {
  const w = ctx.canvas.width;
  const h = ctx.canvas.height;
  ctx.clearRect(0, 0, w, h);
  const a = Math.max(0, Math.min(1, alpha));

  // Outer body glow (large, soft)
  const cx = pose.spine.x;
  const cy = pose.spine.y - 30;
  const bodyGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 180);
  bodyGlow.addColorStop(0, `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},${(a * 0.08).toFixed(3)})`);
  bodyGlow.addColorStop(1, `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},0)`);
  ctx.globalAlpha = 1;
  ctx.fillStyle = bodyGlow;
  ctx.beginPath();
  ctx.arc(cx, cy, 180, 0, Math.PI * 2);
  ctx.fill();

  // Motion trail
  if (prevPose && trailAlpha > 0) {
    ctx.globalAlpha = trailAlpha * a * 0.2;
    ctx.strokeStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},1)`;
    ctx.lineWidth = 4;
    ctx.lineCap = "round";
    for (const [from, to] of LIMBS) {
      ctx.beginPath();
      ctx.moveTo(prevPose[from].x, prevPose[from].y);
      ctx.lineTo(prevPose[to].x, prevPose[to].y);
      ctx.stroke();
    }
  }

  // Limb outer glow
  ctx.globalAlpha = a * 0.35;
  ctx.strokeStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},1)`;
  ctx.lineWidth = 6;
  ctx.lineCap = "round";
  ctx.shadowColor = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},0.5)`;
  ctx.shadowBlur = 12;
  for (const [from, to] of LIMBS) {
    ctx.beginPath();
    ctx.moveTo(pose[from].x, pose[from].y);
    ctx.lineTo(pose[to].x, pose[to].y);
    ctx.stroke();
  }
  ctx.shadowBlur = 0;

  // Limb lines
  ctx.globalAlpha = a * 0.9;
  ctx.strokeStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},1)`;
  ctx.lineWidth = 2;
  for (const [from, to] of LIMBS) {
    ctx.beginPath();
    ctx.moveTo(pose[from].x, pose[from].y);
    ctx.lineTo(pose[to].x, pose[to].y);
    ctx.stroke();
  }

  // Joints
  const pulse = 0.7 + 0.3 * Math.sin(t * 3);
  const jointNames = Object.keys(pose) as JointName[];
  for (const name of jointNames) {
    const j = pose[name];
    const isHead = name === "head";
    const isWrist = name === "lWrist" || name === "rWrist";
    const r = isHead ? 14 : isWrist ? 5 : 4;

    // Big glow
    ctx.globalAlpha = a * 0.4 * pulse;
    ctx.fillStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},1)`;
    ctx.beginPath();
    ctx.arc(j.x, j.y, r + 8, 0, Math.PI * 2);
    ctx.fill();

    // Medium glow
    ctx.globalAlpha = a * 0.5;
    ctx.beginPath();
    ctx.arc(j.x, j.y, r + 4, 0, Math.PI * 2);
    ctx.fill();

    // Solid joint — alternate color for wrists
    ctx.globalAlpha = a * 0.95;
    if (isHead) {
      ctx.strokeStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},0.9)`;
      ctx.lineWidth = 2;
      ctx.fillStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},0.12)`;
      ctx.beginPath();
      ctx.arc(j.x, j.y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else {
      const c = isWrist ? ACCENT2 : ACCENT;
      ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},0.95)`;
      ctx.beginPath();
      ctx.arc(j.x, j.y, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Head scan ring — rotating with glow
  const headPos = pose.head;
  const rotation = t * 1.5;
  ctx.save();
  ctx.translate(headPos.x, headPos.y);
  ctx.rotate(rotation);
  ctx.globalAlpha = a * 0.4;
  ctx.strokeStyle = `rgba(${ACCENT.r},${ACCENT.g},${ACCENT.b},1)`;
  ctx.lineWidth = 1;
  ctx.setLineDash([8, 5]);
  ctx.beginPath();
  ctx.arc(0, 0, 22, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
  // Second ring, opposite direction
  ctx.rotate(-rotation * 2);
  ctx.globalAlpha = a * 0.2;
  ctx.setLineDash([4, 8]);
  ctx.beginPath();
  ctx.arc(0, 0, 30, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  ctx.globalAlpha = 1;
}

function DancingSkeletonCanvas({ opacity }: { opacity: MotionValue<number> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const prevPoseRef = useRef<Skeleton | null>(null);
  const opacityRef = useRef(0);

  useMotionValueEvent(opacity, "change", (v) => { opacityRef.current = v; });

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
    const animate = (now: number) => {
      const t = (now - startTime) / 1000;
      const pose = computePose(t);
      drawSkeleton(ctx, pose, opacityRef.current, 1, prevPoseRef.current, t);
      prevPoseRef.current = pose;
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);

    return () => { cancelAnimationFrame(rafRef.current); window.removeEventListener("resize", resize); };
  }, []);

  return <canvas ref={canvasRef} className="h-full w-full" style={{ width: "500px", height: "100%" }} />;
}

// ─── Section ───────────────────────────────────────────────────────

const STATUS_LINES = ["INITIALIZING", "SCANNING SIGNALS", "ACQUIRING TARGET", "TRACKING ACTIVE"];

export function TrackingOverlay() {
  const sectionRef = useRef<HTMLDivElement>(null);
  // Use motion values for mouse offset to avoid React re-renders on every mousemove
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const rafPending = useRef(false);

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"],
  });

  // Fade in during section entry, hold through sticky pin, fade out on exit
  const figureOpacity = useTransform(scrollYProgress, [0, 0.15, 0.75, 0.9], [0, 1, 1, 0]);
  const figureScale = useTransform(scrollYProgress, [0, 0.15], [0.92, 1]);
  const glowIntensity = useTransform(scrollYProgress, [0.1, 0.25, 0.75, 0.9], [0, 1, 1, 0]);
  const statusIndex = useTransform(scrollYProgress, [0.15, 0.3, 0.5, 0.7], [0, 1, 2, 3]);

  // Bridge status index to state only when it actually changes (integer boundaries)
  const [statusText, setStatusText] = useState(STATUS_LINES[0]);
  const lastStatusIdx = useRef(0);
  useMotionValueEvent(statusIndex, "change", (v) => {
    const idx = Math.min(Math.floor(v), STATUS_LINES.length - 1);
    if (idx !== lastStatusIdx.current) {
      lastStatusIdx.current = idx;
      setStatusText(STATUS_LINES[idx]);
    }
  });

  // RAF-throttled mouse handler — updates motion values directly (no React state)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (rafPending.current) return;
    rafPending.current = true;
    requestAnimationFrame(() => {
      const rect = e.currentTarget?.getBoundingClientRect();
      if (rect) {
        mouseX.set(((e.clientX - rect.left) / rect.width - 0.5) * 10);
        mouseY.set(((e.clientY - rect.top) / rect.height - 0.5) * 10);
      }
      rafPending.current = false;
    });
  }, [mouseX, mouseY]);

  return (
    <section ref={sectionRef} id="detection" className="relative h-[120vh]">
      <div
        className="sticky top-0 flex h-screen w-full items-center justify-center overflow-hidden"
        onMouseMove={handleMouseMove}
      >
        {/* Large pulsing radial glow */}
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ opacity: glowIntensity }}
        >
          <motion.div
            animate={{ scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            style={{
              width: "700px",
              height: "700px",
              background: "radial-gradient(circle, rgba(0,212,255,0.15) 0%, rgba(0,212,255,0.05) 40%, transparent 70%)",
            }}
          />
        </motion.div>

        {/* Animated skeleton figure */}
        <motion.div
          className="relative flex h-[80vh] items-center justify-center"
          style={{ opacity: figureOpacity, scale: figureScale, x: mouseX, y: mouseY }}
        >
          <DancingSkeletonCanvas opacity={glowIntensity} />
        </motion.div>

        {/* Status text with neon glow */}
        <motion.div
          className="absolute bottom-20 left-1/2 -translate-x-1/2"
          style={{ opacity: glowIntensity }}
        >
          <div
            className="rounded-lg px-6 py-3"
            style={{
              background: "rgba(0, 212, 255, 0.04)",
              backdropFilter: "blur(20px)",
              border: "1px solid rgba(0, 212, 255, 0.15)",
              boxShadow: "0 0 20px rgba(0,212,255,0.08), inset 0 0 20px rgba(0,212,255,0.03)",
            }}
          >
            <p
              className="text-xs tracking-[0.4em] uppercase"
              style={{ fontFamily: "var(--font-geist-mono), monospace", color: "rgba(0,212,255,0.85)" }}
            >
              {statusText}
            </p>
          </div>
        </motion.div>

        {/* Corner brackets — larger, with gradient fade */}
        <motion.div className="pointer-events-none absolute inset-10 sm:inset-12" style={{ opacity: glowIntensity }}>
          {[
            "left-0 top-0 border-l border-t",
            "right-0 top-0 border-r border-t",
            "bottom-0 left-0 border-b border-l",
            "bottom-0 right-0 border-b border-r",
          ].map((pos, i) => (
            <motion.div
              key={i}
              className={`absolute h-12 w-12 ${pos} border-[rgba(0,212,255,0.3)]`}
              animate={{ opacity: [0.3, 0.7, 0.3] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.3, ease: "easeInOut" }}
            />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
