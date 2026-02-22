"use client";

import { useRef, useState, useEffect } from "react";
import { motion, useScroll, useMotionValueEvent, AnimatePresence } from "framer-motion";

const NAV_ITEMS = [
  { label: "System", href: "#system" },
  { label: "Detection", href: "#detection" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "Activate", href: "#activate" },
] as const;

export function FloatingNav() {
  const [visible, setVisible] = useState(true);
  const [scrolled, setScrolled] = useState(false);
  const lastScrollY = useRef(0);

  const { scrollY } = useScroll();

  useMotionValueEvent(scrollY, "change", (current) => {
    const previous = lastScrollY.current;
    const direction = current - previous;

    // Show when scrolling up or near top
    if (current < 100) {
      setVisible(true);
      setScrolled(false);
    } else {
      setScrolled(true);
      setVisible(direction < -5);
    }

    lastScrollY.current = current;
  });

  const handleClick = (href: string) => {
    const id = href.replace("#", "");
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.nav
          className="fixed left-1/2 top-6 z-[100] -translate-x-1/2"
          initial={{ y: -80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -80, opacity: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <div
            className="flex items-center gap-1 rounded-full px-2 py-2 transition-all duration-300"
            style={{
              background: scrolled
                ? "rgba(5, 5, 7, 0.8)"
                : "rgba(5, 5, 7, 0.4)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              border: `1px solid ${scrolled ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.05)"}`,
              boxShadow: scrolled
                ? "0 8px 32px rgba(0,0,0,0.4), 0 0 1px rgba(0,212,255,0.1)"
                : "none",
            }}
          >
            {/* Logo */}
            <div className="flex items-center gap-2 pl-3 pr-4">
              <div
                className="h-2 w-2 rounded-full"
                style={{
                  background: "rgba(0, 212, 255, 0.9)",
                  boxShadow: "0 0 8px rgba(0, 212, 255, 0.4)",
                }}
              />
              <span
                className="text-[11px] font-bold tracking-[0.2em] uppercase"
                style={{
                  fontFamily: "var(--font-orbitron), sans-serif",
                  color: "rgba(255,255,255,0.85)",
                }}
              >
                WS
              </span>
            </div>

            {/* Separator */}
            <div
              className="h-4 w-[1px]"
              style={{
                background: "linear-gradient(to bottom, transparent, rgba(255,255,255,0.1), transparent)",
              }}
            />

            {/* Nav items */}
            {NAV_ITEMS.map((item) => (
              <NavItem
                key={item.label}
                label={item.label}
                onClick={() => handleClick(item.href)}
              />
            ))}
          </div>
        </motion.nav>
      )}
    </AnimatePresence>
  );
}

function NavItem({ label, onClick }: { label: string; onClick: () => void }) {
  const [hovered, setHovered] = useState(false);

  return (
    <button
      className="relative rounded-full px-4 py-1.5 transition-colors duration-200"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
    >
      {/* Hover background */}
      <AnimatePresence>
        {hovered && (
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{ background: "rgba(255,255,255,0.06)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            layoutId="nav-hover"
          />
        )}
      </AnimatePresence>

      <span
        className="relative z-10 text-[11px] tracking-[0.15em] uppercase transition-colors duration-200"
        style={{
          fontFamily: "var(--font-geist-mono), monospace",
          color: hovered ? "rgba(0, 212, 255, 0.9)" : "rgba(255,255,255,0.45)",
        }}
      >
        {label}
      </span>

      {/* Neon underline glow on hover */}
      <motion.div
        className="absolute bottom-0 left-1/2 h-[1px] -translate-x-1/2"
        style={{
          width: "60%",
          background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.6), transparent)",
          opacity: hovered ? 1 : 0,
          transition: "opacity 0.2s ease",
        }}
      />
    </button>
  );
}
