"use client";

import { useScroll, useTransform, MotionValue, UseScrollOptions } from "framer-motion";
import { RefObject } from "react";

interface ScrollSectionOptions {
  target: RefObject<HTMLElement | null>;
  offset?: UseScrollOptions["offset"];
}

export function useScrollSection({ target, offset }: ScrollSectionOptions) {
  const { scrollYProgress } = useScroll({
    target,
    offset: offset ?? ["start start", "end start"],
  });

  return { progress: scrollYProgress };
}

export function useScrollRange(
  progress: MotionValue<number>,
  inputRange: [number, number],
  outputRange: [number, number]
) {
  return useTransform(progress, inputRange, outputRange);
}
