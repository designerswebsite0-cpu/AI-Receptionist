"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Room, RoomEvent } from "livekit-client";
import { Button } from "@/components/ui/button";

type TakeoverResponse = {
  livekit_url: string | null;
  token: string | null;
  room_name: string | null;
  configured: boolean;
};

export function CallActionsPanel({ callId, status }: { callId: string; status: string }) {
  const router = useRouter();
  const [room, setRoom] = useState<Room | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [ending, setEnding] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isActive = status === "ringing" || status === "in_progress";

  async function handleTakeover() {
    setConnecting(true);
    setError(null);
    const response = await fetch(`/api/voice-calls/${callId}/takeover`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      setConnecting(false);
      setError(payload?.error?.message ?? "Could not start takeover.");
      return;
    }
    const data: TakeoverResponse = payload.data;
    if (!data.configured || !data.token || !data.livekit_url) {
      setConnecting(false);
      setError(
        "AI has been paused for this call, but live audio join isn't available yet — LiveKit isn't fully " +
          "configured (no LIVEKIT_URL/API_KEY/API_SECRET, or the call hasn't connected a room yet).",
      );
      return;
    }

    try {
      const newRoom = new Room();
      newRoom.on(RoomEvent.Disconnected, () => setConnected(false));
      await newRoom.connect(data.livekit_url, data.token);
      await newRoom.localParticipant.setMicrophoneEnabled(true);
      setRoom(newRoom);
      setConnected(true);
    } catch {
      setError("Connected to the backend, but the browser could not join the live call audio.");
    } finally {
      setConnecting(false);
    }
  }

  function handleDisconnect() {
    room?.disconnect();
    setRoom(null);
    setConnected(false);
  }

  async function handleEndCall() {
    if (!window.confirm("End this call?")) return;
    setEnding(true);
    room?.disconnect();
    const response = await fetch(`/api/voice-calls/${callId}/end`, { method: "POST" });
    setEnding(false);
    if (response.ok) router.refresh();
  }

  if (!isActive) {
    return <p className="text-sm text-charcoal/60">This call has ended — no further action available.</p>;
  }

  return (
    <div className="space-y-3">
      {!connected ? (
        <Button variant="primary" size="sm" loading={connecting} onClick={handleTakeover}>
          Take over call
        </Button>
      ) : (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-800">
            <span className="h-1.5 w-1.5 rounded-full bg-green-600" /> Live — your mic is on
          </span>
          <Button variant="secondary" size="sm" onClick={handleDisconnect}>
            Leave call
          </Button>
        </div>
      )}
      <Button variant="danger" size="sm" loading={ending} onClick={handleEndCall}>
        End call
      </Button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
