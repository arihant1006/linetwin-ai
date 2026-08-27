"use client";

import { create } from "zustand";

export type Persona = "supervisor" | "manager" | "leadership" | "whatif";

interface TwinStore {
  selectedStation: string | null;
  selectStation: (sid: string | null) => void;
  speed: "1x" | "5x" | "10x" | "50x";
  setSpeed: (s: TwinStore["speed"]) => void;
}

export const useTwinStore = create<TwinStore>((set) => ({
  selectedStation: null,
  selectStation: (sid) => set({ selectedStation: sid }),
  speed: "1x",
  setSpeed: (speed) => set({ speed }),
}));
