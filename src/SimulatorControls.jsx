import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchSimulatorStatus, controlSimulator } from './api';

export default function SimulatorControls() {
  const qc = useQueryClient();
  const [confirmClear, setConfirmClear] = useState(false);

  const { data } = useQuery({
    queryKey:        ['simulatorStatus'],
    queryFn:         fetchSimulatorStatus,
    refetchInterval: 3000,
  });
  const running = data?.running ?? true;

  const mutate = useMutation({
    mutationFn: controlSimulator,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['simulatorStatus'] });
      // Also refresh data caches so the UI reacts immediately
      qc.invalidateQueries({ queryKey: ['status'] });
      qc.invalidateQueries({ queryKey: ['readings'] });
      qc.invalidateQueries({ queryKey: ['readings-alerts'] });
    },
  });

  const handleClear = () => {
    if (!confirmClear) { setConfirmClear(true); return; }
    setConfirmClear(false);
    mutate.mutate('clear');
  };

  const busy = mutate.isPending;

  return (
    <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-2">
      {/* Confirm clear tooltip */}
      {confirmClear && (
        <div className="flex items-center gap-2 bg-gray-800 border border-red-700 rounded-lg px-3 py-1.5 shadow-lg text-xs">
          <span className="text-red-400">Delete all readings?</span>
          <button
            onClick={handleClear}
            className="px-2 py-0.5 rounded bg-red-700 hover:bg-red-600 text-white font-semibold transition-colors"
          >
            Yes
          </button>
          <button
            onClick={() => setConfirmClear(false)}
            className="px-2 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
          >
            No
          </button>
        </div>
      )}

      {/* Button row */}
      <div className="flex items-center gap-1 bg-gray-900/90 backdrop-blur border border-gray-700 rounded-xl px-2 py-1.5 shadow-xl">
        {/* Status dot */}
        <span className={`w-2 h-2 rounded-full mr-1 transition-colors ${running ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />

        {running ? (
          <button
            disabled={busy}
            onClick={() => mutate.mutate('stop')}
            title="Stop simulation"
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold
              bg-yellow-700/80 hover:bg-yellow-600 border border-yellow-600 text-yellow-100
              disabled:opacity-50 transition-all"
          >
            ⏸ Stop
          </button>
        ) : (
          <button
            disabled={busy}
            onClick={() => mutate.mutate('start')}
            title="Resume simulation"
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold
              bg-emerald-700/80 hover:bg-emerald-600 border border-emerald-600 text-emerald-100
              disabled:opacity-50 transition-all"
          >
            ▶ Start
          </button>
        )}

        <button
          disabled={busy}
          onClick={handleClear}
          title="Stop and clear all readings"
          className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold
            bg-red-900/70 hover:bg-red-800 border border-red-700 text-red-300
            disabled:opacity-50 transition-all"
        >
          🗑 Clear
        </button>
      </div>
    </div>
  );
}
