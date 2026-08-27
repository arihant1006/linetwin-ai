"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * Scroll-progress is produced by the DOM (normal scrolling, no scroll-jacking)
 * and consumed inside the canvas through this shared ref.
 */
export const scrollProgress = { current: 0 };

/** Deterministic per-station sensor coverage profile (rich/medium/sparse). */
function stationCoverage(i: number): number {
  const cls = i % 20;
  if ([0, 1, 2, 3, 6, 7, 11, 12].includes(cls)) return 0.92;
  if ([4, 5, 8, 9, 10, 13, 18].includes(cls)) return 0.58;
  return 0.22;
}

const STATION_COUNT = 40;
const SPACING = 3.2;
const LINE_START_X = -(STATION_COUNT * SPACING) / 2;
const LINE_END_X = -LINE_START_X;
const FOCUS_X = LINE_START_X + 26 * SPACING; // a sparse-telemetry station
const BARRIER_X = LINE_END_X + 14;

// ---------------------------------------------------------------------------
// Continuous camera path: one keyframe chain, eased per segment, so motion is
// smooth everywhere (each keyframe pose == the next segment's start pose).
// ---------------------------------------------------------------------------
interface Keyframe {
  t: number;
  pos: [number, number, number];
  look: [number, number, number];
}

const KEYFRAMES: Keyframe[] = [
  // HERO — high wide establishing shot drifting toward the line entrance
  { t: 0.0, pos: [-6, 11, 34], look: [0, 1.5, 0] },
  { t: 0.2, pos: [LINE_START_X + 4, 6.5, 19], look: [LINE_START_X + 18, 1, 0] },
  // OBSERVE — long low sweep past the first two-thirds of the line,
  // flying over lit (rich) and dark (sparse) stations
  { t: 0.46, pos: [FOCUS_X - 11, 3.4, 9.5], look: [FOCUS_X, 1, 0] },
  // INFER — slow orbit around the dark focus station while pulses converge
  { t: 0.68, pos: [FOCUS_X + 8, 3.1, 7.5], look: [FOCUS_X, 1.1, 0] },
  // RECOMMEND — pull up/back to frame the constraint and downstream symptoms
  { t: 0.86, pos: [FOCUS_X + 17, 6.5, 15], look: [FOCUS_X + 7, 1, 0] },
  // SIMULATE — descend into a forward dolly down the rest of the line,
  // stopping short of the red control barrier past end-of-line
  { t: 1.0, pos: [BARRIER_X - 17, 2.6, 8], look: [BARRIER_X, 1.5, 0] },
];

const easeInOut = (k: number) =>
  k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;

/** 0→1 ramp between a..b, clamped. */
const ramp = (v: number, a: number, b: number) =>
  THREE.MathUtils.clamp((v - a) / Math.max(b - a, 1e-5), 0, 1);

function samplePose(p: number, outPos: THREE.Vector3, outLook: THREE.Vector3) {
  const t = THREE.MathUtils.clamp(p, 0, 1);
  let i = 0;
  while (i < KEYFRAMES.length - 2 && t > KEYFRAMES[i + 1].t) i++;
  const a = KEYFRAMES[i];
  const b = KEYFRAMES[i + 1];
  const span = Math.max(b.t - a.t, 1e-5);
  const raw = THREE.MathUtils.clamp((t - a.t) / span, 0, 1);
  const k = easeInOut(raw);
  outPos.set(
    THREE.MathUtils.lerp(a.pos[0], b.pos[0], k),
    THREE.MathUtils.lerp(a.pos[1], b.pos[1], k),
    THREE.MathUtils.lerp(a.pos[2], b.pos[2], k),
  );
  outLook.set(
    THREE.MathUtils.lerp(a.look[0], b.look[0], k),
    THREE.MathUtils.lerp(a.look[1], b.look[1], k),
    THREE.MathUtils.lerp(a.look[2], b.look[2], k),
  );
}

// ---------------------------------------------------------------------------

