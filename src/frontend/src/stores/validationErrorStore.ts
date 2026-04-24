import { create } from "zustand";
import type { z } from "zod";

export type StoredValidationError = {
  id: string;
  boundary: "http" | "storage" | "stream";
  mode: "permissive" | "strict";
  error: z.ZodError;
  raw: unknown;
  at: number;
};

type Store = {
  errors: StoredValidationError[];
  mutedIds: Set<string>;
  push: (err: StoredValidationError) => void;
  mute: (id: string) => void;
  unmute: (id: string) => void;
  clear: () => void;
};

const MUTE_KEY = "dto.mutedSchemaIds";
const MAX_ERRORS = 100;

function loadMuted(): Set<string> {
  try {
    const raw = sessionStorage.getItem(MUTE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? new Set(arr) : new Set();
  } catch { return new Set(); }
}

function saveMuted(s: Set<string>): void {
  try { sessionStorage.setItem(MUTE_KEY, JSON.stringify([...s])); } catch { /* noop */ }
}

const useValidationErrorStore = create<Store>((set) => ({
  errors: [],
  mutedIds: loadMuted(),
  push: (err) => set((s) => {
    if (s.mutedIds.has(err.id)) return s;
    return { errors: [err, ...s.errors].slice(0, MAX_ERRORS) };
  }),
  mute: (id) => set((s) => {
    const next = new Set(s.mutedIds); next.add(id); saveMuted(next); return { mutedIds: next };
  }),
  unmute: (id) => set((s) => {
    const next = new Set(s.mutedIds); next.delete(id); saveMuted(next); return { mutedIds: next };
  }),
  clear: () => set({ errors: [] }),
}));

export default useValidationErrorStore;
