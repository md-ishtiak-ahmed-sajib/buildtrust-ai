import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useBlocker } from "react-router-dom";
import { Modal, ErrorState } from "./ui";

type Draft = {
  dirty: boolean;
  save: () => Promise<void>;
  discard?: () => void;
};
const Context = createContext<{
  register: (draft: Draft) => void;
  clear: () => void;
  request: (action: () => void) => void;
}>(null!);

export function DraftProvider({ children }: { children: ReactNode }) {
  const draft = useRef<Draft>({ dirty: false, save: async () => {} });
  const [pending, setPending] = useState<(() => void) | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const blocker = useBlocker(() => draft.current.dirty);
  const open = pending !== null || blocker.state === "blocked";
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => {
      if (draft.current.dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => window.removeEventListener("beforeunload", unload);
  }, []);
  function stay() {
    setPending(null);
    setError("");
    if (blocker.state === "blocked") blocker.reset();
  }
  function proceed(discard = false) {
    if (discard) draft.current.discard?.();
    draft.current.dirty = false;
    const next = pending;
    setPending(null);
    setError("");
    if (blocker.state === "blocked") blocker.proceed();
    else next?.();
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      await draft.current.save();
      proceed();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Save failed. Your changes are still here.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Context.Provider
      value={{
        register: (value) => {
          draft.current = value;
        },
        clear: () => {
          draft.current.dirty = false;
        },
        request: (action) => {
          if (draft.current.dirty) setPending(() => action);
          else action();
        },
      }}
    >
      {children}
      {open && (
        <Modal title="Unsaved estimate changes" onClose={() => !busy && stay()}>
          <p>
            Your estimate has unsaved changes. Save them before continuing, or
            discard them.
          </p>
          {error && <ErrorState message={error} />}
          <div className="modal-actions">
            <button className="button" disabled={busy} onClick={stay}>
              Stay
            </button>
            <button
              className="button"
              disabled={busy}
              onClick={() => proceed(true)}
            >
              Discard
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void save()}
            >
              Save and continue
            </button>
          </div>
        </Modal>
      )}
    </Context.Provider>
  );
}

export function useDraftRegistration(
  dirty: boolean,
  save: () => Promise<void>,
  discard?: () => void,
) {
  const guard = useContext(Context);
  useEffect(() => {
    guard.register({ dirty, save, discard });
  });
  useEffect(() => () => guard.clear(), []);
  return guard.request;
}
export const useGuardedAction = () => useContext(Context).request;