function CameraRig() {
  const smooth = useRef(0);
  const pos = useMemo(() => new THREE.Vector3(), []);
  const look = useMemo(() => new THREE.Vector3(), []);

  useFrame(({ camera }, delta) => {
    // Frame-rate independent damping of raw scroll input → buttery motion.
    const k = 1 - Math.exp(-3.5 * Math.min(delta, 0.1));
    smooth.current += (scrollProgress.current - smooth.current) * k;
    samplePose(smooth.current, pos, look);
    camera.position.copy(pos);
    camera.lookAt(look);
  });
  return null;
}

function StationField() {
  const meshes = useRef<THREE.Mesh[]>([]);
  const halos = useRef<THREE.Mesh[]>([]);
  const emissive = useMemo(
    () =>
      Array.from({ length: STATION_COUNT }, (_, i) => {
        const cov = stationCoverage(i);
        const color =
          cov > 0.8 ? "#22d3ee" : cov > 0.5 ? "#38bdf8" : "#334155";
        return { cov, color };
      }),
    [],
  );

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    for (let i = 0; i < STATION_COUNT; i++) {
      const m = meshes.current[i];
      if (m) {
        const mat = m.material as THREE.MeshStandardMaterial;
        const base = emissive[i].cov;
        const flicker =
          base > 0.5
            ? 0.9 + Math.sin(t * (1.5 + i * 0.13) + i) * 0.1
            : 0.35 + Math.sin(t * 0.7 + i * 2.7) * 0.15;
        mat.emissiveIntensity = base * 2.2 * flicker;
      }
      const h = halos.current[i];
      if (h) {
        const mat = h.material as THREE.MeshBasicMaterial;
        mat.opacity = emissive[i].cov * (0.65 + Math.sin(t * 2 + i) * 0.2);
      }
    }
  });

  return (
    <group>
      {Array.from({ length: STATION_COUNT }, (_, i) => {
        const e = emissive[i];
        const x = i * SPACING + LINE_START_X;
        return (
          <group key={i} position={[x, 0, 0]}>
            <mesh
              ref={(el) => {
                if (el) meshes.current[i] = el;
              }}
              position={[0, 0.75, 0]}
            >
              <boxGeometry args={[1.7, 1.5, 2]} />
              <meshStandardMaterial
                color="#171d26"
                emissive={e.color}
                emissiveIntensity={e.cov}
                roughness={0.55}
                metalness={0.35}
                transparent
                opacity={Math.max(e.cov, 0.28)}
              />
            </mesh>
            <mesh
              ref={(el) => {
                if (el) halos.current[i] = el;
              }}
              position={[0, 1.95, 0]}
            >
              <sphereGeometry args={[0.09 + e.cov * 0.1, 12, 12]} />
              <meshBasicMaterial color={e.color} transparent opacity={e.cov} />
            </mesh>
            <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <planeGeometry args={[SPACING - 0.7, 3.2]} />
              <meshBasicMaterial color="#232c3b" transparent opacity={0.35} />
            </mesh>
          </group>
        );
      })}
      {/* conveyor rail */}
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[STATION_COUNT * SPACING + 34, 0.25]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.22} />
      </mesh>
    </group>
  );
}

/**
 * Contextual signal pulses converging on the dark focus station (INFER).
 * Gated to the infer chapter of the scroll timeline with soft fades.
 */
function InferencePulses() {
  const refs = useRef<THREE.Mesh[]>([]);
  const sources = useMemo(() => [-16, -9, 5, 12, -23, 27], []);
  const smooth = useRef(0);

  useFrame(({ clock }, delta) => {
    const k = 1 - Math.exp(-4 * Math.min(delta, 0.1));
    smooth.current += (scrollProgress.current - smooth.current) * k;
    const w =
      ramp(smooth.current, 0.43, 0.5) * (1 - ramp(smooth.current, 0.63, 0.7));
    refs.current.forEach((m, i) => {
      if (!m) return;
      const phase = (clock.elapsedTime * 0.85 + i * 0.37) % 2.2;
      const prog = Math.min(phase / 1.9, 1);
      const sx = sources[i];
      m.position.set(
        sx + (FOCUS_X - sx) * prog,
        1.4 + Math.sin(prog * Math.PI) * 0.9,
        0,
      );
      const mat = m.material as THREE.MeshBasicMaterial;
      mat.opacity = w * Math.max(1 - Math.abs(prog - 0.5) * 1.7, 0) * 0.95;
      m.visible = w > 0.01;
    });
  });

  return (
    <>
      {sources.map((_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            if (el) refs.current[i] = el;
          }}
          visible={false}
        >
          <sphereGeometry args={[0.15, 12, 12]} />
          <meshBasicMaterial color="#67e8f9" transparent opacity={0} />
        </mesh>
      ))}
    </>
  );
}

