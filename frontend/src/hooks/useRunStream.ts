import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  RUN_EVENT_TYPES,
  fetchAllEvents,
  type RunEvent,
} from "../api/run";
import { initialRunState, runReducer } from "../lib/runState";

export type RunConnection = "idle" | "connecting" | "live" | "reconnecting" | "replaying" | "error";

const STREAM_TYPES: string[] = RUN_EVENT_TYPES;

export function useRunStream(projectId: string | undefined) {
  const [state, dispatch] = useReducer(runReducer, undefined, initialRunState);
  const [connection, setConnection] = useState<RunConnection>("idle");
  const [replaying, setReplaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const lastIdRef = useRef(0);
  const connectRef = useRef<() => void>(() => undefined);
  const replayTimersRef = useRef<number[]>([]);
  const replayingRef = useRef(false);

  const handleEvent = useCallback((raw: MessageEvent) => {
    if (replayingRef.current) return;
    try {
      const event = JSON.parse(String(raw.data)) as RunEvent;
      if (!event || typeof event.id !== "number" || event.id <= lastIdRef.current) return;
      lastIdRef.current = event.id;
      dispatch({ type: "event", event });
      setError(null);
    } catch {
      // Ignore malformed frames; the stream must keep running.
    }
  }, []);

  useEffect(() => {
    if (!projectId) {
      setConnection("idle");
      return;
    }
    let disposed = false;
    let retry = 0;
    let retryTimer: number | undefined;

    const clearRetry = () => {
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
        retryTimer = undefined;
      }
    };

    const connect = () => {
      if (disposed) return;
      clearRetry();
      sourceRef.current?.close();
      const url = `/api/v1/projects/${encodeURIComponent(projectId)}/events?last_event_id=${
        lastIdRef.current
      }`;
      const source = new EventSource(url);
      sourceRef.current = source;
      setConnection(lastIdRef.current === 0 && retry === 0 ? "connecting" : "reconnecting");

      source.onopen = () => {
        if (disposed) return;
        retry = 0;
        setConnection("live");
        setError(null);
      };

      source.onerror = () => {
        if (disposed) return;
        source.close();
        if (sourceRef.current === source) sourceRef.current = null;
        retry += 1;
        setConnection("reconnecting");
        if (retry >= 4) setError("The live stream is unavailable. Retrying automatically…");
        const delay = Math.min(8000, 500 * 2 ** Math.min(retry, 4));
        retryTimer = window.setTimeout(connect, delay);
      };

      source.onmessage = handleEvent;
      for (const type of STREAM_TYPES) {
        source.addEventListener(type, handleEvent as EventListener);
      }
    };

    connectRef.current = connect;
    connect();

    return () => {
      disposed = true;
      clearRetry();
      for (const timer of replayTimersRef.current) window.clearTimeout(timer);
      replayTimersRef.current = [];
      sourceRef.current?.close();
      sourceRef.current = null;
      connectRef.current = () => undefined;
    };
  }, [projectId, handleEvent]);

  const replay = useCallback(async () => {
    if (!projectId) return;
    for (const timer of replayTimersRef.current) window.clearTimeout(timer);
    replayTimersRef.current = [];
    replayingRef.current = true;
    setReplaying(true);
    setError(null);
    sourceRef.current?.close();
    sourceRef.current = null;
    setConnection("replaying");

    try {
      const events = await fetchAllEvents(projectId);
      dispatch({ type: "reset" });
      lastIdRef.current = 0;

      if (!events.length) {
        replayingRef.current = false;
        setReplaying(false);
        setConnection("reconnecting");
        connectRef.current();
        return;
      }

      let cumulative = 16;
      let previousTs = new Date(events[0].ts).getTime();
      events.forEach((event, index) => {
        const timestamp = new Date(event.ts).getTime();
        if (index > 0) {
          const delta =
            Number.isFinite(timestamp) && Number.isFinite(previousTs)
              ? Math.max(0, timestamp - previousTs)
              : 0;
          cumulative += Math.max(4, delta / 20);
        }
        previousTs = timestamp;
        const timer = window.setTimeout(() => {
          lastIdRef.current = event.id;
          dispatch({ type: "event", event });
          if (index === events.length - 1) {
            replayingRef.current = false;
            setReplaying(false);
            setConnection("reconnecting");
            connectRef.current();
          }
        }, cumulative);
        replayTimersRef.current.push(timer);
      });
    } catch (caught) {
      replayingRef.current = false;
      setReplaying(false);
      setConnection("error");
      setError(
        caught instanceof Error ? caught.message : "Could not load the stored run events.",
      );
      connectRef.current();
    }
  }, [projectId]);

  return { state, connection, replaying, replay, error };
}
