import { useCallback, useSyncExternalStore } from "react";
const memory = new Map<string, string>();

// View preferences only: never authentication tokens or document contents.
export function useStoredFilter(key: string, fallback: string) {
  const storageKey = `buildtrust.view.${key}`;
  const subscribe = useCallback((listener: () => void) => {
    window.addEventListener("buildtrust-view", listener);
    return () => window.removeEventListener("buildtrust-view", listener);
  }, []);
  const read = useCallback(() => { try { return sessionStorage.getItem(storageKey) ?? memory.get(storageKey) ?? fallback; } catch { return memory.get(storageKey) ?? fallback; } }, [storageKey, fallback]);
  const value = useSyncExternalStore(subscribe, read, () => fallback);
  const setValue = (next: string) => { memory.set(storageKey, next); try { sessionStorage.setItem(storageKey, next); } catch { /* Keep this view usable when storage is disabled. */ } window.dispatchEvent(new Event("buildtrust-view")); };
  return [value, setValue] as const;
}