/**
 * The control barrier past end-of-line: where "write to plant" would be —
 * and isn't. Attempt pulses travel toward it and bounce off.
 */
function ControlBarrier() {
  const wallRef = useRef<THREE.Mesh>(null);
  const pulseRef = useRef<THREE.Mesh>(null);
  const smooth = useRef(0);

  useFrame(({ clock }, delta) => {
    const k = 1 - Math.exp(-4 * Math.min(delta, 0.1));
    smooth.current += (scrollProgress.current - smooth.current) * k;
    const w = ramp(smooth.current, 0.83, 0.93);

    if (wallRef.current) {
      const mat = wallRef.current.material as THREE.MeshStandardMaterial;
      mat.opacity = 0.85 * w;
      mat.emissiveIntensity = 0.45 + Math.sin(clock.elapsedTime * 2) * 0.15;
      wallRef.current.visible = w > 0.01;
    }
    if (pulseRef.current) {
      const period = 3.0;
      const phase = clock.elapsedTime % period;
      const travel = 1.3;
      let x: number;
      if (phase < travel) {
        x = THREE.MathUtils.lerp(BARRIER_X - 26, BARRIER_X - 1.2, phase / travel);
      } else if (phase < travel * 2) {
        x = THREE.MathUtils.lerp(
          BARRIER_X - 1.2,
          BARRIER_X - 14,
          (phase - travel) / travel,
        );
      } else {
        x = BARRIER_X - 14;
      }
      pulseRef.current.position.set(x, 1.4, 0);
      const mat = pulseRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = w * (phase > period - 0.3 ? 0 : 0.95);
      pulseRef.current.visible = w > 0.01 && mat.opacity > 0.02;
    }
  });

  return (
    <>
      <mesh ref={wallRef} position={[BARRIER_X, 1.6, 0]} visible={false}>
        <boxGeometry args={[0.35, 3.4, 5]} />
        <meshStandardMaterial
          color="#ef4444"
          emissive="#ef4444"
          emissiveIntensity={0.5}
          transparent
          opacity={0}
        />
      </mesh>
      {/* hazard floor strip in front of the barrier */}
      <BarrierFloor x={BARRIER_X} />
      <mesh ref={pulseRef} position={[BARRIER_X - 26, 1.4, 0]} visible={false}>
        <sphereGeometry args={[0.18, 12, 12]} />
        <meshBasicMaterial color="#fca5a5" transparent opacity={0.95} />
      </mesh>
    </>
  );
}

function BarrierFloor({ x }: { x: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const smooth = useRef(0);
  useFrame(({}, delta) => {
    const k = 1 - Math.exp(-4 * Math.min(delta, 0.1));
    smooth.current += (scrollProgress.current - smooth.current) * k;
    if (ref.current) {
      const mat = ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = ramp(smooth.current, 0.83, 0.93) * 0.35;
      ref.current.visible = mat.opacity > 0.01;
    }
  });
  return (
    <mesh ref={ref} position={[x - 8, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
      <planeGeometry args={[16, 5.4]} />
      <meshBasicMaterial color="#ef4444" transparent opacity={0} />
    </mesh>
  );
}

export default function TwinScene() {
  useEffect(() => {
    function onScroll() {
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      scrollProgress.current = max > 0 ? window.scrollY / max : 0;
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return (
    <div className="fixed inset-0 z-0">
      <Canvas
        camera={{ position: [-6, 11, 34], fov: 50 }}
        dpr={[1, 1.75]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
      >
        <color attach="background" args={["#0a0d12"]} />
        <fog attach="fog" args={["#0a0d12", 26, 90]} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[10, 18, 12]} intensity={0.5} color="#8fb8c9" />
        <CameraRig />
        <StationField />
        <InferencePulses />
        <ControlBarrier />
      </Canvas>
      {/* vignette */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 42%, rgba(10,13,18,.88) 100%)",
        }}
      />
    </div>
  );
}
