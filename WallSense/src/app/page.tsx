"use client";

import { useRef } from "react";
import { BackgroundLayers } from "@/components/ui/background-layers";

import { BrickWallIntro } from "@/components/ui/brick-wall-intro";
import { TrackingOverlay } from "@/components/ui/tracking-overlay";
import { SystemActivation } from "@/components/ui/system-activation";
import { ScrollProgress } from "@/components/ui/scroll-progress";
import { FilmGrain } from "@/components/ui/film-grain";

export default function Home() {
  const mainRef = useRef<HTMLElement>(null);

  return (
    <main ref={mainRef} className="relative bg-[#050507]">
      <BackgroundLayers containerRef={mainRef} />
      <ScrollProgress containerRef={mainRef} />

      <FilmGrain />
      <div className="relative z-10">
        <BrickWallIntro />
        <TrackingOverlay />
        <SystemActivation />
      </div>
    </main>
  );
}
