import React from 'react';

const SEGMENTS = ['S1', 'S2', 'S3', 'S4', 'S5'];

const SEGMENT_LABELS = {
  S1: 'Weston Rd',
  S2: 'Keele St',
  S3: 'Dufferin St',
  S4: 'Allen Rd',
  S5: 'Bathurst St',
};

function CameraFeed({ segmentId }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">{segmentId}</span>
        <span className="text-[9px] text-gray-600">{SEGMENT_LABELS[segmentId]}</span>
      </div>
      <div className="relative w-full aspect-video bg-gray-900 rounded-md border border-gray-800 overflow-hidden flex items-center justify-center">
        {/* Scanline overlay for CRT effect */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.18) 2px, rgba(0,0,0,0.18) 4px)',
          }}
        />
        {/* Noise texture */}
        <div className="absolute inset-0 opacity-5"
          style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'1\'/%3E%3C/svg%3E")' }}
        />
        <div className="flex flex-col items-center gap-1 z-10">
          <span className="text-[10px] font-mono text-gray-600 tracking-widest uppercase">No Signal</span>
          <span className="w-8 h-px bg-gray-700" />
          <span className="text-[8px] font-mono text-gray-700">CAM-{segmentId}-01</span>
        </div>
        {/* Recording indicator */}
        <div className="absolute top-1.5 right-1.5 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-700" />
          <span className="text-[7px] font-mono text-gray-700 uppercase">offline</span>
        </div>
        {/* Timestamp */}
        <div className="absolute bottom-1.5 left-1.5 text-[7px] font-mono text-gray-700">
          {new Date().toLocaleTimeString('en-CA', { hour12: false })}
        </div>
      </div>
    </div>
  );
}

export default function CctvSidebar({ open, onClose }) {
  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px]"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed top-0 right-0 h-full z-50 w-72 bg-gray-950 border-l border-gray-800 flex flex-col
          transition-transform duration-300 ease-in-out
          ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800 shrink-0">
          <span className="text-[10px] text-gray-500">📷</span>
          <span className="text-xs font-bold text-gray-300 uppercase tracking-widest">Live Footage</span>
          <span className="ml-auto text-[9px] text-gray-600 font-mono">HWY 401 W</span>
          <button
            onClick={onClose}
            className="ml-2 text-gray-600 hover:text-gray-200 transition-colors text-sm leading-none"
            title="Close"
          >
            ✕
          </button>
        </div>

        {/* Feed grid */}
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          {SEGMENTS.map(seg => (
            <CameraFeed key={seg} segmentId={seg} />
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-800 flex items-center gap-2 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-700" />
          <span className="text-[9px] text-gray-600 font-mono uppercase">Camera feeds offline — integration pending</span>
        </div>
      </div>
    </>
  );
}
