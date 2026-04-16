import type { SessionState } from "../types/contracts";

export interface SessionStore {
  currentSession: SessionState | null;
}

export const initialSessionStore: SessionStore = {
  currentSession: null,
};
